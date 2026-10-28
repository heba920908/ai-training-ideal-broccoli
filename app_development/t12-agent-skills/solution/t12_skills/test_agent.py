import json
import os
import threading
from copy import deepcopy
from types import SimpleNamespace

import pytest
from commons.models.message import Message
from commons.models.role import Role
from t12_skills.custom.agent import T12Agent
from t12_skills.custom.tools.base import BaseTool


@pytest.mark.asyncio
async def test_decorated_async_provider_return_is_awaited():
    async def create_response():
        return completion("done")

    provider = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: create_response()))
    )
    reply = await T12Agent(provider, "configured").chat_completion([Message(Role.USER, "hello")])
    assert reply.content == "done"


def test_probe_requires_read_before_execution_and_numeric_output():
    from t12_skills.probe import validate_history

    def call(identifier, name, arguments):
        return {"id": identifier, "function": {"name": name, "arguments": json.dumps(arguments)}}

    history = [
        {"role": "system", "content": "metadata only"},
        {
            "role": "assistant",
            "tool_calls": [call("read", "read_skill", {"path": "/unit-converter/SKILL.md"})],
        },
        {"role": "tool", "tool_call_id": "read", "name": "read_skill", "content": "instructions"},
        {
            "role": "assistant",
            "tool_calls": [
                call(
                    "run",
                    "execute_code",
                    {
                        "script_path": "/unit-converter/scripts/convert.py",
                        "code": "print(37)",
                        "session_id": "",
                    },
                )
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "run",
            "name": "execute_code",
            "content": json.dumps(
                {
                    "success": True,
                    "output": ["37 Celsius\n310.15 Kelvin"],
                    "session_info": {"session_id": "session"},
                }
            ),
        },
    ]
    assert validate_history(history, [37, 310.15])["session_ids"] == ["session"]
    with pytest.raises(AssertionError, match="numeric"):
        validate_history(history, [999])
    with pytest.raises(AssertionError, match="read"):
        validate_history(history[3:], [37])


@pytest.fixture
def provider_env(monkeypatch, tmp_path):
    for key in list(os.environ):
        if key.startswith(("OPENAI_", "ANTHROPIC_")):
            monkeypatch.delenv(key)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://dial.example/deployments/test")
    monkeypatch.setenv("OPENAI_MODEL", "configured-deployment")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_dial_configuration_retains_model_header_and_finite_limits(provider_env):
    from t12_skills.config import dial_settings

    settings = dial_settings()
    assert settings.model == "configured-deployment"
    assert settings.client_kwargs()["base_url"] == "https://dial.example/deployments/test"
    assert settings.client_kwargs()["default_headers"] == {"Api-Key": "test-key"}
    assert settings.client_kwargs()["timeout"] == 90
    assert settings.client_kwargs()["max_retries"] == 1
    assert "reasoning_effort" not in settings.client_kwargs()


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "https://API.OPENAI.COM./v1",
        "https://user:password@dial.example/v1",
        "https://dial.example/v1?api_key=secret",
        "file:///tmp/provider",
        "http://dial.example/v1",
    ],
)
def test_rejects_provider_boundary_changes_before_client_construction(
    provider_env, monkeypatch, url
):
    from t12_skills.config import dial_settings

    monkeypatch.setenv("OPENAI_BASE_URL", url)
    with pytest.raises(ValueError):
        dial_settings()


@pytest.mark.parametrize("missing", ["OPENAI_BASE_URL", "OPENAI_MODEL", "OPENAI_API_KEY"])
def test_missing_configuration_is_actionable_without_values(provider_env, monkeypatch, missing):
    from t12_skills.config import dial_settings

    monkeypatch.delenv(missing)
    with pytest.raises(ValueError, match=missing) as failure:
        dial_settings()
    assert "synthetic-test-value" not in str(failure.value)


def test_nearest_ancestor_dotenv_preserves_exported_values(provider_env, monkeypatch):
    from t12_skills.config import dial_settings

    (provider_env / ".env").write_text(
        "OPENAI_MODEL=ancestor-model\nOPENAI_API_KEY=ancestor-test-value\n"
    )
    nested = provider_env / "outer" / "inner"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.delenv("OPENAI_API_KEY")
    settings = dial_settings()
    assert settings.model == "configured-deployment"
    assert settings.client_kwargs()["api_key"] == "ancestor-test-value"


