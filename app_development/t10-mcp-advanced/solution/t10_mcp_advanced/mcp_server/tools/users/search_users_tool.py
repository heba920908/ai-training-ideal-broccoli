from typing import Any

from t10_mcp_advanced.mcp_server.tools.users.base import BaseUserServiceTool


class SearchUsersTool(BaseUserServiceTool):
    @property
    def name(self) -> str:
        return "search_users"

    @property
    def description(self) -> str:
        return "Search users by optional name, surname, email, or gender. Empty result means no match."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                key: {"type": "string"}
                for key in ("name", "surname", "email", "gender")
            },
            "additionalProperties": False,
        }

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await self.call_service("search_users", arguments, **arguments)
