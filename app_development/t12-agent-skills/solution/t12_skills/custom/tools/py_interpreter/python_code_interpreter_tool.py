from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError
from t12_skills.custom.file_utils import get_file_content, resolve_skill_path
from t12_skills.custom.mcp.mcp_client import T12MCPClient
from t12_skills.custom.mcp.mcp_tool_model import MCPToolModel
from t12_skills.custom.tools.base import BaseTool
from t12_skills.custom.tools.py_interpreter._response import _ExecutionResult


class PythonCodeInterpreterTool(BaseTool):
    def __init__(
        self,
        mcp_client: T12MCPClient,
        mcp_tool_models: list[MCPToolModel],
        tool_name: str,
        skills_dir: Path,
    ):
        self._mcp_client = mcp_client
        self._skills_dir = skills_dir

        self._code_execute_tool: Optional[MCPToolModel] = next(
            (tool for tool in mcp_tool_models if tool.name == tool_name), None
        )
        if self._code_execute_tool is None:
            available = ", ".join(tool.name for tool in mcp_tool_models) or "none"
            raise ValueError(f"Missing MCP tool {tool_name}; available: {available}")

    @classmethod
    async def create(
        cls, mcp_url: str, tool_name: str, skills_dir: Path
    ) -> "PythonCodeInterpreterTool":
        """Async factory method to create PythonCodeInterpreterTool."""
        client = await T12MCPClient.create(mcp_url)
        try:
            tools = await client.get_tools()
            return cls(client, tools, tool_name, skills_dir)
        except BaseException:
            await client.close()
            raise

    async def close(self):
        await self._mcp_client.close()

    @property
    def name(self) -> str:
        return self._code_execute_tool.name

    @property
    def description(self) -> str:
        return self._code_execute_tool.description or "Execute Python in a persistent session"

    @property
    def parameters(self) -> dict[str, Any]:
        parameters = deepcopy(self._code_execute_tool.parameters)
        parameters.setdefault("properties", {})["script_path"] = {
            "type": "string",
            "description": "Optional skill-relative Python file to prepend to code. Omit when reusing an initialized session.",
        }
        return parameters

    async def _execute(self, arguments: dict[str, Any]) -> str:
        code = arguments.get("code")
        session_id = arguments.get("session_id", "")
        if not isinstance(code, str) or not isinstance(session_id, str):
            raise ValueError("code and session_id must be strings")
        script_path = arguments.get("script_path")
        if script_path:
            script = get_file_content(resolve_skill_path(self._skills_dir, script_path))
            code = script + "\n\n" + code
        response = await self._mcp_client.call_tool(
            self.name, {"code": code, "session_id": session_id}
        )
        try:
            return _ExecutionResult.model_validate_json(response).model_dump_json()
        except (ValidationError, TypeError):
            raise ValueError(
                "Invalid interpreter result JSON/schema; execution was not replayed"
            ) from None
