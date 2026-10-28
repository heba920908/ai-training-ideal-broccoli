import asyncio
import inspect
import json

from commons.models.message import Message
from commons.models.role import Role
from openai import OpenAI
from t12_skills.config import MAX_ROUNDS
from t12_skills.custom.tools.base import BaseTool


class T12Agent:
    def __init__(self, client: OpenAI, model: str, tools: list[BaseTool] | None = None):
        self._client = client
        self._model = model
        self._tools: dict[str, BaseTool] = {}
        for tool in tools or []:
            if tool.name in self._tools:
                raise ValueError(f"Duplicate tool name: {tool.name}")
            self._tools[tool.name] = tool
        self._tools_schemas = [tool.schema for tool in tools] if tools else []
        self.usage = []

    async def chat_completion(self, messages: list[Message], log_messages: bool = False) -> Message:
        if log_messages:
            print("\n--- REQUEST ---")
            print(json.dumps([msg.to_dict() for msg in messages], indent=2, default=str))

        return await self._chat_completion(messages, log_messages)

    async def _chat_completion(
        self, messages: list[Message], log_messages: bool = False
    ) -> Message:
        for _ in range(MAX_ROUNDS):
            request = {
                "model": self._model,
                "messages": [message.to_dict() for message in messages],
            }
            if self._tools_schemas:
                request["tools"] = self._tools_schemas
            create = self._client.chat.completions.create
            if inspect.iscoroutinefunction(create):
                response = await create(**request)
            else:
                response = await asyncio.to_thread(create, **request)
                if inspect.isawaitable(response):
                    response = await response
            if response.usage:
                self.usage.append(response.usage.model_dump())
            if not response.choices:
                raise RuntimeError("Provider returned no completion choices")
            choice = response.choices[0]
            reply = choice.message
            if getattr(reply, "refusal", None):
                raise RuntimeError("Provider refused the request")
            calls = reply.tool_calls or []
            serialized = [
                {
                    "id": call.id,
                    "type": call.type,
                    "function": {"name": call.function.name, "arguments": call.function.arguments},
                }
                for call in calls
            ]
            assistant = Message(Role.ASSISTANT, reply.content or "", tool_calls=serialized or None)
            if choice.finish_reason == "tool_calls" and calls:
                messages.append(assistant)
                messages.extend(await self._dispatch_tool_calls(calls))
                if log_messages:
                    print(json.dumps([message.to_dict() for message in messages], default=str))
                continue
            if choice.finish_reason != "stop" or calls:
                raise RuntimeError(f"Provider did not complete normally: {choice.finish_reason}")
            return assistant
        raise RuntimeError(f"Agent stopped after {MAX_ROUNDS} model/tool rounds")

    async def _dispatch_tool_calls(self, tool_calls) -> list[Message]:
        results = []
        for call in tool_calls:
            name = call.function.name
            tool = self._tools.get(name)
            try:
                arguments = json.loads(call.function.arguments)
                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be a JSON object")
                if tool is None:
                    content = "ERROR: Unknown tool"
                else:
                    content = (await tool.execute(call.id, arguments)).content
            except (ValueError, TypeError):
                content = "ERROR: Tool arguments must be a valid JSON object"
            except Exception:
                content = "ERROR: Tool execution failed"
            results.append(Message(Role.TOOL, content, tool_call_id=call.id, name=name))
        return results
