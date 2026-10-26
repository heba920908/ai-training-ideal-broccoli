from typing import Any

from t8_agent.task.tools.users.base import BaseUserServiceTool


class DeleteUserTool(BaseUserServiceTool):

    @property
    def name(self) -> str:
        return "delete_users"

    @property
    def description(self) -> str:
        return "Permanently deletes a single user by numeric user ID. Irreversible."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "id": {"type": "number", "description": "ID of the user to delete"},
            },
            "required": ["id"],
        }

    def execute(self, arguments: dict[str, Any]) -> str:
        try:
            user_id = int(arguments["id"])
            return self._user_client.delete_user(user_id)
        except Exception as e:  # noqa: BLE001 - the user client raises bare Exception; tools must return errors
            return f"Error while deleting user by id: {e!s}"