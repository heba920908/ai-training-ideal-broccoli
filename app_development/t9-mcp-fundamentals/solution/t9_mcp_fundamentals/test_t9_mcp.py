from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from t9_mcp_fundamentals.agent.mcp_clients.http import HttpMCPClient


@pytest.mark.asyncio
async def test_tool_schemas_preserve_server_parameters():
    client = HttpMCPClient("http://127.0.0.1:8005/mcp")
    schema = {"type": "object", "properties": {"user_id": {"type": "integer"}}}
    client.client = SimpleNamespace(
        list_tools=AsyncMock(
            return_value=SimpleNamespace(
                tools=[
                    SimpleNamespace(
                        name="get_user_by_id",
                        description="Get a user",
                        input_schema=schema,
                    )
                ],
                next_cursor=None,
            )
        )
    )
    assert await client.get_tools() == [
        {
            "type": "function",
            "function": {
                "name": "get_user_by_id",
                "description": "Get a user",
                "parameters": schema,
            },
        }
    ]


@pytest.mark.asyncio
async def test_tool_results_include_all_blocks_and_errors():
    from mcp.types import CallToolResult, TextContent

    client = HttpMCPClient("http://localhost:8005/mcp")
    client.client = SimpleNamespace(
        call_tool=AsyncMock(
            return_value=CallToolResult(
                content=[
                    TextContent(type="text", text="one"),
                    TextContent(type="text", text="two"),
                ],
            )
        )
    )
    assert await client.call_tool("search_user", {}) == "one\ntwo"
    client.client.call_tool.return_value = CallToolResult(
        content=[TextContent(type="text", text="not found")],
        is_error=True,
    )
    with pytest.raises(RuntimeError, match="not found"):
        await client.call_tool("get_user_by_id", {"user_id": 999})


@pytest.mark.asyncio
async def test_resources_prompts_and_unsupported_capabilities():
    from mcp.types import TextContent, TextResourceContents

    client = HttpMCPClient("http://localhost:8005/mcp")
    client.client = SimpleNamespace(
        list_resources=AsyncMock(side_effect=RuntimeError("unsupported")),
        list_prompts=AsyncMock(side_effect=RuntimeError("unsupported")),
        read_resource=AsyncMock(
            return_value=SimpleNamespace(
                contents=[
                    TextResourceContents(uri="test://text", text="resource"),
                ]
            )
        ),
        get_prompt=AsyncMock(
            return_value=SimpleNamespace(
                messages=[
                    SimpleNamespace(content=TextContent(type="text", text="first")),
                    SimpleNamespace(content=TextContent(type="text", text="second")),
                ]
            )
        ),
    )
    assert await client.get_resources() == []
    assert await client.get_prompts() == []
    assert await client.get_resource("test://text") == "resource"
    assert await client.get_prompt("search") == "first\nsecond"


@pytest.mark.asyncio
async def test_http_connection_and_cleanup(monkeypatch):
    from t9_mcp_fundamentals.agent.mcp_clients import http

    sdk = SimpleNamespace(
        __aenter__=AsyncMock(),
        __aexit__=AsyncMock(),
        server_info="test",
        protocol_version="test",
        server_capabilities=SimpleNamespace(model_dump_json=lambda **kwargs: "{}"),
    )
    factory = Mock(return_value=sdk)
    monkeypatch.setattr(http, "Client", factory)
    client = HttpMCPClient("http://localhost:8005/mcp")
    async with client as connected:
        assert connected is client
        assert client.client is sdk
    assert client.client is None
    sdk.__aexit__.assert_awaited_once()


def test_stdio_uses_podman_without_a_tty():
    from t9_mcp_fundamentals.agent.mcp_clients.stdio import StdioMCPClient

    params = StdioMCPClient(
        docker_image="docker.io/mcp/duckduckgo:latest"
    )._build_server_params()
    assert params.command == "podman"
    assert params.args == ["run", "--rm", "-i", "docker.io/mcp/duckduckgo:latest"]
    local = StdioMCPClient(
        command="python", args=["server.py"], env={"PYTHONPATH": "/tmp"}
    )
    assert local._build_server_params().env == {"PYTHONPATH": "/tmp"}


