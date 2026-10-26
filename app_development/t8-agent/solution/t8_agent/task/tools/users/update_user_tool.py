from typing import Any

from commons.user_service.user_info import UserUpdate
from t8_agent.task.tools.users.base import BaseUserServiceTool


class UpdateUserTool(BaseUserServiceTool):

    @property
    def name(self) -> str:
        return "update_user"

    @property
    def description(self) -> str:
        return "Updates an existing user by numeric ID. Only the fields provided in new_info are changed."

    @property
    def input_schema(self) -> dict[str, Any]:
        new_info = UserUpdate.model_json_schema()
        # "#/$defs/..." refs resolve from the root, so nested $defs must be hoisted
        defs = new_info.pop("$defs", None)
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "id": {"type": "number", "description": "User ID that should be updated."},
                "new_info": new_info,
            },
            "required": ["id", "new_info"],
        }
        if defs:
            schema["$defs"] = defs
        return schema

    def execute(self, arguments: dict[str, Any]) -> str:
        try:
            user_id = int(arguments["id"])
            new_info = UserUpdate.model_validate(arguments["new_info"])
            return self._user_client.update_user(user_id, new_info)
        except Exception as e:  # noqa: BLE001 - the user client raises bare Exception; tools must return errors
            return f"Error while updating user: {e!s}"
