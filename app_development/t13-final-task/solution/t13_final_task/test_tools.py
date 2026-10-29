import os
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from mcp.types import TextContent
from t13_final_task.task.agent.clients import http_mcp_client, stdio_mcp_client
from t13_final_task.task.agent.models import McpToolModel, Role
from t13_final_task.task.agent.tools.mcp_tool import McpTool
from t13_final_task.task.agent.tools.read_skill_tool import ReadSkillTool


@pytest.fixture
def skills(tmp_path):
    root = tmp_path / "skills"
    (root / "demo").mkdir(parents=True)
    (root / "demo" / "SKILL.md").write_text("demo skill", encoding="utf-8")
    (root / "demo" / "bad.bin").write_bytes(b"\xff\xfe\x00")
    (tmp_path / "secret.txt").write_text("TOP-SECRET-CONTENT", encoding="utf-8")
    os.symlink(tmp_path / "secret.txt", root / "demo" / "link.txt")
    return root


@pytest.mark.parametrize("path", ["/demo/SKILL.md", "demo/SKILL.md"])
async def test_read_skill_valid_paths(skills, path):
    message = await ReadSkillTool(skills).execute("call-1", {"path": path})
    assert message.content == "demo skill"
    assert message.tool_call_id == "call-1"
    assert message.role == Role.TOOL


@pytest.mark.parametrize(
    "path",
    ["/../secret.txt", "demo/../../secret.txt", "/demo/link.txt", "/demo", "/demo/missing.md"],
)
async def test_read_skill_refuses_escape_and_non_files(skills, tmp_path, path):
    message = await ReadSkillTool(skills).execute("call-2", {"path": path})
    assert "TOP-SECRET-CONTENT" not in message.content
    assert message.content.startswith("ERROR")
    assert message.tool_call_id == "call-2"


async def test_read_skill_absolute_outside_path(skills, tmp_path):
    message = await ReadSkillTool(skills).execute("c", {"path": str(tmp_path / "secret.txt")})
    assert "TOP-SECRET-CONTENT" not in message.content
    assert message.content.startswith("ERROR")


async def test_read_skill_non_utf8(skills):
    message = await ReadSkillTool(skills).execute("c", {"path": "/demo/bad.bin"})
    assert message.content.startswith("ERROR")


class FakeClient:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        if self.error:
            raise self.error
        return self.result


def mcp_tool(client):
    return McpTool(client, McpToolModel("search_user", "Search", {"type": "object"}))


async def test_mcp_tool_delegates_and_exposes_schema():
    client = FakeClient(result="found")
    tool = mcp_tool(client)
    message = await tool.execute("id-1", {"search_user_request": {"surname": "Smith"}})
    assert client.calls == [("search_user", {"search_user_request": {"surname": "Smith"}})]
    assert message.content == "found"
    assert tool.schema["function"]["name"] == "search_user"


async def test_mcp_tool_serializes_non_text_content():
    content = [TextContent(type="text", text="a"), TextContent(type="text", text="b")]
    message = await mcp_tool(FakeClient(result=content)).execute("id", {})
    assert message.content == "a\nb"


async def test_mcp_tool_handles_none_result():
    message = await mcp_tool(FakeClient(result=None)).execute("id", {})
    assert message.content == "No content returned from tool"


async def test_mcp_tool_exception_becomes_tool_error():
    message = await mcp_tool(FakeClient(error=RuntimeError("boom"))).execute("id-9", {})
    assert message.content.startswith("ERROR")
    assert message.tool_call_id == "id-9"


class FakeSession:
    instances = []

    def __init__(self, read, write):
        self.closed = False
        FakeSession.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.closed = True

    async def initialize(self):
        return SimpleNamespace(model_dump=lambda: {})

    async def list_tools(self):
        tool = SimpleNamespace(name="search", description="d", input_schema={"type": "object"})
        return SimpleNamespace(tools=[tool])


def fake_transport(record):
    @asynccontextmanager
    async def transport(arg, *args, **kwargs):
        record["arg"] = arg
        try:
            yield ("read", "write")
        finally:
            record["closed"] = True

    return transport


async def test_stdio_client_launches_podman_without_tty(monkeypatch):
    record = {}
    monkeypatch.setattr(stdio_mcp_client, "stdio_client", fake_transport(record))
    monkeypatch.setattr(stdio_mcp_client, "ClientSession", FakeSession)

    client = await stdio_mcp_client.StdioMcpClient.create("image@sha256:abc")
    tools = await client.get_tools()
    await client.close()

    params = record["arg"]
    assert params.command == "podman"
    assert params.args == ["run", "--rm", "-i", "image@sha256:abc"]
    assert "-t" not in params.args
    assert tools[0].parameters == {"type": "object"}
    assert FakeSession.instances[-1].closed and record["closed"]
    assert client.session is None


async def test_http_client_unpacks_two_streams_and_closes(monkeypatch):
    record = {}
    monkeypatch.setattr(http_mcp_client, "streamable_http_client", fake_transport(record))
    monkeypatch.setattr(http_mcp_client, "ClientSession", FakeSession)

    client = await http_mcp_client.HttpMcpClient.create("http://localhost:8005/mcp")
    tools = await client.get_tools()
    await client.close()

    assert record["arg"] == "http://localhost:8005/mcp"
    assert tools[0].name == "search"
    assert record["closed"] and client.session is None


class FailingSession(FakeSession):
    async def initialize(self):
        raise RuntimeError("handshake failed")


@pytest.mark.parametrize(
    ("module", "factory", "transport_name", "target"),
    [
        (http_mcp_client, "HttpMcpClient", "streamable_http_client", "http://x/mcp"),
        (stdio_mcp_client, "StdioMcpClient", "stdio_client", "image"),
    ],
)
async def test_failed_connect_releases_transport(
    monkeypatch, module, factory, transport_name, target
):
    record = {}
    monkeypatch.setattr(module, transport_name, fake_transport(record))
    monkeypatch.setattr(module, "ClientSession", FailingSession)

    with pytest.raises(RuntimeError, match="handshake"):
        await getattr(module, factory).create(target)
    assert record["closed"] and FakeSession.instances[-1].closed
