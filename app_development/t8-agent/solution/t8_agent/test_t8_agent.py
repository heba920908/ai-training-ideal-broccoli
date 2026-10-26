"""Offline tests for the T8 agent: no DIAL calls, no running user service."""
import importlib
import json
from typing import Any

import pytest
from commons import constants
from commons.models.message import Message
from commons.models.role import Role
from t8_agent.task.agents import anthropic as anthropic_module
from t8_agent.task.agents import openai as openai_module
from t8_agent.task.agents.anthropic import AnthropicBasedAgent
from t8_agent.task.agents.openai import OpenAIBasedAgent
from t8_agent.task.tools import web_search as web_search_module
from t8_agent.task.tools.users.create_user_tool import CreateUserTool
from t8_agent.task.tools.users.delete_user_tool import DeleteUserTool
from t8_agent.task.tools.users.get_user_by_id_tool import GetUserByIdTool
from t8_agent.task.tools.users.search_users_tool import SearchUsersTool
from t8_agent.task.tools.users.update_user_tool import UpdateUserTool
from t8_agent.task.tools.web_search import WebSearchTool

FAKE_KEY = "fake-key-0000"


class FakeUserClient:
    def __init__(self, fail: bool = False):
        self.calls: list[tuple[str, Any]] = []
        self.fail = fail

    def _record(self, op: str, *args: Any, **kwargs: Any) -> str:
        if self.fail:
            raise Exception("HTTP 404: not found")  # noqa: TRY002 - mimics UserServiceClient
        self.calls.append((op, args or kwargs))
        return f"{op} ok"

    def get_user(self, user_id):
        return self._record("get_user", user_id)

    def search_users(self, name=None, surname=None, email=None, gender=None):
        return self._record("search_users", name=name, surname=surname, email=email, gender=gender)

    def add_user(self, model):
        return self._record("add_user", model)

    def update_user(self, user_id, model):
        return self._record("update_user", user_id, model)

    def delete_user(self, user_id):
        return self._record("delete_user", user_id)


