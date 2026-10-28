import asyncio
import json
import socket
from types import SimpleNamespace

import pytest
import pytest_asyncio
import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, ImageContent, TextContent
from t12_skills.custom.mcp.mcp_client import T12MCPClient
from t12_skills.custom.tools.py_interpreter._response import _ExecutionResult


@pytest_asyncio.fixture
async def interpreter_url():
    server = FastMCP("t12-contract", host="127.0.0.1")

    @server.tool()
    def execute_code(code: str, session_id: str = "") -> str:
        return json.dumps(
            {
                "success": True,
                "output": [code],
                "result": "42",
                "session_info": {"session_id": session_id or "contract-session"},
            }
        )

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    app = uvicorn.Server(uvicorn.Config(server.streamable_http_app(), log_level="critical"))
    task = asyncio.create_task(app.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(10):
            while not app.started:
                if task.done():
                    task.result()
                await asyncio.sleep(0.01)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        app.should_exit = True
        await task
        listener.close()


@pytest.mark.asyncio
async def test_stateful_socket_initializes_pings_discovers_and_preserves_session(
    interpreter_url,
):
    async with T12MCPClient(interpreter_url) as client:
        tools = await client.get_tools()
        assert [tool.name for tool in tools] == ["execute_code"]
        assert tools[0].parameters["required"] == ["code"]
        first = _ExecutionResult.model_validate_json(
            await client.call_tool("execute_code", {"code": "answer = 42"})
        )
        assert first.success and first.result == "42"
        assert first.session_info.session_id == "contract-session"
        second = _ExecutionResult.model_validate_json(
            await client.call_tool(
                "execute_code",
                {"code": "answer", "session_id": first.session_info.session_id},
            )
        )
        assert second.session_info.session_id == first.session_info.session_id
        assert second.output == ["answer"]
    assert client.session is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result",
    [
        CallToolResult(isError=True, content=[TextContent(type="text", text="provider internal")]),
        CallToolResult(content=[]),
        CallToolResult(
            content=[TextContent(type="text", text="one"), TextContent(type="text", text="two")]
        ),
        CallToolResult(content=[ImageContent(type="image", data="AA==", mimeType="image/png")]),
    ],
)
async def test_mcp_unusable_results_are_errors_not_success(result):
    async def call_tool(*args):
        return result

    client = T12MCPClient("http://127.0.0.1:1/mcp")
    client.session = SimpleNamespace(call_tool=call_tool)
    with pytest.raises(ValueError, match="MCP"):
        await client.call_tool("execute_code", {"code": "42"})


class Context:
    def __init__(self, value, events, name):
        self.value, self.events, self.name = value, events, name

    async def __aenter__(self):
        self.events.append("enter-" + self.name)
        return self.value

    async def __aexit__(self, *args):
        self.events.append("exit-" + self.name)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["initialize", "ping", "list", "missing", "cancel"])
async def test_partial_factory_failures_close_entered_contexts_in_reverse_order(
    monkeypatch, tmp_path, stage
):
    from t12_skills.custom.mcp import mcp_client
    from t12_skills.custom.tools.py_interpreter.python_code_interpreter_tool import (
        PythonCodeInterpreterTool,
    )

    events = []

    async def initialize():
        if stage == "initialize":
            raise RuntimeError("initialization failed")
        if stage == "cancel":
            raise asyncio.CancelledError()

    async def ping():
        if stage == "ping":
            raise RuntimeError("ping failed")

    async def list_tools():
        if stage == "list":
            raise RuntimeError("discovery failed")
        return SimpleNamespace(tools=[])

    session = SimpleNamespace(initialize=initialize, send_ping=ping, list_tools=list_tools)
    monkeypatch.setattr(
        mcp_client,
        "streamable_http_client",
        lambda *args, **kwargs: Context((None, None, None), events, "streams"),
    )
    monkeypatch.setattr(
        mcp_client, "ClientSession", lambda *args, **kwargs: Context(session, events, "session")
    )
    expected_error = asyncio.CancelledError if stage == "cancel" else Exception
    with pytest.raises(expected_error):
        await PythonCodeInterpreterTool.create("http://127.0.0.1:1/mcp", "execute_code", tmp_path)
    assert events == ["enter-streams", "enter-session", "exit-session", "exit-streams"]
