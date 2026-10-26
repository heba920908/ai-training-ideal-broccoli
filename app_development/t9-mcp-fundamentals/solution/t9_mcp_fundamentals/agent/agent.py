import json
from collections import defaultdict
from typing import Any

from commons.models.message import Message
from commons.models.role import Role
from openai import AsyncOpenAI
from t9_mcp_fundamentals.agent.mcp_clients.base import MCPClient


class AgentMCPFundamentals:
    """Handles AI model interactions and integrates with MCP client"""

    def __init__(
        self,
        api_key: str,
        model: str,
        tools: list[dict[str, Any]],
        mcp_client: MCPClient,
        *,
        base_url: str,
        tool_clients: dict[str, MCPClient] | None = None,
        max_tool_rounds: int = 10,
    ):
        self.model = model
        self.tools = tools
        self.mcp_client = mcp_client
        self.tool_clients = (
            tool_clients
            if tool_clients is not None
            else {tool["function"]["name"]: mcp_client for tool in tools}
        )
        self.max_tool_rounds = max_tool_rounds
        self.openai = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=60)

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

        print("Assistant: ", end="", flush=True)

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            # Stream content
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

    async def get_response(self, messages: list[Message]) -> Message:
        """Process user query with streaming and tool calling"""
        for _ in range(self.max_tool_rounds):
            ai_message = await self._stream_response(messages)
            if not ai_message.tool_calls:
                return ai_message
            messages.append(ai_message)
            await self._call_tools(ai_message, messages)
        response = Message(
            role=Role.ASSISTANT,
            content="Stopped: tool round limit reached. Please narrow the request.",
        )
        print(f"Assistant: {response.content}")
        return response

    async def _call_tools(self, ai_message: Message, messages: list[Message]):
        """Execute tool calls using MCP client"""
        for call in ai_message.tool_calls or []:
            name = call["function"]["name"]
            try:
                arguments = json.loads(call["function"]["arguments"])
                if not isinstance(arguments, dict):
                    raise TypeError("Tool arguments must be a JSON object")
                if name not in self.tool_clients:
                    raise ValueError(f"Unknown tool: {name}")
                result = await self.tool_clients[name].call_tool(name, arguments)
                content = (
                    result
                    if isinstance(result, str)
                    else json.dumps(result, default=str)
                )
            except Exception as error:
                content = f"Error calling {name}: {error}"
            messages.append(
                Message(role=Role.TOOL, content=content, tool_call_id=call["id"])
            )
