import asyncio
import importlib
import json
import secrets
from secrets import token_urlsafe
from types import SimpleNamespace

import httpx
import pytest
from commons.models.message import Message
from commons.models.role import Role
from openai import AsyncOpenAI
from t11_mcp_auth.agent import _agent


def config():
    return importlib.import_module("t11_mcp_auth.config")


def test_environment_nearest_ancestor_and_exports(tmp_path, monkeypatch):
    key = secrets.token_urlsafe()
    (tmp_path / ".env").write_text(f"MCP_API_KEY={key}\nOPENAI_MODEL=parent\n")
    nested = tmp_path / "nested"
    nested.mkdir()
    env = nested / ".env"
    env.write_text("OPENAI_MODEL=nearest\n")
    start = nested / "deep"
    start.mkdir()
    monkeypatch.setenv("OPENAI_MODEL", "exported")
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    assert config().load_environment(start) == env
    assert config().required("OPENAI_MODEL") == "exported"
    with pytest.raises(ValueError, match="MCP_API_KEY"):
        config().required("MCP_API_KEY")
    monkeypatch.setenv("MCP_API_KEY", "  ")
    with pytest.raises(ValueError, match="MCP_API_KEY"):
        config().required("MCP_API_KEY")
    monkeypatch.delenv("MCP_API_KEY")
    assert (
        config().load_environment(tmp_path / "absent" / "file.py") == tmp_path / ".env"
    )
    assert config().required("MCP_API_KEY") == key


@pytest.mark.parametrize(
    "url",
    [
        "http://dial.example/deployments/model",
        "https://api.openai.com/v1",
        "https://evil.api.openai.com/v1",
        "https://openai.com./v1",
        "https://user:password@dial.example/v1",
        "https://dial.example/v1?api_key=unsafe",
        "https://dial.example/v1#unsafe",
        "https:///v1",
    ],
)
def test_unsafe_provider_rejected(url, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    with pytest.raises(ValueError):
        _agent.AgentMCPAuth(secrets.token_urlsafe(), "configured", [], object())


def stream_response(content="done", arguments=None, call_id="call-1"):
    delta = {"content": content}
    if arguments is not None:
        delta = {
            "tool_calls": [
                {
                    "index": 0,
                    "id": call_id,
                    "type": "function",
                    "function": {"name": "search_user", "arguments": arguments},
                }
            ]
        }
    chunk = {
        "id": "chat-1",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "configured",
        "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
    }
    return httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        text=f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n",
    )


