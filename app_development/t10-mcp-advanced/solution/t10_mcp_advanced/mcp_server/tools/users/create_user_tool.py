from typing import Any

from commons.user_service.user_info import UserCreate
from t10_mcp_advanced.mcp_server.tools.users.base import BaseUserServiceTool


class CreateUserTool(BaseUserServiceTool):
    @property
    def name(self) -> str:
        return "add_user"

    @property
    def description(self) -> str:
        return "Create a user from supplied details. Do not invent private contact information."

    @property
    def input_schema(self) -> dict[str, Any]:
        return UserCreate.model_json_schema()

    async def execute(self, arguments: dict[str, Any]) -> str:
        model = UserCreate.model_validate(arguments)
        return await self.call_service("add_user", arguments, model)