@pytest.mark.asyncio
async def test_server_exposes_tools_resource_and_prompts(monkeypatch):
    from fastmcp import Client
    from t9_mcp_fundamentals.mcp_server import _server

    monkeypatch.setattr(
        _server.user_service, "get_user", lambda user_id: f"user {user_id}"
    )
    async with Client(_server.mcp) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == {
            "get_user_by_id",
            "delete_user",
            "search_user",
            "add_user",
            "update_user",
        }
        result = await client.call_tool("get_user_by_id", {"user_id": 7})
        assert result.content[0].text == "user 7"
        resources = await client.list_resources()
        assert str(resources[0].uri) == "users-management://flow-diagram"
        resource = await client.read_resource("users-management://flow-diagram")
        assert resource[0].mime_type == "image/png"
        assert {prompt.name for prompt in await client.list_prompts()} == {
            "search_guidance",
            "creation_guidance",
        }
        prompt = await client.get_prompt("search_guidance")
        assert "Search" in prompt.messages[0].content.text


@pytest.mark.asyncio
async def test_agent_routes_tools_and_returns_argument_errors(monkeypatch):
    from commons.models.message import Message
    from commons.models.role import Role
    from t9_mcp_fundamentals.agent.agent import AgentMCPFundamentals

    users = SimpleNamespace(call_tool=AsyncMock(return_value="created"))
    search = SimpleNamespace(call_tool=AsyncMock(return_value="found"))
    agent = AgentMCPFundamentals(
        "test-key",
        "test-model",
        [],
        users,
        tool_clients={"add_user": users, "web_search": search},
        base_url="https://ai-proxy.lab.epam.com/openai/deployments/test",
    )
    calls = [
        {
            "id": "1",
            "function": {"name": "web_search", "arguments": '{"query":"person"}'},
        },
        {"id": "2", "function": {"name": "add_user", "arguments": "not JSON"}},
        {"id": "3", "function": {"name": "missing", "arguments": "{}"}},
    ]
    messages = []
    await agent._call_tools(Message(Role.ASSISTANT, "", tool_calls=calls), messages)
    assert [message.tool_call_id for message in messages] == ["1", "2", "3"]
    assert messages[0].content == "found"
    assert all("Error" in message.content for message in messages[1:])
    search.call_tool.assert_awaited_once_with("web_search", {"query": "person"})
    users.call_tool.assert_not_awaited()
    await agent.openai.close()


@pytest.mark.asyncio
async def test_app_discovery_needs_no_llm_and_closes_clients(monkeypatch):
    from t9_mcp_fundamentals.agent import app

    client = SimpleNamespace(
        get_tools=AsyncMock(
            return_value=[
                {
                    "type": "function",
                    "function": {
                        "name": "search_user",
                        "parameters": {},
                        "description": "search",
                    },
                }
            ]
        ),
        get_resources=AsyncMock(return_value=[]),
        get_prompts=AsyncMock(return_value=[]),
    )

    class Connection:
        async def __aenter__(self):
            return client

        async def __aexit__(self, *args):
            client.closed = True

    monkeypatch.setattr(app, "HttpMCPClient", lambda **kwargs: Connection())
    await app.main(["--discover-only"])
    assert client.closed


@pytest.mark.asyncio
async def test_app_rejects_duplicate_tool_names(monkeypatch):
    from t9_mcp_fundamentals.agent import app

    client = SimpleNamespace(
        get_tools=AsyncMock(
            return_value=[
                {
                    "type": "function",
                    "function": {
                        "name": "same",
                        "parameters": {},
                        "description": "",
                    },
                }
            ]
        ),
        get_resources=AsyncMock(return_value=[]),
        get_prompts=AsyncMock(return_value=[]),
    )

    class Connection:
        async def __aenter__(self):
            return client

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(app, "HttpMCPClient", lambda **kwargs: Connection())
    with pytest.raises(ValueError, match="Duplicate tool"):
        await app.main(
            [
                "--server-url",
                "http://first/mcp",
                "--server-url",
                "http://second/mcp",
                "--discover-only",
            ]
        )


@pytest.mark.asyncio
async def test_agent_stream_ignores_empty_chunks_and_model_specific_parameters():
    from commons.models.message import Message
    from commons.models.role import Role
    from t9_mcp_fundamentals.agent.agent import AgentMCPFundamentals

    agent = AgentMCPFundamentals(
        "test-key",
        "test-model",
        [],
        SimpleNamespace(),
        base_url="https://ai-proxy.lab.epam.com/openai/deployments/test",
    )

    async def chunks():
        yield SimpleNamespace(choices=[])
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(delta=SimpleNamespace(content="hello", tool_calls=None))
            ]
        )

    agent.openai.chat.completions.create = AsyncMock(return_value=chunks())
    result = await agent.get_response([Message(Role.USER, "hi")])
    assert result.content == "hello"
    kwargs = agent.openai.chat.completions.create.call_args.kwargs
    assert "reasoning_effort" not in kwargs
    assert "temperature" not in kwargs
    assert "tools" not in kwargs
    await agent.openai.close()


