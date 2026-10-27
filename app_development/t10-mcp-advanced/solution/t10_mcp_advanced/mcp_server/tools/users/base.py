import asyncio
from abc import ABC

from commons.user_service.client import UserServiceClient
from jsonschema import validate
from t10_mcp_advanced.mcp_server.tools.base import BaseTool


class BaseUserServiceTool(BaseTool, ABC):
    def __init__(self, user_client: UserServiceClient):
        super().__init__()
        self._user_client = user_client

    async def call_service(self, method, arguments, *values, **keywords):
        validate(arguments, self.input_schema)
        return await asyncio.to_thread(
            getattr(self._user_client, method), *values, **keywords
        )