class FakeResponse:
    def __init__(self, status_code: int, payload: Any = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or json.dumps(payload)

    def json(self):
        return self._payload


class FakePost:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.requests.append({"url": url, "headers": headers, "json": json})
        return self.responses.pop(0)


def all_tools(client=None):
    client = client or FakeUserClient()
    return [
        GetUserByIdTool(client), SearchUsersTool(client), CreateUserTool(client),
        UpdateUserTool(client), DeleteUserTool(client), WebSearchTool(FAKE_KEY, model="m"),
    ]


def resolve_refs(schema: dict, node: Any) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if ref:
            assert ref.startswith("#/$defs/")
            assert ref.split("/")[-1] in schema.get("$defs", {}), ref
        for value in node.values():
            resolve_refs(schema, value)
    elif isinstance(node, list):
        for value in node:
            resolve_refs(schema, value)


# ---------- configuration ----------

def test_endpoints_derive_from_openai_base_url(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://dial.example.com/openai/deployments/any-model/")
    try:
        cfg = importlib.reload(constants)
        assert cfg.OPENAI_CHAT_COMPLETIONS_ENDPOINT == "https://dial.example.com/openai/deployments/any-model/chat/completions"
        assert cfg.OPENAI_RESPONSES_ENDPOINT == "https://dial.example.com/openai/v1/responses"
        assert cfg.ANTHROPIC_ENDPOINT == "https://dial.example.com/anthropic/v1/messages"
    finally:
        monkeypatch.undo()
        importlib.reload(constants)


# ---------- tool schemas ----------

def test_tool_names_match_course():
    assert [t.name for t in all_tools()] == [
        "get_user_by_id", "search_users", "add_user", "update_user", "delete_users", "web_search_tool",
    ]


@pytest.mark.parametrize("tool", all_tools(), ids=lambda t: t.name)
def test_provider_schemas(tool):
    assert tool.openai_schema == {
        "type": "function",
        "function": {"name": tool.name, "description": tool.description, "parameters": tool.input_schema},
    }
    assert tool.anthropic_schema == {
        "name": tool.name, "description": tool.description, "input_schema": tool.input_schema,
    }
    schema = tool.input_schema
    assert schema["type"] == "object"
    resolve_refs(schema, schema)


def test_update_schema_hoists_defs_to_root():
    schema = UpdateUserTool(FakeUserClient()).input_schema
    assert "$defs" not in schema["properties"]["new_info"]
    assert {"Address"} <= set(schema["$defs"])
    assert schema["required"] == ["id", "new_info"]


# ---------- user tools ----------

def test_get_and_delete_cast_id_to_int():
    client = FakeUserClient()
    assert GetUserByIdTool(client).execute({"id": 3.0}) == "get_user ok"
    assert DeleteUserTool(client).execute({"id": "4"}) == "delete_user ok"
    assert client.calls == [("get_user", (3,)), ("delete_user", (4,))]


def test_search_passes_only_given_filters():
    client = FakeUserClient()
    SearchUsersTool(client).execute({"gender": "female"})
    assert client.calls == [("search_users", {"name": None, "surname": None, "email": None, "gender": "female"})]


def test_create_validates_and_reports_errors():
    client = FakeUserClient()
    ok = CreateUserTool(client).execute(
        {"name": "Andrej", "surname": "Karpathy", "email": "a@example.com", "about_me": "AI researcher"}
    )
    assert ok == "add_user ok"
    missing = CreateUserTool(client).execute({"name": "Andrej"})
    assert missing.startswith("Error while creating a new user:")
    assert len(client.calls) == 1


def test_update_validates_new_info():
    client = FakeUserClient()
    assert UpdateUserTool(client).execute({"id": 2, "new_info": {"company": "EPAM"}}) == "update_user ok"
    _, (user_id, model) = client.calls[0]
    assert user_id == 2 and model.company == "EPAM"
    assert UpdateUserTool(client).execute({"id": 2}).startswith("Error while updating user:")


@pytest.mark.parametrize("tool_cls,args,prefix", [
    (GetUserByIdTool, {"id": 1}, "Error while retrieving user by id:"),
    (DeleteUserTool, {"id": 1}, "Error while deleting user by id:"),
    (SearchUsersTool, {"name": "x"}, "Error while searching users:"),
])
def test_service_errors_become_strings(tool_cls, args, prefix):
    assert tool_cls(FakeUserClient(fail=True)).execute(args).startswith(prefix)


# ---------- web search ----------

def test_web_search_posts_to_dial_responses_and_extracts_text(monkeypatch):
    post = FakePost([FakeResponse(200, {"output": [
        {"type": "web_search_call"},
        {"type": "message", "content": [{"type": "output_text", "text": "Karpathy is an AI researcher."}]},
    ]})])
    monkeypatch.setattr(web_search_module.requests, "post", post)
    result = WebSearchTool(FAKE_KEY, model="search-deployment").execute({"request": "Andrej Karpathy"})
    assert result == "Karpathy is an AI researcher."
    sent = post.requests[0]
    assert sent["url"] == constants.OPENAI_RESPONSES_ENDPOINT
    assert sent["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert sent["json"] == {"model": "search-deployment", "input": "Andrej Karpathy", "tools": [{"type": "web_search"}]}


def test_web_search_returns_error_string_for_unsupported_deployment(monkeypatch):
    post = FakePost([FakeResponse(503, text="OpenAI responses not supported for this deployment type")])
    monkeypatch.setattr(web_search_module.requests, "post", post)
    result = WebSearchTool(FAKE_KEY, model="m").execute({"request": "x"})
    assert result == "Error: 503 OpenAI responses not supported for this deployment type"


# ---------- agents ----------

def test_blank_api_key_rejected():
    with pytest.raises(ValueError):
        OpenAIBasedAgent("m", "  ")
    with pytest.raises(ValueError):
        AnthropicBasedAgent("m", "")


def openai_tool_call_response(name: str, args: dict) -> FakeResponse:
    return FakeResponse(200, {"choices": [{"finish_reason": "tool_calls", "message": {
        "role": "assistant", "content": "\n\n",
        "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}],
    }}]})


def test_openai_agent_runs_tool_loop(monkeypatch):
    client = FakeUserClient()
    post = FakePost([
        openai_tool_call_response("get_user_by_id", {"id": 3}),
        FakeResponse(200, {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "User 3 is Ann."}}]}),
    ])
    monkeypatch.setattr(openai_module.requests, "post", post)
    agent = OpenAIBasedAgent("any-model", FAKE_KEY, all_tools(client), system_prompt="SYS")
    messages = [Message(role=Role.USER, content="Get user 3")]

    reply = agent.get_response(messages, print_request=False)

    assert reply.content == "User 3 is Ann."
    assert [m.role for m in messages] == [Role.USER, Role.ASSISTANT, Role.TOOL]
    assert messages[2].tool_call_id == "call_1" and messages[2].content == "get_user ok"
    first, second = post.requests
    assert first["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert first["json"]["messages"][0] == {"role": "system", "content": "SYS"}
    assert "reasoning_effort" not in first["json"]
    assert len(first["json"]["tools"]) == 6
    assert [m["role"] for m in second["json"]["messages"]] == ["system", "user", "assistant", "tool"]


def test_openai_agent_handles_unknown_tool_and_bad_json(monkeypatch):
    agent = OpenAIBasedAgent("m", FAKE_KEY, all_tools())
    assert agent._call_tool("nope", {}) == "Unknown function: nope"
    bad = agent._process_tool_calls([{"id": "c", "function": {"name": "search_users", "arguments": "{oops"}}])
    assert bad[0].content.startswith("Error: invalid JSON arguments")


def test_openai_agent_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(openai_module.requests, "post", FakePost([FakeResponse(401, text="unauthorized")]))
    agent = OpenAIBasedAgent("m", FAKE_KEY, all_tools())
    with pytest.raises(Exception, match="HTTP 401"):
        agent.get_response([Message(role=Role.USER, content="hi")], print_request=False)


def test_anthropic_agent_runs_tool_loop(monkeypatch):
    client = FakeUserClient()
    tool_turn = [
        {"type": "text", "text": "Searching."},
        {"type": "tool_use", "id": "toolu_1", "name": "search_users", "input": {"gender": "female"}},
        {"type": "tool_use", "id": "toolu_2", "name": "get_user_by_id", "input": {"id": 1}},
    ]
    post = FakePost([
        FakeResponse(200, {"content": tool_turn, "stop_reason": "tool_use"}),
        FakeResponse(200, {"content": [{"type": "text", "text": "Done."}], "stop_reason": "end_turn"}),
    ])
    monkeypatch.setattr(anthropic_module.requests, "post", post)
    agent = AnthropicBasedAgent("claude-deployment", FAKE_KEY, all_tools(client), system_prompt="SYS")
    messages = [Message(role=Role.USER, content="Find female users")]

    reply = agent.get_response(messages, print_request=False)

    assert reply.content == "Done." and reply.tool_calls is None
    first, second = post.requests
    assert first["url"] == constants.ANTHROPIC_ENDPOINT
    assert first["headers"]["x-api-key"] == FAKE_KEY
    assert first["headers"]["anthropic-version"] == "2023-06-01"
    assert first["json"]["system"] == "SYS"
    assert all(m["role"] != "system" for m in first["json"]["messages"])
    assert "input_schema" in first["json"]["tools"][0]
    sent = second["json"]["messages"]
    assert sent[1] == {"role": "assistant", "content": tool_turn}
    assert sent[2] == {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": "search_users ok"},
        {"type": "tool_result", "tool_use_id": "toolu_2", "content": "get_user ok"},
    ]}


def test_anthropic_messages_keep_plain_assistant_text():
    agent = AnthropicBasedAgent("m", FAKE_KEY)
    converted = agent._to_anthropic_messages([
        Message(role=Role.USER, content="hi"),
        Message(role=Role.ASSISTANT, content="hello"),
    ])
    assert converted == [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]


# ---------- app wiring ----------

def test_app_loop_uses_conversation_and_exits(monkeypatch, capsys):
    from t8_agent.task import app

    seen: list[list[str]] = []

    class StubAgent:
        def __init__(self, model, api_key, tools, system_prompt):
            assert len(tools) == 6 and system_prompt

        def get_response(self, messages, print_request=True):
            seen.append([m.content for m in messages])
            return Message(role=Role.ASSISTANT, content=f"reply {len(seen)}")

    monkeypatch.setattr(app, "OpenAIBasedAgent", StubAgent)
    monkeypatch.setattr(app, "OPENAI_API_KEY", FAKE_KEY)
    inputs = iter(["Find all female users", "", "Delete user with id 3", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    app.main(["--quiet"])

    assert seen == [["Find all female users"], ["Find all female users", "reply 1", "Delete user with id 3"]]
    assert "AI: reply 2" in capsys.readouterr().out