def install_transport(monkeypatch, handler):
    def factory(**kwargs):
        return AsyncOpenAI(
            **kwargs,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

    monkeypatch.setattr(_agent, "AsyncOpenAI", factory)


def test_dial_request_shape_and_separate_credentials(monkeypatch):
    dial_key, mcp_key = secrets.token_urlsafe(), secrets.token_urlsafe()
    monkeypatch.setenv("OPENAI_BASE_URL", "https://dial.example/deployments/custom")
    monkeypatch.setenv("MCP_API_KEY", mcp_key)
    requests = []

    def handler(request):
        requests.append(request)
        return stream_response()

    install_transport(monkeypatch, handler)

    async def scenario():
        agent = _agent.AgentMCPAuth(dial_key, "environment-model", [], object())
        try:
            result = await agent.get_completion([Message(Role.USER, "Hello")])
            assert result.content == "done"
            assert agent.openai.timeout == 90
            assert agent.openai.max_retries == 1
        finally:
            await agent.openai.close()

    asyncio.run(scenario())
    (request,) = requests
    body = json.loads(request.content)
    assert body == {
        "model": "environment-model",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True,
    }
    assert request.url.host == "dial.example"
    assert request.headers["Api-Key"] == dial_key
    assert mcp_key not in request.content.decode()
    assert mcp_key not in str(request.headers)


@pytest.mark.parametrize("arguments", ["{broken", "[]", "null", '"text"', "42"])
def test_invalid_tool_arguments_are_correlated(arguments, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://dial.example/v1")
    requests = []

    class Directory:
        async def call_tool(self, name, args):
            pytest.fail("Invalid arguments must not reach MCP")

    def handler(request):
        requests.append(json.loads(request.content))
        return (
            stream_response(arguments=arguments)
            if len(requests) == 1
            else stream_response()
        )

    install_transport(monkeypatch, handler)

    async def scenario():
        agent = _agent.AgentMCPAuth(secrets.token_urlsafe(), "custom", [], Directory())
        try:
            result = await agent.get_completion([Message(Role.USER, "Search")])
            assert result.content == "done"
        finally:
            await agent.openai.close()

    asyncio.run(scenario())
    tool = requests[1]["messages"][-1]
    assert tool["role"] == "tool"
    assert tool["tool_call_id"] == "call-1"
    assert "error" in tool["content"].lower()


@pytest.mark.parametrize("raises", [False, True])
def test_tool_credentials_never_reach_model_or_stdout(raises, monkeypatch, capsys):
    mcp_key, token = token_urlsafe(), token_urlsafe()
    monkeypatch.setenv("MCP_API_KEY", mcp_key)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://dial.example/v1")
    requests = []

    class Directory:
        api_key = mcp_key

        async def call_tool(self, name, args):
            assert name == "search_user"
            assert args == {"search_user_request": {"name": "Synthetic"}}
            if raises:
                raise RuntimeError(f"X-API-Key: {mcp_key}; Bearer {token}")
            return {
                "name": "Synthetic",
                "access_token": token,
                "detail": f"key={mcp_key}",
            }

    def handler(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return stream_response(
                arguments='{"search_user_request":{"name":"Synthetic"}}'
            )
        return stream_response()

    install_transport(monkeypatch, handler)

    async def scenario():
        agent = _agent.AgentMCPAuth(secrets.token_urlsafe(), "custom", [], Directory())
        try:
            await agent.get_completion([Message(Role.USER, "Search")])
        finally:
            await agent.openai.close()

    asyncio.run(scenario())
    recorded = json.dumps(requests) + capsys.readouterr().out
    assert mcp_key not in recorded
    assert token not in recorded
    assert requests[1]["messages"][-1]["tool_call_id"] == "call-1"


def test_round_bound(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://dial.example/v1")
    requests, calls = [], []

    class Directory:
        async def call_tool(self, name, args):
            calls.append((name, args))
            return "ok"

    def handler(request):
        requests.append(json.loads(request.content))
        if len(requests) > 10:
            pytest.fail("Model round bound exceeded")
        return stream_response(arguments='{"search_user_request":{}}')

    install_transport(monkeypatch, handler)

    async def scenario():
        agent = _agent.AgentMCPAuth(secrets.token_urlsafe(), "custom", [], Directory())
        try:
            with pytest.raises(RuntimeError, match="limit"):
                await agent.get_completion([Message(Role.USER, "Search")])
        finally:
            await agent.openai.close()

    asyncio.run(scenario())
    assert len(requests) == 10
    assert len(calls) <= 10


def test_interleaved_function_name_and_argument_fragments():
    agent = object.__new__(_agent.AgentMCPAuth)

    def delta(index, name, arguments, identifier=None):
        return SimpleNamespace(
            index=index,
            id=identifier,
            type="function" if identifier else None,
            function=SimpleNamespace(name=name, arguments=arguments),
        )

    result = agent._collect_tool_calls(
        [
            delta(0, "search_", '{"search_user_', "search-call"),
            delta(1, "get_user_", '{"user_', "get-call"),
            delta(0, "user", 'request":{}}'),
            delta(1, "by_id", 'id":42}'),
        ]
    )
    assert result == [
        {
            "id": "search-call",
            "type": "function",
            "function": {
                "name": "search_user",
                "arguments": '{"search_user_request":{}}',
            },
        },
        {
            "id": "get-call",
            "type": "function",
            "function": {"name": "get_user_by_id", "arguments": '{"user_id":42}'},
        },
    ]


def test_fragmented_tool_calls_and_oauth_secret_separation(monkeypatch):
    access, refresh = secrets.token_urlsafe(), secrets.token_urlsafe()
    monkeypatch.setenv("OPENAI_BASE_URL", "https://dial.example/v1")
    requests, calls = [], []

    class Directory:
        token_manager = SimpleNamespace(_access_token=access, _refresh_token=refresh)

        async def call_tool(self, name, args):
            calls.append((name, args))
            return f"credential echo: {access} {refresh}"

    def handler(request):
        requests.append(json.loads(request.content))
        if len(requests) > 1:
            return stream_response()
        first = stream_response(arguments='{"search_user_').text.split("data: [DONE]")[
            0
        ]
        second = {
            "id": "chat-1",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "custom",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "function": {"arguments": 'request":{}}'}}
                        ]
                    },
                }
            ],
        }
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=first + f"data: {json.dumps(second)}\n\ndata: [DONE]\n\n",
        )

    install_transport(monkeypatch, handler)

    async def scenario():
        agent = _agent.AgentMCPAuth(secrets.token_urlsafe(), "custom", [], Directory())
        try:
            await agent.get_completion([Message(Role.USER, "Search")])
        finally:
            await agent.openai.close()

    asyncio.run(scenario())
    assert calls == [("search_user", {"search_user_request": {}})]
    assert requests[1]["messages"][-1]["tool_call_id"] == "call-1"
    assert access not in json.dumps(requests)
    assert refresh not in json.dumps(requests)


