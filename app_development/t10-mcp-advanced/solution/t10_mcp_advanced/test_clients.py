import asyncio
import json
from contextlib import asynccontextmanager

import pytest
from aiohttp import web
from t10_mcp_advanced.agent.clients.custom_mcp_client import CustomMCPClient


@asynccontextmanager
async def remote(handler):
    app = web.Application()
    app.router.add_post("/mcp", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        await runner.cleanup()


@pytest.mark.parametrize("sse", [False, True])
def test_custom_client_roundtrip_metadata_and_split_sse(sse):
    async def scenario():
        async def handler(request):
            body = await request.json()
            assert request.headers["Mcp-Method"] == body["method"]
            assert request.headers["MCP-Protocol-Version"] == "2026-07-28"
            assert (
                body["params"]["_meta"]["io.modelcontextprotocol/clientCapabilities"]
                == {}
            )
            result = {"resultType": "complete"}
            if body["method"] == "server/discover":
                result["supportedVersions"] = ["2026-07-28"]
            elif body["method"] == "tools/list":
                result["tools"] = [
                    {
                        "name": "echo",
                        "description": "Echo",
                        "inputSchema": {"type": "object"},
                    }
                ]
            else:
                assert request.headers["Mcp-Name"] == "echo"
                result.update(
                    content=[
                        {"type": "text", "text": "first"},
                        {"type": "text", "text": "second"},
                    ],
                    isError=True,
                )
            payload = {"jsonrpc": "2.0", "id": body["id"], "result": result}
            if not sse:
                return web.json_response(payload)
            response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
            await response.prepare(request)
            data = (
                ': heartbeat\n\nevent: message\ndata: {"jsonrpc":"2.0","method":"notifications/progress"}\n\n'
                "event: message\ndata: " + json.dumps(payload) + "\n\n"
            ).encode()
            for offset in range(0, len(data), 7):
                await response.write(data[offset : offset + 7])
            await response.write_eof()
            return response

        async with remote(handler) as url:
            client = await CustomMCPClient.create(url)
            try:
                assert (await client.get_tools())[0]["function"]["parameters"] == {
                    "type": "object"
                }
                result = await client.call_tool("echo", {})
                assert "first" in result and "second" in result
                assert "error" in result.lower()
            finally:
                await client.close()
            assert client.http_session is None

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "kind,message",
    [
        ("rpc", "-32602"),
        ("id", "ID"),
        ("type", "resultType"),
        ("malformed_error", "Invalid MCP error"),
        ("malformed_result", "Invalid MCP result"),
    ],
)
def test_client_rejects_protocol_errors_and_unrelated_responses(kind, message):
    async def scenario():
        async def handler(request):
            body = await request.json()
            if kind == "malformed_error":
                return web.json_response(
                    {"jsonrpc": "2.0", "id": body["id"], "error": {"code": -32602}}
                )
            if kind == "malformed_result":
                return web.json_response(
                    {"jsonrpc": "2.0", "id": body["id"], "result": []}
                )
            if kind == "rpc":
                return web.json_response(
                    {
                        "jsonrpc": "2.0",
                        "id": body["id"],
                        "error": {"code": -32602, "message": "bad input"},
                    },
                    status=400,
                )
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": "wrong" if kind == "id" else body["id"],
                    "result": {
                        "resultType": "partial" if kind == "type" else "complete"
                    },
                }
            )

        async with remote(handler) as url:
            client = CustomMCPClient(url)
            with pytest.raises(RuntimeError, match=message):
                await client.connect()
            assert client.http_session is None

    asyncio.run(scenario())


def test_encoded_tool_headers_roundtrip():
    from t10_mcp_advanced.mcp_server.server import _decode_header_value

    for name in ["plain", "caf\u00e9", " leading", "=?base64?literal?="]:
        encoded = CustomMCPClient._encode_header_value(name)
        assert encoded.isascii()
        assert _decode_header_value(encoded) == name


@pytest.mark.parametrize("mode", ["sdk", "custom"])
def test_both_clients_execute_real_server_contract(mode, monkeypatch):
    import httpx
    from t10_mcp_advanced.agent.clients.mcp_client import MCPClient
    from t10_mcp_advanced.mcp_server import server
    from t10_mcp_advanced.test_server import Directory

    directory = Directory()
    for tool in server.mcp_server.tools.values():
        monkeypatch.setattr(tool, "_user_client", directory)

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app)
        ) as backend:

            async def handler(request):
                response = await backend.post(
                    "http://testserver/mcp",
                    content=await request.read(),
                    headers=dict(request.headers),
                )
                return web.Response(
                    body=response.content,
                    status=response.status_code,
                    headers={"Content-Type": response.headers["content-type"]},
                )

            async with remote(handler) as url:
                client_type = MCPClient if mode == "sdk" else CustomMCPClient
                client = await client_type.create(url)
                try:
                    assert len(await client.get_tools()) == 5
                    assert "42" in await client.call_tool(
                        "add_user",
                        {
                            "name": "Socket",
                            "surname": "Fixture",
                            "email": "socket@example.invalid",
                            "about_me": "Synthetic",
                        },
                    )
                    assert "socket@example.invalid" in await client.call_tool(
                        "get_user_by_id", {"id": 42}
                    )
                    assert "error" in (await client.call_tool("add_user", {})).lower()
                    assert "deleted" in await client.call_tool(
                        "delete_users", {"id": 42}
                    )
                finally:
                    await client.close()

    asyncio.run(scenario())
    assert not directory.users
