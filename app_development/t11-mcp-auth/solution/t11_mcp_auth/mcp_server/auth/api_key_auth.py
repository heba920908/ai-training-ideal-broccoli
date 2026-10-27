import hmac
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, api_key: str | None = None):
        super().__init__(app)
        key = os.environ.get("MCP_API_KEY") if api_key is None else api_key
        if not isinstance(key, str) or not key.strip():
            raise ValueError("MCP_API_KEY must be configured and nonempty")
        self.api_key = key.encode("utf-8")

    async def dispatch(self, request: Request, call_next):
        supplied = request.headers.get("X-API-Key", "").encode("utf-8")
        if not supplied or not hmac.compare_digest(supplied, self.api_key):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)
