import os

import uvicorn
from t11_mcp_auth.config import load_environment, required
from t11_mcp_auth.mcp_server.auth.api_key_auth import APIKeyMiddleware


def create_app():
    load_environment()
    os.environ.setdefault("USER_SERVICE_URL", "http://127.0.0.1:8042")
    from t11_mcp_auth.mcp_server._server import mcp

    application = mcp.http_app(stateless_http=True)
    application.add_middleware(APIKeyMiddleware, api_key=required("MCP_API_KEY"))
    return application


app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8007, log_level="info")
