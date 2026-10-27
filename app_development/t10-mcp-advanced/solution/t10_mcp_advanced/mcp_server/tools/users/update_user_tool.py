from typing import Any

from commons.user_service.user_info import UserUpdate
from t10_mcp_advanced.mcp_server.tools.users.base import BaseUserServiceTool


class UpdateUserTool(BaseUserServiceTool):
    @property
    def name(self) -> str:
        return "update_user"

    @property
    def description(self) -> str:
        return "Update a user by ID with new_info."

    @property
    def input_schema(self) -> dict[str, Any]:
        schema = UserUpdate.model_json_schema()
        definitions = schema.pop("$defs", {})
        return {
            "type": "object",
            "properties": {"id": {"type": "integer"}, "new_info": schema},
            "required": ["id", "new_info"],
            "$defs": definitions,
            "additionalProperties": False,
        }

    async def execute(self, arguments: dict[str, Any]) -> str:
        model = UserUpdate.model_validate(arguments["new_info"])
        return await self.call_service("update_user", arguments, arguments["id"], model)
