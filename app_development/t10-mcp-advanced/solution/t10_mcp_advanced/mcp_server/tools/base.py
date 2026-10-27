from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """
    Abstract base class for all tools. All tools must inherit from this class.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        pass

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> str:
        """Execute the tool with MCP-compliant arguments

        Args:
            arguments: Dictionary containing the tool arguments as passed
                      by the MCP client (extracted from params.arguments)

        Returns:
            str: Tool execution result that will be wrapped in MCP content format
        """

    def to_mcp_tool(self) -> dict[str, Any]:
        """Provides tools JSON Schema"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }
