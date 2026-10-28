from datetime import timedelta
from typing import Any, Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import (
    BlobResourceContents,
    CallToolResult,
    ReadResourceResult,
    TextContent,
    TextResourceContents,
)
from pydantic import AnyUrl
from t12_skills.config import MCP_TIMEOUT
from t12_skills.custom.mcp.mcp_tool_model import MCPToolModel


class T12MCPClient:
    """Handles MCP server connection and tool execution"""

    def __init__(self, mcp_server_url: str) -> None:
        self.server_url = mcp_server_url
        self.session: Optional[ClientSession] = None
        self._streams_context = None
        self._session_context = None

    @classmethod
    async def create(cls, mcp_server_url: str) -> "T12MCPClient":
        """Async factory method to create and connect MCPClient"""
        instance = cls(mcp_server_url)
        await instance.connect()
        return instance

    async def connect(self):
        """Connect to MCP server"""
        if self.session is not None:
            return  # Already connected

        try:
            streams_context = streamable_http_client(self.server_url)
            read_stream, write_stream, _ = await streams_context.__aenter__()
            self._streams_context = streams_context
            session_context = ClientSession(
                read_stream,
                write_stream,
                read_timeout_seconds=timedelta(seconds=MCP_TIMEOUT),
            )
            self.session = await session_context.__aenter__()
            self._session_context = session_context
            await self.session.initialize()
            await self.session.send_ping()
        except BaseException:
            await self.close()
            raise

    async def get_tools(self) -> list[MCPToolModel]:
        """Get available tools from MCP server"""
        if not self.session:
            raise RuntimeError("MCP client not connected.")

        tools = await self.session.list_tools()
        return [
            MCPToolModel(
                name=tool.name,
                description=tool.description,
                parameters=tool.inputSchema,
            )
            for tool in tools.tools
        ]

    async def call_tool(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        """Call a tool on the MCP server"""
        if not self.session:
            raise RuntimeError("MCP client not connected.")

        tool_result: CallToolResult = await self.session.call_tool(tool_name, tool_args)

        if tool_result.isError:
            raise ValueError("MCP execution reported an error; code was not replayed")
        if len(tool_result.content) != 1 or not isinstance(tool_result.content[0], TextContent):
            raise ValueError("MCP execution requires exactly one text result")
        return tool_result.content[0].text

    async def get_resource(self, uri: AnyUrl) -> str | bytes:
        """Get specific resource content"""
        if not self.session:
            raise RuntimeError("MCP client not connected.")

        resource_result: ReadResourceResult = await self.session.read_resource(uri)

        if not resource_result.contents:
            raise ValueError(f"No content in resource: {uri}")

        content = resource_result.contents[0]

        if isinstance(content, TextResourceContents):
            return content.text
        elif isinstance(content, BlobResourceContents):
            return content.blob
        else:
            raise ValueError(f"Unexpected content type: {type(content)}")

    async def close(self):
        """Close connection to MCP server"""
        session_context, self._session_context = self._session_context, None
        streams_context, self._streams_context = self._streams_context, None
        self.session = None
        try:
            if session_context:
                await session_context.__aexit__(None, None, None)
        except Exception:
            print("Warning: MCP session cleanup failed")
        finally:
            try:
                if streams_context:
                    await streams_context.__aexit__(None, None, None)
            except Exception:
                print("Warning: MCP transport cleanup failed")

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        return False
