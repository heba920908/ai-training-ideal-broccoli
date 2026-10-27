from t11_mcp_auth.agent.mcp_clients._base import T11MCPClient


class ApiKeyMCPClient(T11MCPClient):
    """Handles MCP server connection and tool execution via http"""

    def __init__(self, mcp_server_url: str, api_key: str) -> None:
        super().__init__()
        self.mcp_server_url = mcp_server_url
        self.api_key = api_key

    async def __aenter__(self):
        if not self.api_key:
            raise ValueError("MCP_API_KEY is required")
        return await self._connect({"X-API-Key": self.api_key})
