from typing import Any

from t10_mcp_advanced.mcp_server.tools.users.base import BaseUserServiceTool


class GetUserByIdTool(BaseUserServiceTool):
    @property
    def name(self) -> str:
        return "get_user_by_id"

    @property
    def description(self) -> str:
        return "Get a user by integer ID."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
            "additionalProperties": False,
        }

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await self.call_service("get_user", arguments, arguments["id"])
