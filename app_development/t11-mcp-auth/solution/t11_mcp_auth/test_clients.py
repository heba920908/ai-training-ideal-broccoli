import asyncio
import secrets
import socket
from contextlib import asynccontextmanager
from secrets import token_urlsafe
from types import SimpleNamespace

import httpx2
import pytest
import uvicorn
from mcp.shared.exceptions import MCPError
from mcp.types import CallToolResult, TextContent
from t11_mcp_auth.agent.mcp_clients.api_key_mcp_client import ApiKeyMCPClient
from t11_mcp_auth.mcp_server import _server


@asynccontextmanager
async def serve(app):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical"))
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if task.done():
                    await task
                await asyncio.sleep(0.01)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        server.should_exit = True
        await task
        listener.close()


def test_authenticated_stateless_contract_and_header_replacement(monkeypatch):
    first_key, second_key = secrets.token_urlsafe(), secrets.token_urlsafe()
    requests = []

    class Directory:
        def get_user(self, user_id):
            return f"synthetic user {user_id}"

    monkeypatch.setattr(_server, "user_client", Directory())
    backend = _server.mcp.http_app(stateless_http=True)

    async def app(scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            requests.append(headers)
            assert headers.get(b"x-api-key") in {
                first_key.encode(),
                second_key.encode(),
            }
        await backend(scope, receive, send)

    async def scenario():
        async with serve(app) as url:
            wrapper = ApiKeyMCPClient(url, first_key)
            async with wrapper:
                original_client = wrapper.client
                original_http = wrapper._http_client
                tools = {
                    item["function"]["name"]: item["function"]
                    for item in await wrapper.get_tools()
                }
                assert set(tools) == {
                    "get_user_by_id",
                    "delete_user",
                    "search_user",
                    "add_user",
                    "update_user",
                }
                assert (
                    tools["get_user_by_id"]["parameters"]["properties"]["user_id"][
                        "type"
                    ]
                    == "integer"
                )
                assert tools["search_user"]["parameters"]["required"] == [
                    "search_user_request"
                ]
                assert tools["add_user"]["parameters"]["required"] == [
                    "user_create_model"
                ]
                assert tools["update_user"]["parameters"]["required"] == [
                    "user_id",
                    "user_update_model",
                ]
                original_http.headers["X-API-Key"] = second_key
                assert "synthetic user 42" in await wrapper.call_tool(
                    "get_user_by_id", {"user_id": 42}
                )
                assert wrapper.client is original_client
                assert wrapper._http_client is original_http
            assert original_http.is_closed
        assert [item[b"mcp-method"].decode() for item in requests] == [
            "server/discover",
            "tools/list",
            "tools/call",
        ]
        assert [item[b"x-api-key"] for item in requests] == [
            first_key.encode(),
            first_key.encode(),
            second_key.encode(),
        ]
        assert all(item[b"mcp-protocol-version"] == b"2026-07-28" for item in requests)
        assert all(b"mcp-session-id" not in item for item in requests)

    asyncio.run(scenario())


def test_user_service_calls_leave_the_event_loop(monkeypatch):
    import threading

    from commons.user_service.user_info import UserCreate, UserSearchRequest, UserUpdate

    main_thread = threading.get_ident()
    observed = []

    class Directory:
        def __getattr__(self, name):
            def invoke(*args, **kwargs):
                observed.append((name, threading.get_ident()))
                return "synthetic result"

            return invoke

    monkeypatch.setattr(_server, "user_client", Directory())

    async def scenario():
        assert await _server.get_user_by_id(42) == "synthetic result"
        assert await _server.delete_user(42) == "synthetic result"
        assert (
            await _server.search_user(
                UserSearchRequest(email="fixture@example.invalid")
            )
            == "synthetic result"
        )
        assert (
            await _server.add_user(
                UserCreate(
                    name="Synthetic",
                    surname="Fixture",
                    email="fixture@example.invalid",
                    about_me="Synthetic",
                )
            )
            == "synthetic result"
        )
        assert (
            await _server.update_user(42, UserUpdate(name="Updated"))
            == "synthetic result"
        )

    asyncio.run(scenario())
    assert [name for name, _ in observed] == [
        "get_user",
        "delete_user",
        "search_users",
        "add_user",
        "update_user",
    ]
    assert all(thread != main_thread for _, thread in observed)


def test_user_service_endpoint_can_be_isolated_from_t10(monkeypatch):
    import subprocess
    import sys

    monkeypatch.setenv("USER_SERVICE_URL", "http://127.0.0.1:8042")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from commons.user_service.client import USER_SERVICE_ENDPOINT; print(USER_SERVICE_ENDPOINT)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "http://127.0.0.1:8042"


@pytest.mark.parametrize("status", [200, 401, 403])
def test_oauth_refreshes_on_existing_connection_without_replay(monkeypatch, status):
    from t11_mcp_auth.agent.mcp_clients import _oauth_keycloak as oauth
    from t11_mcp_auth.agent.mcp_clients.oauth_mcp_client import OauthHttpMCPClient

    clock = [100.0]
    monkeypatch.setattr(oauth, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    first, replacement, refresh_token = [secrets.token_urlsafe() for _ in range(3)]
    refreshes = []
    requests = []
    status_holder = [200]

    async def refresh(token):
        assert token == refresh_token
        refreshes.append(token)
        await asyncio.sleep(0)
        return {"access_token": replacement, "expires_in": 60, "token_type": "Bearer"}

    async def authenticate(manager):
        manager._store_tokens(
            {
                "access_token": first,
                "refresh_token": refresh_token,
                "expires_in": 60,
                "token_type": "Bearer",
            }
        )

    monkeypatch.setattr(oauth.OAuthTokenManager, "authenticate", authenticate)
    monkeypatch.setattr(oauth, "_refresh_access_token", refresh)
    backend = _server.mcp.http_app(stateless_http=True)

    async def app(scope, receive, send):
        if scope["type"] == "http":
            requests.append(dict(scope["headers"]))
            if status_holder[0] != 200:
                from starlette.responses import Response

                await Response(status_code=status_holder[0])(scope, receive, send)
                return
        await backend(scope, receive, send)

    async def scenario():
        async with serve(app) as url:
            wrapper = OauthHttpMCPClient(url)
            async with wrapper:
                original_http, original_sdk = wrapper._http_client, wrapper.client
                await wrapper.get_tools()
                clock[0] = 131.0
                await asyncio.gather(wrapper.get_tools(), wrapper.get_tools())
                assert len(refreshes) == 1
                assert wrapper.client is original_sdk
                assert wrapper._http_client is original_http
                assert (
                    requests[-1][b"authorization"] == f"Bearer {replacement}".encode()
                )
                status_holder[0] = status
                if status != 200:
                    before = len(requests)
                    with pytest.raises(
                        MCPError, match="Server returned an error response"
                    ):
                        await wrapper.call_tool("get_user_by_id", {"user_id": 42})
                    assert len(requests) == before + 1
                    assert len(refreshes) == 1
            assert original_http.is_closed
        assert sum(item[b"mcp-method"] == b"server/discover" for item in requests) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("kind", ["api-key", "oauth"])
def test_failed_discovery_closes_owned_http_client(monkeypatch, kind):
    from t11_mcp_auth.agent.mcp_clients import oauth_mcp_client

    clients = []
    original = httpx2.AsyncClient

    def create(*args, **kwargs):
        client = original(*args, **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(httpx2, "AsyncClient", create)

    async def authenticate(manager):
        manager._store_tokens(
            {
                "access_token": token_urlsafe(),
                "expires_in": 60,
                "token_type": "Bearer",
            }
        )

    monkeypatch.setattr(
        oauth_mcp_client.OAuthTokenManager, "authenticate", authenticate
    )

    async def app(scope, receive, send):
        from starlette.responses import Response

        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                await send({"type": message["type"] + ".complete"})
                if message["type"] == "lifespan.shutdown":
                    return
        else:
            await Response(status_code=401)(scope, receive, send)

    async def scenario():
        async with serve(app) as url:
            wrapper = (
                ApiKeyMCPClient(url, secrets.token_urlsafe())
                if kind == "api-key"
                else oauth_mcp_client.OauthHttpMCPClient(url)
            )
            with pytest.raises(ExceptionGroup, match="unhandled errors in a TaskGroup"):
                async with wrapper:
                    pytest.fail("Unauthenticated discovery succeeded")
            assert clients and all(client.is_closed for client in clients)
            assert wrapper.client is None

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "content,is_error,expected",
    [
        ([], False, "(empty result)"),
        (
            [
                TextContent(type="text", text="first"),
                TextContent(type="text", text="second"),
            ],
            False,
            "first\nsecond",
        ),
        ([TextContent(type="text", text="denied")], True, "Tool error: denied"),
    ],
)
@pytest.mark.parametrize("kind", ["api-key", "oauth"])
def test_complete_results(kind, content, is_error, expected):
    from t11_mcp_auth.agent.mcp_clients.oauth_mcp_client import OauthHttpMCPClient

    class SDK:
        async def call_tool(self, name, arguments):
            return CallToolResult(content=content, is_error=is_error)

    async def scenario():
        wrapper = (
            ApiKeyMCPClient("http://unused", secrets.token_urlsafe())
            if kind == "api-key"
            else OauthHttpMCPClient("http://unused")
        )
        wrapper.client = SDK()
        if kind == "oauth":
            wrapper.token_manager._store_tokens(
                {
                    "access_token": token_urlsafe(),
                    "expires_in": 60,
                    "token_type": "Bearer",
                }
            )
            wrapper._http_client = httpx2.AsyncClient()
        try:
            assert await wrapper.call_tool("echo", {}) == expected
        finally:
            if wrapper._http_client is not None:
                await wrapper._http_client.aclose()

    asyncio.run(scenario())
