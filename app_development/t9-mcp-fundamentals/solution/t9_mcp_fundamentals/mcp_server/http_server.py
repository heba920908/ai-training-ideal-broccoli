from t9_mcp_fundamentals.mcp_server._server import mcp

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8005,
        # Don't create sessions even for legacy clients that start with `initialize`.
        # Modern (2026-07-28) clients are stateless anyway: every request carries its protocol version in `_meta`
        stateless_http=True,
    )
