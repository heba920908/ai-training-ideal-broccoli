import json
from typing import Any

from t13_final_task.task.agent.clients.base_mcp_client import BaseMcpClient
from t13_final_task.task.agent.models import McpToolModel
from t13_final_task.task.agent.tools.base import BaseTool


class McpTool(BaseTool):
    """Exposes one MCP server tool through the agent's tool interface."""

    def __init__(self, client: BaseMcpClient, mcp_tool_model: McpToolModel):
        self._client = client
        self._mcp_tool_model = mcp_tool_model

    async def _execute(self, arguments: dict[str, Any]) -> str:
        result = await self._client.call_tool(self.name, arguments)
        if result is None:
            return "No content returned from tool"
        if isinstance(result, str):
            return result
        if isinstance(result, list):
            return "\n".join(
                getattr(item, "text", None) or json.dumps(item.model_dump(mode="json"))
                for item in result
            )
        return str(result)

    @property
    def name(self) -> str:
        return self._mcp_tool_model.name

    @property
    def description(self) -> str:
        return self._mcp_tool_model.description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._mcp_tool_model.parameters