def test_anthropic_requires_environment_model_and_token_bound(provider_env, monkeypatch):
    from t12_skills.config import anthropic_settings, token_limit

    with pytest.raises(ValueError, match="ANTHROPIC"):
        anthropic_settings()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-anthropic-value")
    monkeypatch.setenv("ANTHROPIC_MODEL", "configured-anthropic-deployment")
    assert anthropic_settings().model == "configured-anthropic-deployment"
    assert token_limit(512) == 512
    for value in (0, -1, 1000000):
        with pytest.raises(ValueError):
            token_limit(value)


def tool_call(name="echo", arguments='{"value": "hello"}', identifier="call-1"):
    return SimpleNamespace(
        id=identifier, type="function", function=SimpleNamespace(name=name, arguments=arguments)
    )


def completion(content="done", calls=None, reason="stop", refusal=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=reason,
                message=SimpleNamespace(content=content, tool_calls=calls, refusal=refusal),
            )
        ],
        usage=SimpleNamespace(model_dump=lambda: {"total_tokens": 30}),
    )


class Provider:
    def __init__(self, replies):
        self.replies, self.requests, self.threads = iter(replies), [], []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **payload):
        self.threads.append(threading.get_ident())
        self.requests.append(deepcopy(payload))
        return next(self.replies)


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo a value"
    parameters = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
    }

    async def _execute(self, arguments):
        return arguments["value"]


@pytest.mark.asyncio
async def test_plain_completion_accepts_none_tools_and_does_not_block_loop():
    provider = Provider([completion()])
    result = await T12Agent(provider, "configured-model").chat_completion(
        [Message(Role.USER, "hello")]
    )
    assert result.content == "done"
    assert provider.requests == [
        {"model": "configured-model", "messages": [{"role": "user", "content": "hello"}]}
    ]
    assert provider.threads[0] != threading.get_ident()


def test_duplicate_tool_names_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        T12Agent(Provider([]), "configured-model", [EchoTool(), EchoTool()])


@pytest.mark.asyncio
async def test_tool_turn_preserves_ids_serialization_and_order():
    calls = [
        tool_call(identifier="first"),
        tool_call(arguments='{"value":"world"}', identifier="second"),
    ]
    provider = Provider([completion(None, calls, "tool_calls"), completion("hello world")])
    messages = [Message(Role.SYSTEM, "instructions"), Message(Role.USER, "echo")]
    result = await T12Agent(provider, "configured-model", [EchoTool()]).chat_completion(messages)
    assert result.content == "hello world"
    history = provider.requests[1]["messages"]
    assert history[2]["tool_calls"][0] == {
        "id": "first",
        "type": "function",
        "function": {"name": "echo", "arguments": '{"value": "hello"}'},
    }
    assert [(entry["tool_call_id"], entry["content"]) for entry in history[3:]] == [
        ("first", "hello"),
        ("second", "world"),
    ]
    assert "reasoning_effort" not in provider.requests[0]
    assert "temperature" not in provider.requests[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,arguments",
    [("missing", "{}"), ("echo", "broken"), ("echo", "[]"), ("echo", "null"), ("echo", "{}")],
)
async def test_dispatch_failures_stay_correlated_and_do_not_abort_query(name, arguments):
    provider = Provider(
        [completion(None, [tool_call(name, arguments)], "tool_calls"), completion("recovered")]
    )
    await T12Agent(provider, "configured-model", [EchoTool()]).chat_completion(
        [Message(Role.USER, "hello")]
    )
    message = provider.requests[1]["messages"][-1]
    assert message["role"] == "tool"
    assert message["tool_call_id"] == "call-1"
    assert message["name"] == name
    assert message["content"].startswith("ERROR")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason,refusal", [("length", None), ("content_filter", None), ("stop", "cannot comply")]
)
async def test_non_success_finish_reasons_are_not_normal_completion(reason, refusal):
    with pytest.raises(RuntimeError):
        await T12Agent(
            Provider([completion("partial", reason=reason, refusal=refusal)]), "configured-model"
        ).chat_completion([])


