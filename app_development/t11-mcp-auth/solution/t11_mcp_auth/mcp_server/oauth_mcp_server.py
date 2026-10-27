import os

import uvicorn
from t11_mcp_auth.config import load_environment
from t11_mcp_auth.mcp_server.auth.oauth import JWTAuthMiddleware


def create_app():
    load_environment()
    os.environ.setdefault("USER_SERVICE_URL", "http://127.0.0.1:8042")
    from t11_mcp_auth.mcp_server._server import mcp

    application = mcp.http_app(stateless_http=True)
    application.add_middleware(JWTAuthMiddleware)
    return application


app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8008, log_level="info")
