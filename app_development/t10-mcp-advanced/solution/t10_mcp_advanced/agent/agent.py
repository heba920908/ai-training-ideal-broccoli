import json
from collections import defaultdict
from typing import Any

from commons.models.message import Message
from commons.models.role import Role
from openai import AsyncOpenAI
from t10_mcp_advanced.agent.clients.custom_mcp_client import CustomMCPClient
from t10_mcp_advanced.agent.clients.mcp_client import MCPClient
from t10_mcp_advanced.config import validate_base_url


class CustomAgentMCP:
    """Handles AI model interactions and integrates with MCP client"""

    def __init__(
        self,
        api_key: str,
        model: str,
        tools: list[dict[str, Any]],
        tool_name_client_map: dict[str, MCPClient | CustomMCPClient],
        *,
        base_url: str,
        max_tool_rounds: int = 10,
        http_client=None,
    ):
        self.model = model
        self.tools = tools
        self.tool_name_client_map = tool_name_client_map
        if max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be positive")
        self.max_tool_rounds = max_tool_rounds
        self.model_calls = 0
        self.openai = AsyncOpenAI(
            api_key=api_key,
            base_url=validate_base_url(base_url),
            default_headers={"Api-Key": api_key},
            timeout=90,
            max_retries=1,
            http_client=http_client,
        )

    def _collect_tool_calls(self, tool_deltas):
        """Convert streaming tool call deltas to complete tool calls"""
        tool_dict = defaultdict(
            lambda: {
                "id": None,
                "function": {"arguments": "", "name": None},
                "type": None,
            }
        )

        for delta in tool_deltas:
            idx = delta.index
            if delta.id:
                tool_dict[idx]["id"] = delta.id
            if delta.function and delta.function.name:
                tool_dict[idx]["function"]["name"] = delta.function.name
            if delta.function and delta.function.arguments:
                tool_dict[idx]["function"]["arguments"] += delta.function.arguments
            if delta.type:
                tool_dict[idx]["type"] = delta.type

        return list(tool_dict.values())

    async def _stream_response(self, messages: list[Message]) -> Message:
        """Stream OpenAI response and handle tool calls"""
        stream = await self.openai.chat.completions.create(
            **{
                "model": self.model,
                "messages": [msg.to_dict() for msg in messages],
                **({"tools": self.tools} if self.tools else {}),
                "stream": True,
            }
        )

        content = ""
        tool_deltas = []

        self.model_calls += 1
        print("Assistant: ", end="", flush=True)

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                print(delta.content, end="", flush=True)
                content += delta.content

            if delta.tool_calls:
                tool_deltas.extend(delta.tool_calls)

        print()
        return Message(
            role=Role.ASSISTANT,
            content=content,
            tool_calls=self._collect_tool_calls(tool_deltas) if tool_deltas else [],
        )

    async def get_completion(self, messages: list[Message]) -> Message:
        for _ in range(self.max_tool_rounds):
            ai_message = await self._stream_response(messages)
            if not ai_message.tool_calls:
                return ai_message
            messages.append(ai_message)
            await self._call_tools(ai_message, messages)
        return Message(
            Role.ASSISTANT,
            "Stopped: tool round limit reached. Please narrow the request.",
        )

    async def _call_tools(self, ai_message: Message, messages: list[Message]):
        """Execute tool calls using MCP client"""
        for tool_call in ai_message.tool_calls:
            tool_name = tool_call["function"]["name"]
            try:
                tool_args = json.loads(tool_call["function"]["arguments"])
                if not isinstance(tool_args, dict):
                    raise TypeError("Tool arguments must be a JSON object")
                client = self.tool_name_client_map.get(tool_name)
                if not client:
                    raise ValueError(
                        f"Unable to call {tool_name}. MCP client not found."
                    )

                tool_result = await client.call_tool(tool_name, tool_args)

                messages.append(
                    Message(
                        role=Role.TOOL,
                        content=str(tool_result),
                        tool_call_id=tool_call["id"],
                    )
                )
            except Exception as e:
                error_msg = f"Error: {e}"
                print(f"Error: {error_msg}")
                messages.append(
                    Message(
                        role=Role.TOOL,
                        content=error_msg,
                        tool_call_id=tool_call["id"],
                    )
                )