@pytest.mark.asyncio
async def test_repeated_tool_requests_stop_after_ten_provider_rounds():
    provider = Provider([completion(None, [tool_call()], "tool_calls")] * 11)
    with pytest.raises(RuntimeError, match="10"):
        await T12Agent(provider, "configured-model", [EchoTool()]).chat_completion([])
    assert len(provider.requests) == 10


def test_system_prompt_escapes_metadata_without_loading_skill_body(tmp_path):
    import xml.etree.ElementTree as ET

    from t12_skills.custom.custom_app import _build_available_skills_xml, build_system_prompt
    from t12_skills.custom.models import SkillMetadata

    skill = SkillMetadata(
        "sample", "Convert <units> & quantities", tmp_path, metadata={"unsafe<key": "<value>&"}
    )
    xml = ET.fromstring(_build_available_skills_xml([skill]))
    assert xml.find("skill/description").text == "Convert <units> & quantities"
    assert xml.find("skill/metadata/entry").attrib["key"] == "unsafe<key"
    prompt = build_system_prompt([skill])
    assert "read_skill" in prompt and "script_path" in prompt
    assert "def convert_units" not in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("ending", ["exit", "quit", None])
async def test_custom_chat_exit_quit_eof_do_not_call_provider(ending):
    from t12_skills.custom.custom_app import run_chat

    def read(_prompt):
        if ending is None:
            raise EOFError
        return ending

    provider = Provider([])
    history = await run_chat(T12Agent(provider, "configured-model"), [], input_fn=read)
    assert [message.role for message in history] == [Role.SYSTEM]
    assert provider.requests == []


@pytest.mark.asyncio
async def test_custom_single_query_progressively_reads_then_executes(tmp_path):
    from t12_skills.custom.custom_app import run_chat
    from t12_skills.custom.models import SkillMetadata
    from t12_skills.custom.tools.skills.read_skill_tool import ReadSkillTool

    directory = tmp_path / "sample"
    directory.mkdir()
    (directory / "SKILL.md").write_text("BODY-SENTINEL: execute the calculation")

    class Execute(EchoTool):
        name = "execute_code"

    provider = Provider(
        [
            completion(
                None, [tool_call("read_skill", '{"path":"sample/SKILL.md"}', "read")], "tool_calls"
            ),
            completion(
                None, [tool_call("execute_code", '{"value":"37 celsius"}', "execute")], "tool_calls"
            ),
            completion("37 celsius"),
        ]
    )
    history = await run_chat(
        T12Agent(provider, "configured-model", [ReadSkillTool(tmp_path), Execute()]),
        [SkillMetadata("sample", "Convert quantities", directory)],
        query="convert",
    )
    assert "BODY-SENTINEL" not in json.dumps(provider.requests[0])
    assert "BODY-SENTINEL" in provider.requests[1]["messages"][-1]["content"]
    assert [message.role for message in history] == [
        Role.SYSTEM,
        Role.USER,
        Role.ASSISTANT,
        Role.TOOL,
        Role.ASSISTANT,
        Role.TOOL,
        Role.ASSISTANT,
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True])
async def test_custom_main_closes_owned_tool_then_provider(provider_env, monkeypatch, fail):
    from t12_skills.custom import custom_app

    events = []

    class Client(Provider):
        async def __aenter__(self):
            events.append("provider-enter")
            return self

        async def __aexit__(self, *args):
            events.append("provider-close")

    client = Client([completion("done", reason="length" if fail else "stop")])
    monkeypatch.setattr(custom_app, "AsyncOpenAI", lambda **kwargs: client)

    async def create(url, name, skills):
        assert url == "http://127.0.0.1:8123/mcp"
        tool = EchoTool()

        async def close():
            events.append("tool-close")

        tool.close = close
        return tool

    monkeypatch.setattr(custom_app.PythonCodeInterpreterTool, "create", create)
    if fail:
        with pytest.raises(RuntimeError):
            await custom_app.main(["--query", "test", "--mcp-url", "http://127.0.0.1:8123/mcp"])
    else:
        await custom_app.main(["--query", "test", "--mcp-url", "http://127.0.0.1:8123/mcp"])
    assert events == ["provider-enter", "tool-close", "provider-close"]
