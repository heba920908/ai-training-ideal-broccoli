from typing import Any

from t10_mcp_advanced.mcp_server.tools.users.base import BaseUserServiceTool


class DeleteUserTool(BaseUserServiceTool):
    @property
    def name(self) -> str:
        return "delete_users"

    @property
    def description(self) -> str:
        return "Delete a user by ID. Only delete a record when explicitly requested."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
            "additionalProperties": False,
        }

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await self.call_service("delete_user", arguments, arguments["id"])
