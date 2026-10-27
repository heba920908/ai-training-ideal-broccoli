from typing import Any

from mcp import Client
from t10_mcp_advanced.agent.clients.results import tool_text


class MCPClient:
    """Handles MCP server connection and tool execution"""

    def __init__(self, mcp_server_url: str) -> None:
        self.server_url = mcp_server_url
        self.client: Client | None = None

    @classmethod
    async def create(cls, mcp_server_url: str) -> "MCPClient":
        """Async factory method to create and connect MCPClient"""
        instance = cls(mcp_server_url)
        await instance.connect()
        return instance

    async def connect(self):
        """Connect to MCP server"""
        # Client calls `server/discover` to select the protocol version. It falls back to the legacy
        # `initialize` handshake only if the server doesn't support stateless MCP (2026-07-28)
        self.client = Client(self.server_url)
        try:
            await self.client.__aenter__()
        except BaseException:
            self.client = None
            raise

        print(
            f"Connected to {self.client.server_info} (protocol version {self.client.protocol_version})"
        )
        print(
            self.client.server_capabilities.model_dump_json(indent=2, exclude_none=True)
        )

    async def close(self):
        """Close connection to MCP server"""
        if self.client:
            await self.client.__aexit__(None, None, None)
            self.client = None

    async def get_tools(self) -> list[dict[str, Any]]:
        """Get available tools from MCP server"""
        if not self.client:
            raise RuntimeError("MCP client not connected. Call connect() first.")

        schemas = []
        cursor = None
        while True:
            tools = await self.client.list_tools(cursor=cursor)
            schemas.extend(
                [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.input_schema,
                        },
                    }
                    for tool in tools.tools
                ]
            )
            if not tools.next_cursor:
                return schemas
            if tools.next_cursor == cursor:
                raise RuntimeError("Repeated tools/list cursor")
            cursor = tools.next_cursor

    async def call_tool(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        """Call a specific tool on the MCP server"""
        if not self.client:
            raise RuntimeError("MCP client not connected. Call connect() first.")

        print(f"    Calling `{tool_name}` with {tool_args}")

        result = await self.client.call_tool(tool_name, tool_args)
        text = tool_text(result.model_dump(by_alias=True, exclude_none=True))
        print(text)
        return text
