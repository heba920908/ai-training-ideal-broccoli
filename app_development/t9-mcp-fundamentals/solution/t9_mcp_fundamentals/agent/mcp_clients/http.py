from mcp import Client
from t9_mcp_fundamentals.agent.mcp_clients.base import MCPClient


class HttpMCPClient(MCPClient):
    """Handles MCP server connection and tool execution via http"""

    def __init__(self, mcp_server_url: str) -> None:
        super().__init__()
        self.mcp_server_url = mcp_server_url

    async def __aenter__(self):
        client = Client(self.mcp_server_url, read_timeout_seconds=60)
        await client.__aenter__()
        self.client = client
        print(
            f"Connected to {client.server_info} (protocol version {client.protocol_version})"
        )
        print(client.server_capabilities.model_dump_json(indent=2, exclude_none=True))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            try:
                await self.client.__aexit__(exc_type, exc_val, exc_tb)
            finally:
                self.client = None
