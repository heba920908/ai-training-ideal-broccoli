from abc import ABC, abstractmethod
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent


class T11MCPClient(ABC):
    def __init__(self) -> None:
        self.client: Client | None = None
        self._http_client: httpx2.AsyncClient | None = None

    async def _connect(self, headers: dict[str, str]):
        self._http_client = httpx2.AsyncClient(headers=headers, timeout=60)
        self.client = Client(
            streamable_http_client(self.mcp_server_url, http_client=self._http_client),
            read_timeout_seconds=60,
            cache=None,
        )
        try:
            await self.client.__aenter__()
        except BaseException:
            await self._http_client.aclose()
            self.client = None
            raise
        return self

    @abstractmethod
    async def __aenter__(self): ...

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.client is not None:
                await self.client.__aexit__(exc_type, exc_val, exc_tb)
        finally:
            self.client = None
            if self._http_client is not None:
                await self._http_client.aclose()

    async def get_tools(self) -> list[dict[str, Any]]:
        """Get available tools from MCP server"""
        if self.client is None:
            raise RuntimeError("MCP client not connected")
        listing = await self.client.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema,
                },
            }
            for tool in listing.tools
        ]

    async def call_tool(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        """Call a specific tool on the MCP server"""
        if self.client is None:
            raise RuntimeError("MCP client not connected")
        result = await self.client.call_tool(tool_name, tool_args)
        text = (
            "\n".join(
                item.text if isinstance(item, TextContent) else item.model_dump_json()
                for item in result.content
            )
            or "(empty result)"
        )
        return f"Tool error: {text}" if result.is_error else text