@pytest.mark.asyncio
async def test_pagination_collects_all_tools():
    client = HttpMCPClient("http://localhost:8005/mcp")

    def page(name, cursor):
        return SimpleNamespace(
            tools=[SimpleNamespace(name=name, description=None, input_schema={})],
            next_cursor=cursor,
        )

    client.client = SimpleNamespace(
        list_tools=AsyncMock(side_effect=[page("first", "next"), page("second", None)])
    )
    assert [tool["function"]["name"] for tool in await client.get_tools()] == [
        "first",
        "second",
    ]
    client.client.list_tools.assert_any_await(cursor="next")


@pytest.mark.asyncio
async def test_disconnected_client_rejects_calls():
    client = HttpMCPClient("http://localhost:8005/mcp")
    for operation in [
        client.get_tools(),
        client.get_resources(),
        client.get_prompts(),
        client.get_prompt("search"),
        client.get_resource("test://resource"),
        client.call_tool("search", {}),
    ]:
        with pytest.raises(RuntimeError, match="not connected"):
            await operation


@pytest.mark.asyncio
async def test_all_server_tools_delegate_validated_models(monkeypatch):
    from fastmcp import Client
    from t9_mcp_fundamentals.mcp_server import _server

    service = _server.user_service
    search = Mock(return_value="found")
    create = Mock(return_value="created")
    update = Mock(return_value="updated")
    delete = Mock(return_value="deleted")
    monkeypatch.setattr(service, "search_users", search)
    monkeypatch.setattr(service, "add_user", create)
    monkeypatch.setattr(service, "update_user", update)
    monkeypatch.setattr(service, "delete_user", delete)
    async with Client(_server.mcp) as client:
        await client.call_tool("search_user", {"request": {"name": "Training"}})
        await client.call_tool(
            "add_user",
            {
                "user": {
                    "name": "Training",
                    "surname": "Example",
                    "email": "test@example.com",
                    "about_me": "Test",
                }
            },
        )
        await client.call_tool(
            "update_user", {"user_id": 7, "user": {"company": "Test"}}
        )
        await client.call_tool("delete_user", {"user_id": 7})
    search.assert_called_once_with(name="Training")
    assert create.call_args.args[0].email == "test@example.com"
    assert update.call_args.args[0] == 7
    assert update.call_args.args[1].company == "Test"
    delete.assert_called_once_with(7)


@pytest.mark.asyncio
async def test_tool_round_limit_preserves_complete_tool_messages(capsys):
    from commons.models.message import Message
    from commons.models.role import Role
    from t9_mcp_fundamentals.agent.agent import AgentMCPFundamentals

    client = SimpleNamespace(call_tool=AsyncMock(return_value="found"))
    tools = [{"function": {"name": "search_user"}}]
    agent = AgentMCPFundamentals(
        "test-key",
        "test",
        tools,
        client,
        base_url="https://ai-proxy.lab.epam.com/openai/deployments/test",
        max_tool_rounds=1,
    )
    call = {"id": "1", "function": {"name": "search_user", "arguments": "{}"}}
    agent._stream_response = AsyncMock(
        return_value=Message(Role.ASSISTANT, "", tool_calls=[call])
    )
    messages = [Message(Role.USER, "search")]
    response = await agent.get_response(messages)
    assert "limit" in response.content
    assert response.content in capsys.readouterr().out
    assert [message.role for message in messages] == [
        Role.USER,
        Role.ASSISTANT,
        Role.TOOL,
    ]
    await agent.openai.close()


def test_tool_delta_fragments_are_joined():
    from t9_mcp_fundamentals.agent.agent import AgentMCPFundamentals

    deltas = [
        SimpleNamespace(
            index=0,
            id="call",
            type="function",
            function=SimpleNamespace(name="search", arguments='{"query":'),
        ),
        SimpleNamespace(
            index=0,
            id=None,
            type=None,
            function=SimpleNamespace(name=None, arguments='"test"}'),
        ),
    ]
    result = AgentMCPFundamentals._collect_tool_calls(None, deltas)
    assert result == [
        {
            "id": "call",
            "type": "function",
            "function": {"name": "search", "arguments": '{"query":"test"}'},
        }
    ]
