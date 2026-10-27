import json
from collections import defaultdict
from typing import Any

from commons.models.message import Message
from commons.models.role import Role
from openai import AsyncOpenAI
from t11_mcp_auth.agent.mcp_clients._base import T11MCPClient
from t11_mcp_auth.config import dial_base_url, redact


class AgentMCPAuth:
    """Handles AI model interactions and integrates with MCP client"""

    def __init__(
        self,
        api_key: str,
        model: str,
        tools: list[dict[str, Any]],
        mcp_client: T11MCPClient,
        base_url: str | None = None,
    ):
        self.model = model
        self.tools = tools
        self.mcp_client = mcp_client
        self._secrets = [api_key, getattr(mcp_client, "api_key", "")]
        self._token_manager = getattr(mcp_client, "token_manager", None)
        self.openai = AsyncOpenAI(
            api_key=api_key,
            base_url=dial_base_url(base_url),
            default_headers={"Api-Key": api_key},
            timeout=90,
            max_retries=1,
        )

    def _collect_tool_calls(self, tool_deltas):
        """Convert streaming tool call deltas to complete tool calls"""
        tool_dict = defaultdict(
            lambda: {
                "id": None,
                "function": {"arguments": "", "name": ""},
                "type": None,
            }
        )

        for delta in tool_deltas:
            idx = delta.index
            if delta.id:
                tool_dict[idx]["id"] = delta.id
            if delta.function and delta.function.name:
                tool_dict[idx]["function"]["name"] += delta.function.name
            if delta.function and delta.function.arguments:
                tool_dict[idx]["function"]["arguments"] += delta.function.arguments
            if delta.type:
                tool_dict[idx]["type"] = delta.type

        return [tool_dict[index] for index in sorted(tool_dict)]

    def _redact(self, value):
        tokens = [
            getattr(self._token_manager, name, "")
            for name in (
                "access_token",
                "refresh_token",
                "code_verifier",
                "code",
                "state",
                "_access_token",
                "_refresh_token",
                "_code_verifier",
                "_code",
                "_state",
            )
        ]
        return redact(value, secrets=(*self._secrets, *tokens))

    async def _stream_response(self, messages: list[Message]) -> Message:
        """Stream OpenAI response and handle tool calls"""
        stream = await self.openai.chat.completions.create(
            **{
                "model": self.model,
                "messages": self._redact([msg.to_dict() for msg in messages]),
                **({"tools": self._redact(self.tools)} if self.tools else {}),
                "stream": True,
            }
        )

        content = ""
        tool_deltas = []

        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    content += delta.content
                if delta.tool_calls:
                    tool_deltas.extend(delta.tool_calls)
        finally:
            await stream.close()
        return Message(
            role=Role.ASSISTANT,
            content=self._redact(content),
            tool_calls=self._collect_tool_calls(tool_deltas) if tool_deltas else [],
        )

    async def get_completion(self, messages: list[Message]) -> Message:
        """Process user query with streaming and tool calling"""
        for _round in range(10):
            try:
                ai_message = await self._stream_response(messages)
            except Exception:  # noqa: BLE001
                raise RuntimeError(
                    "DIAL request failed; check provider configuration."
                ) from None
            if not ai_message.tool_calls:
                return ai_message
            messages.append(ai_message)
            await self._call_tools(ai_message, messages)
        raise RuntimeError("Model tool round limit reached (10 requests).")

    async def _call_tools(self, ai_message: Message, messages: list[Message]):
        """Execute tool calls using MCP client"""
        for tool_call in ai_message.tool_calls:
            try:
                tool_name = tool_call["function"]["name"]
                tool_args = json.loads(tool_call["function"]["arguments"])
                if not isinstance(tool_args, dict):
                    raise TypeError
            except (ValueError, TypeError, KeyError):
                tool_result = "Tool error: arguments must be a valid JSON object."
            else:
                try:
                    tool_result = await self.mcp_client.call_tool(tool_name, tool_args)
                except Exception:  # noqa: BLE001
                    tool_result = "Tool error: MCP request failed; check authentication and service availability."
            safe_result = self._redact(tool_result)
            messages.append(
                Message(
                    role=Role.TOOL,
                    content=safe_result
                    if isinstance(safe_result, str)
                    else json.dumps(safe_result),
                    tool_call_id=tool_call["id"],
                )
            )
