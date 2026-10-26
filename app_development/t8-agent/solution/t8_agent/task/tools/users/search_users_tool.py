from typing import Any

from t8_agent.task.tools.users.base import BaseUserServiceTool


class SearchUsersTool(BaseUserServiceTool):

    @property
    def name(self) -> str:
        return "search_users"

    @property
    def description(self) -> str:
        return (
            "Searches users by any combination of name, surname, email, and gender. "
            "All filters are optional; omit a filter to not restrict by it."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "User first name"},
                "surname": {"type": "string", "description": "User last name"},
                "email": {"type": "string", "description": "User email"},
                "gender": {"type": "string", "description": "User gender, e.g. male or female"},
            },
            "required": [],
        }

    def execute(self, arguments: dict[str, Any]) -> str:
        try:
            return self._user_client.search_users(**arguments)
        except Exception as e:  # noqa: BLE001 - the user client raises bare Exception; tools must return errors
            return f"Error while searching users: {e!s}"
