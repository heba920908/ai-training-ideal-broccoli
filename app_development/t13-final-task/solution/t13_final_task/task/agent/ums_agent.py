import asyncio
import json
import logging
from collections import defaultdict
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI
from t13_final_task.task.agent.config import MAX_TOOL_ROUNDS
from t13_final_task.task.agent.guardrail import UMSDataGuardrail
from t13_final_task.task.agent.models import Message, Role
from t13_final_task.task.agent.tools.base import BaseTool

logger = logging.getLogger(__name__)

_LIMIT_MESSAGE = (
    "I stopped because the tool-call limit for one request was reached. "
    "Please narrow the request and try again."
)
_STREAM_ERROR = "The assistant could not complete the request. Please try again."


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _content_chunk(content: str | None, finish_reason: str | None = None) -> str:
    delta = {"content": content} if content is not None else {}
    return _sse({"choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]})


class UMSAgent:
    """Handles AI model interactions and integrates with MCP client"""

    def __init__(
        self,
        api_key: str,
        model: str,
        tools: list[BaseTool],
        base_url: str | None = None,
        client: Any = None,
        guardrail: Any = None,
        max_tool_rounds: int = MAX_TOOL_ROUNDS,
    ):
        self.tools: dict[str, BaseTool] = {tool.name: tool for tool in tools}
        self.tools_schemas = [tool.schema for tool in tools]
        self.model = model
        self.async_openai = client or AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={"Api-Key": api_key},
            timeout=90,
            max_retries=1,
        )
        self.guardrail = guardrail or UMSDataGuardrail()
        self.max_tool_rounds = max_tool_rounds

    def _request(self, messages: list[Message], stream: bool) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self.model,
            "messages": [message.to_dict() for message in messages],
            "stream": stream,
        }
        if self.tools_schemas:
            request["tools"] = self.tools_schemas
        return request

    async def response(self, messages: list[Message]) -> Message:
        """Non-streaming completion with tool calling support"""
        rounds = 0
        while True:
            completion = await self.async_openai.chat.completions.create(
                **self._request(messages, stream=False)
            )
            choice = completion.choices[0].message
            ai_message = Message(role=Role.ASSISTANT, content=choice.content or "")
            if not choice.tool_calls:
                messages.append(ai_message)
                return ai_message

            ai_message.tool_calls = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.function.name, "arguments": call.function.arguments},
                }
                for call in choice.tool_calls
            ]
            messages.append(ai_message)
            await self._call_tools(ai_message, messages)
            rounds += 1
            if rounds >= self.max_tool_rounds:
                limit_message = Message(role=Role.ASSISTANT, content=_LIMIT_MESSAGE)
                messages.append(limit_message)
                return limit_message

    async def stream_response(
        self, messages: list[Message], _round: int = 0
    ) -> AsyncGenerator[str, None]:
        """
        Streaming completion with tool calling support.
        Yields SSE-formatted chunks.
        """
        try:
            stream = await self.async_openai.chat.completions.create(
                **self._request(messages, stream=True)
            )
            content = ""
            tool_deltas = []
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    content += delta.content
                    yield _content_chunk(delta.content)
                if delta.tool_calls:
                    tool_deltas.extend(delta.tool_calls)

            if tool_deltas:
                ai_message = Message(
                    role=Role.ASSISTANT,
                    content=content,
                    tool_calls=self._collect_tool_calls(tool_deltas),
                )
                messages.append(ai_message)
                for tool_call in ai_message.tool_calls:
                    name, arguments = self._parse_call(tool_call)
                    yield _sse(
                        {
                            "tool_activity": {
                                "type": "call",
                                "name": name,
                                "arguments": arguments if arguments is not None else {},
                            }
                        }
                    )
                    tool_message = await self._execute_tool_call(tool_call)
                    messages.append(tool_message)
                    yield _sse(
                        {
                            "tool_activity": {
                                "type": "result",
                                "name": name,
                                "content": tool_message.content,
                            }
                        }
                    )

                if _round + 1 >= self.max_tool_rounds:
                    messages.append(Message(role=Role.ASSISTANT, content=_LIMIT_MESSAGE))
                    yield _content_chunk(_LIMIT_MESSAGE)
                else:
                    async for item in self.stream_response(messages, _round + 1):
                        yield item
                    return
            else:
                messages.append(Message(role=Role.ASSISTANT, content=content))
        except Exception:
            logger.exception("Streaming completion failed")
            yield _sse({"error": _STREAM_ERROR})
            yield "data: [DONE]\n\n"
            return

        yield _content_chunk(None, finish_reason="stop")
        yield "data: [DONE]\n\n"

    def _collect_tool_calls(self, tool_deltas):
        """Convert streaming tool call deltas to complete tool calls"""
        tool_dict = defaultdict(
            lambda: {"id": None, "function": {"arguments": "", "name": ""}, "type": None}
        )
        for delta in tool_deltas:
            entry = tool_dict[delta.index]
            if delta.id:
                entry["id"] = delta.id
            if delta.type:
                entry["type"] = delta.type
            if delta.function:
                if delta.function.name:
                    entry["function"]["name"] += delta.function.name
                if delta.function.arguments:
                    entry["function"]["arguments"] += delta.function.arguments
        calls = list(tool_dict.values())
        for call in calls:
            call["type"] = call["type"] or "function"
        return calls

    @staticmethod
    def _parse_call(tool_call: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
        function = tool_call["function"]
        try:
            arguments = json.loads(function.get("arguments") or "{}")
        except json.JSONDecodeError:
            return function["name"], None
        return function["name"], arguments if isinstance(arguments, dict) else None

    async def _execute_tool_call(self, tool_call: dict[str, Any]) -> Message:
        name, arguments = self._parse_call(tool_call)
        tool = self.tools.get(name)
        if tool is None:
            message = Message(
                role=Role.TOOL,
                tool_call_id=tool_call["id"],
                content=f"ERROR: unknown tool '{name}'",
            )
        elif arguments is None:
            message = Message(
                role=Role.TOOL,
                tool_call_id=tool_call["id"],
                content=f"ERROR: invalid arguments for '{name}'; expected a JSON object",
            )
        else:
            message = await tool.execute(tool_call["id"], arguments)
        message.content = await asyncio.to_thread(self.guardrail.redact, message.content)
        return message

    async def _call_tools(self, ai_message: Message, messages: list[Message], silent: bool = False):
        """Execute tool calls sequentially; every result is PII-redacted before it is stored."""
        for tool_call in ai_message.tool_calls:
            messages.append(await self._execute_tool_call(tool_call))
