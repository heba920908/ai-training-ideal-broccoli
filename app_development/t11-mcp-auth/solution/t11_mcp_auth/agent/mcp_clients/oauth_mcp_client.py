from typing import Any

from t11_mcp_auth.agent.mcp_clients._base import T11MCPClient
from t11_mcp_auth.agent.mcp_clients._oauth_keycloak import OAuthTokenManager


class OauthHttpMCPClient(T11MCPClient):
    """
    MCP client that authenticates via OAuth 2.0 + PKCE.

    On __aenter__:
      1. Runs the PKCE browser flow (opens Keycloak login once)
      2. Connects to the MCP server with the resulting Bearer token

    On tool calls:
      - Proactively refreshes the token before it expires. MCP is stateless (no session), so the new token
        is simply sent with the next request, there is nothing to reconnect
    """

    def __init__(self, mcp_server_url: str) -> None:
        super().__init__()
        self.mcp_server_url = mcp_server_url
        self.token_manager = OAuthTokenManager()

    async def __aenter__(self):
        await self.token_manager.authenticate()
        return await self._connect(await self.token_manager.auth_headers())

    async def get_tools(self) -> list[dict[str, Any]]:
        """Get available tools from MCP server"""
        await self._ensure_fresh()
        return await super().get_tools()

    async def call_tool(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        """
        Call a tool on the MCP server.
        Proactively refreshes the token before it expires.
        """
        await self._ensure_fresh()
        return await self._do_call_tool(tool_name, tool_args)

    async def _do_call_tool(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        return await super().call_tool(tool_name, tool_args)

    async def _ensure_fresh(self) -> None:
        if self.client is None or self._http_client is None:
            raise RuntimeError("MCP client not connected")
        self._http_client.headers.update(await self.token_manager.auth_headers())

    async def _refresh_token(self) -> None:
        """Refresh OAuth token and send it with the next requests"""
        await self.token_manager.refresh()
        await self._ensure_fresh()
