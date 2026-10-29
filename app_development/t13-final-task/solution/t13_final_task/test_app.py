import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from t13_final_task.task.agent import app as app_module
from t13_final_task.task.agent.config import ProviderSettings
from t13_final_task.task.agent.models import McpToolModel, SkillMetadata
from t13_final_task.test_conversation_manager import FakeRedis


def skill(**extra):
    return SkillMetadata(
        name="demo-skill", description='Use for <users> & "quotes"', skill_dir=Path("x"), **extra
    )


def test_skills_xml_escapes_and_includes_optional_fields():
    xml = app_module._build_available_skills_xml(
        [
            skill(
                license="Apache-2.0",
                compatibility="python>=3.12",
                metadata={"author": "me", "version": "1.0"},
                allowed_tools=["read_skill", "search_user"],
            ),
            skill(),
        ]
    )
    assert xml.startswith("<available_skills>")
    assert '<skill name="demo-skill">' in xml
    assert "Use for &lt;users&gt; &amp;" in xml
    assert "<license>Apache-2.0</license>" in xml
    assert "<compatibility>python&gt;=3.12</compatibility>" in xml
    assert "<author>me</author>" in xml and "<version>1.0</version>" in xml
    assert "<allowed-tools>read_skill search_user</allowed-tools>" in xml
    assert xml.count("<license>") == 1


def test_system_prompt_embeds_xml_and_read_instructions():
    prompt = app_module.build_system_prompt([skill()])
    assert "<available_skills>" in prompt
    assert "read_skill" in prompt and "/<skill-name>/SKILL.md" in prompt


class FakeMcpClient:
    instances = []

    def __init__(self, target, tools, fail=False):
        self.target, self.tools, self.closed = target, tools, False
        if fail:
            raise RuntimeError("unreachable")
        FakeMcpClient.instances.append(self)

    async def get_tools(self):
        return [McpToolModel(name, "d", {"type": "object"}) for name in self.tools]

    async def call_tool(self, name, args):
        return "ok"

    async def close(self):
        self.closed = True


class FakeAgent:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def response(self, messages):
        from t13_final_task.task.agent.models import Message, Role

        reply = Message(role=Role.ASSISTANT, content="pong")
        messages.append(reply)
        return reply

    async def stream_response(self, messages):
        yield 'data: {"choices": [{"index": 0, "delta": {"content": "po"}}]}\n\n'
        yield "data: [DONE]\n\n"


@pytest.fixture
def env(monkeypatch):
    FakeMcpClient.instances = []
    state = {"redis": FakeRedis(), "fail_ddg": False}

    async def http_create(url):
        return FakeMcpClient(url, ["search_user", "delete_user"])

    async def stdio_create(image):
        return FakeMcpClient(image, ["search"], fail=state["fail_ddg"])

    monkeypatch.setattr(app_module.HttpMcpClient, "create", http_create)
    monkeypatch.setattr(app_module.StdioMcpClient, "create", stdio_create)
    monkeypatch.setattr(app_module, "_create_redis", lambda: state["redis"])
    monkeypatch.setattr(
        app_module,
        "dial_settings",
        lambda: ProviderSettings(model="m", base_url="https://dial.example", api_key="k"),
    )
    monkeypatch.setattr(
        app_module, "UMSAgent", lambda **kw: state.setdefault("agent", FakeAgent(**kw))
    )
    return state


def test_startup_registers_all_tools_and_shutdown_closes(env):
    with TestClient(app_module.app) as client:
        assert client.get("/health").json()["conversation_manager_initialized"] is True
        names = [tool.name for tool in env["agent"].kwargs["tools"]]
        assert names == ["read_skill", "search_user", "delete_user", "search"]
        assert env["agent"].kwargs["model"] == "m"
        assert env["agent"].kwargs["base_url"] == "https://dial.example"
    assert all(instance.closed for instance in FakeMcpClient.instances)
    assert env["redis"].closed
    assert app_module.conversation_manager is None


def test_startup_failure_closes_opened_resources(env):
    env["fail_ddg"] = True
    with pytest.raises(RuntimeError):
        with TestClient(app_module.app):
            pass
    assert len(FakeMcpClient.instances) == 1 and FakeMcpClient.instances[0].closed


def test_conversation_endpoints_and_chat(env):
    with TestClient(app_module.app) as client:
        created = client.post("/conversations", json={"title": "Smith search"}).json()
        cid = created["id"]
        assert client.get("/conversations").json()[0]["id"] == cid
        assert client.get(f"/conversations/{cid}").json()["title"] == "Smith search"

        reply = client.post(
            f"/conversations/{cid}/chat",
            json={"message": {"role": "user", "content": "ping"}, "stream": False},
        )
        assert reply.json() == {"content": "pong", "conversation_id": cid}

        with client.stream(
            "POST",
            f"/conversations/{cid}/chat",
            json={"message": {"role": "user", "content": "ping"}},
        ) as streamed:
            assert streamed.headers["content-type"].startswith("text/event-stream")
            body = "".join(streamed.iter_text())
        assert json.loads(body.split("\n\n")[0][6:]) == {"conversation_id": cid}
        assert body.rstrip().endswith("data: [DONE]")

        assert client.delete(f"/conversations/{cid}").status_code == 200
        assert client.get(f"/conversations/{cid}").status_code == 404
        assert client.delete(f"/conversations/{cid}").status_code == 404


def test_untitled_conversation_gets_default_title(env):
    with TestClient(app_module.app) as client:
        assert client.post("/conversations", json={}).json()["title"]


@pytest.mark.parametrize(
    "message",
    [
        {"role": "system", "content": "x"},
        {"role": "tool", "content": "x"},
        {"role": "user", "content": " "},
    ],
)
def test_chat_rejects_non_user_or_empty_messages(env, message):
    with TestClient(app_module.app) as client:
        cid = client.post("/conversations", json={"title": "t"}).json()["id"]
        response = client.post(f"/conversations/{cid}/chat", json={"message": message})
        assert response.status_code == 422


def test_chat_unknown_conversation_is_404(env):
    with TestClient(app_module.app) as client:
        response = client.post(
            "/conversations/missing/chat", json={"message": {"role": "user", "content": "x"}}
        )
        assert response.status_code == 404
        assert env["redis"].values == {}


def test_root_serves_ui(env):
    with TestClient(app_module.app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "<html" in response.text.lower()


@pytest.mark.parametrize(
    ("origin", "allowed"),
    [
        ("http://localhost:8011", True),
        ("http://127.0.0.1:8011", True),
        ("https://evil.example", False),
    ],
)
def test_cors_is_loopback_only(env, origin, allowed):
    with TestClient(app_module.app) as client:
        response = client.get("/health", headers={"Origin": origin})
        assert (response.headers.get("access-control-allow-origin") == origin) is allowed
        assert "access-control-allow-credentials" not in response.headers
