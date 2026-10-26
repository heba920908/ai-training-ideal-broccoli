from abc import ABC, abstractmethod
from typing import Any

from mcp import Client
from mcp.types import (
    BlobResourceContents,
    Prompt,
    Resource,
    TextContent,
    TextResourceContents,
)
from pydantic import AnyUrl


class MCPClient(ABC):
    def __init__(self) -> None:
        self.client: Client | None = None

    @abstractmethod
    async def __aenter__(self): ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb): ...

    async def get_tools(self) -> list[dict[str, Any]]:
        """Get available tools from MCP server"""
        if not self.client:
            raise RuntimeError("MCP client not connected. Call connect() first.")
        schemas = []
        cursor = None
        while True:
            result = await self.client.list_tools(cursor=cursor)
            schemas.extend(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.input_schema,
                    },
                }
                for tool in result.tools
            )
            cursor = result.next_cursor
            if not cursor:
                return schemas

    async def call_tool(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        """Call a specific tool on the MCP server"""
        if not self.client:
            raise RuntimeError("MCP client not connected. Call connect() first.")

        result = await self.client.call_tool(tool_name, tool_args)
        content = "\n".join(
            block.text
            if isinstance(block, TextContent)
            else block.model_dump_json(by_alias=True)
            for block in result.content
        )
        if result.is_error:
            raise RuntimeError(content or f"Tool {tool_name} failed")
        print(f"Tool {tool_name}: completed")
        return content

    async def get_resources(self) -> list[Resource]:
        """Get available resources from MCP server"""
        if not self.client:
            raise RuntimeError("MCP client not connected.")
        try:
            resources = []
            cursor = None
            while True:
                result = await self.client.list_resources(cursor=cursor)
                resources.extend(result.resources)
                cursor = result.next_cursor
                if not cursor:
                    return resources
        except Exception as error:
            print(f"Resources unavailable: {error}")
            return []

    async def get_resource(self, uri: AnyUrl) -> str:
        """Get specific resource content"""
        if not self.client:
            raise RuntimeError("MCP client not connected.")

        result = await self.client.read_resource(str(uri))
        parts = []
        for content in result.contents:
            if isinstance(content, TextResourceContents):
                parts.append(content.text)
            elif isinstance(content, BlobResourceContents):
                parts.append(content.blob)
        return "\n".join(parts)

    async def get_prompts(self) -> list[Prompt]:
        """Get available prompts from MCP server"""
        if not self.client:
            raise RuntimeError("MCP client not connected.")
        try:
            prompts = []
            cursor = None
            while True:
                result = await self.client.list_prompts(cursor=cursor)
                prompts.extend(result.prompts)
                cursor = result.next_cursor
                if not cursor:
                    return prompts
        except Exception as error:
            print(f"Prompts unavailable: {error}")
            return []

    async def get_prompt(self, name: str) -> str:
        """Get specific prompt content"""
        if not self.client:
            raise RuntimeError("MCP client not connected.")
        result = await self.client.get_prompt(name)
        parts = []
        for message in result.messages:
            if isinstance(message.content, TextContent):
                parts.append(message.content.text)
            elif isinstance(message.content, str):
                parts.append(message.content)
        return "\n".join(parts)