def test_environment_not_found_and_sanitized_required(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.is_file", lambda path: False)
    assert config().load_environment(tmp_path) is None
    key = secrets.token_urlsafe()
    monkeypatch.setenv("MCP_API_KEY", "  ")
    with pytest.raises(ValueError) as error:
        config().required("MCP_API_KEY")
    assert key not in str(error.value)


def test_t11_agent_imports_without_t9_or_shared_provider_constants(monkeypatch):
    import builtins

    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.startswith("t9_") or name == "commons.constants":
            pytest.fail("T11 must not import T9 or fixed provider settings")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    importlib.reload(_agent)
    importlib.reload(importlib.import_module("t11_mcp_auth.agent.app"))


def test_provider_failure_is_generic(monkeypatch, capsys):
    key = secrets.token_urlsafe()
    monkeypatch.setenv("OPENAI_BASE_URL", "https://dial.example/v1")
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(500, json={"error": {"message": key}})

    install_transport(monkeypatch, handler)

    async def scenario():
        agent = _agent.AgentMCPAuth(key, "custom", [], object())
        try:
            with pytest.raises(RuntimeError) as error:
                await agent.get_completion([Message(Role.USER, "Hi")])
            assert key not in str(error.value)
        finally:
            await agent.openai.close()

    asyncio.run(scenario())
    assert len(requests) == 2
    assert key not in capsys.readouterr().out


def test_recursive_capture_redaction():
    key, token, password = [secrets.token_urlsafe() for _ in range(3)]
    payload = {
        "headers": {"Authorization": f"Bearer {token}", "X-API-Key": key},
        "items": [
            {
                "access_token": token,
                "refresh_token": token,
                "password": password,
                "code": key,
                "code_verifier": key,
                "error_description": password,
            }
        ],
        "text": f"prefix-{key}-suffix Authorization: Bearer {token}",
        "callback": f"http://127.0.0.1/callback?code={key}&state={token}",
        "safe": "Synthetic user",
    }
    result = config().redact(payload, secrets=(key,))
    serialized = json.dumps(result)
    assert all(value not in serialized for value in (key, token, password))
    assert result["safe"] == "Synthetic user"
    assert payload["items"][0]["password"] == password


@pytest.mark.parametrize(
    "template",
    [
        "headers={'X-API-Key': '%s'}",
        'headers={"Api-Key": "%s"}',
        'token endpoint: {"error_description": "rejected %s"}',
        "callback?code=%s&state=unused",
        "Authorization: Bearer %s",
    ],
)
def test_capture_scrubs_embedded_header_and_token_error_text(template):
    key = secrets.token_urlsafe()
    assert key not in config().redact(template % key)


@pytest.mark.parametrize("mode", ["api-key", "oauth"])
def test_cli_single_query_capture(mode, tmp_path, monkeypatch, capsys):
    from t11_mcp_auth.agent import app

    key = secrets.token_urlsafe()
    for name, value in {
        "OPENAI_API_KEY": key,
        "OPENAI_MODEL": "configured",
        "OPENAI_BASE_URL": "https://dial.example/v1",
        "MCP_API_KEY": key,
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(app, "load_environment", lambda: None)
    chosen, closed = [], []

    class Client:
        def __init__(self, mcp_server_url, api_key=None):
            chosen.append((mcp_server_url, api_key))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            closed.append(True)

        async def get_tools(self):
            return []

    class Agent:
        def __init__(self, **kwargs):
            self.openai = self

        async def close(self):
            closed.append(True)

        async def get_completion(self, messages):
            return Message(Role.ASSISTANT, f"Synthetic {key}")

    monkeypatch.setattr(app, "ApiKeyMCPClient", Client)
    monkeypatch.setattr(app, "OauthHttpMCPClient", Client)
    monkeypatch.setattr(app, "AgentMCPAuth", Agent)
    assert (
        asyncio.run(
            app.main(
                ["--auth", mode, "--query", "Search", "--output-dir", str(tmp_path)]
            )
        )
        == 0
    )
    (capture,) = tmp_path.glob("*.json")
    data = json.loads(capture.read_text())
    assert data["auth"] == mode
    assert data["query"] == "Search"
    assert data["messages"][-1]["role"] == "assistant"
    assert data["result"] == "Synthetic <redacted>"
    assert key not in capture.read_text() + capsys.readouterr().out
    assert chosen == [
        (
            f"http://127.0.0.1:{8007 if mode == 'api-key' else 8008}/mcp",
            key if mode == "api-key" else None,
        )
    ]
    assert len(closed) == 2


def test_cli_oauth_capture_removes_manager_tokens(tmp_path, monkeypatch, capsys):
    from t11_mcp_auth.agent import app

    access, refresh, dial = [secrets.token_urlsafe() for _ in range(3)]
    for name, value in {
        "OPENAI_API_KEY": dial,
        "OPENAI_MODEL": "configured",
        "OPENAI_BASE_URL": "https://dial.example/v1",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.setattr(app, "load_environment", lambda: None)

    class Client:
        token_manager = SimpleNamespace(_access_token=access, _refresh_token=refresh)

        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get_tools(self):
            return []

    class Agent:
        def __init__(self, **kwargs):
            self.openai = self

        async def close(self):
            pass

        async def get_completion(self, messages):
            return Message(Role.ASSISTANT, f"Synthetic {access} {refresh}")

    monkeypatch.setattr(app, "OauthHttpMCPClient", Client)
    monkeypatch.setattr(app, "AgentMCPAuth", Agent)
    assert (
        asyncio.run(
            app.main(
                ["--auth", "oauth", "--query", "Search", "--output-dir", str(tmp_path)]
            )
        )
        == 0
    )
    output = (tmp_path / "agent_oauth.json").read_text() + capsys.readouterr().out
    assert access not in output
    assert refresh not in output


def test_cli_interactive_retains_history(monkeypatch, capsys):
    from t11_mcp_auth.agent import app

    for name, value in {
        "OPENAI_API_KEY": token_urlsafe(),
        "OPENAI_MODEL": "custom",
        "OPENAI_BASE_URL": "https://dial.example/v1",
        "MCP_API_KEY": token_urlsafe(),
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(app, "load_environment", lambda: None)
    queries, history = iter(["", "first", "second", "QUIT"]), []
    monkeypatch.setattr("builtins.input", lambda prompt: next(queries))

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get_tools(self):
            return []

    class Agent:
        def __init__(self, **kwargs):
            self.openai = self

        async def close(self):
            pass

        async def get_completion(self, messages):
            history.append([message.to_dict() for message in messages])
            return Message(Role.ASSISTANT, "Synthetic answer")

    monkeypatch.setattr(app, "ApiKeyMCPClient", Client)
    monkeypatch.setattr(app, "AgentMCPAuth", Agent)
    assert asyncio.run(app.main([])) == 0
    assert [message["content"] for message in history[1][1:]] == [
        "first",
        "Synthetic answer",
        "second",
    ]
    assert capsys.readouterr().out.count("Synthetic answer") == 2


@pytest.mark.parametrize("stop", ["exit", "quit", "eof"])
def test_cli_interactive_exit(stop, monkeypatch):
    from t11_mcp_auth.agent import app

    monkeypatch.setattr(app, "load_environment", lambda: None)
    for name, value in {
        "OPENAI_API_KEY": token_urlsafe(),
        "OPENAI_MODEL": "custom",
        "OPENAI_BASE_URL": "https://dial.example/v1",
        "MCP_API_KEY": token_urlsafe(),
    }.items():
        monkeypatch.setenv(name, value)

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get_tools(self):
            return []

    def read_input(prompt):
        if stop == "eof":
            raise EOFError
        return stop

    monkeypatch.setattr(app, "ApiKeyMCPClient", Client)
    monkeypatch.setattr("builtins.input", read_input)
    assert asyncio.run(app.main([])) == 0


def test_cli_errors_are_generic_nonzero(monkeypatch, capsys):
    from t11_mcp_auth.agent import app

    key = secrets.token_urlsafe()

    def fail():
        raise ValueError(f"configuration {key}")

    monkeypatch.setattr(app, "load_environment", fail)
    assert asyncio.run(app.main(["--query", "Search"])) == 1
    captured = capsys.readouterr()
    assert key not in captured.out + captured.err
