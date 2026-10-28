import io
import zipfile
from copy import deepcopy
from types import SimpleNamespace

import pytest


class Page:
    def __init__(self, data, next_page=None):
        self.data, self.next_page = data, next_page

    def has_next_page(self):
        return self.next_page is not None

    def get_next_page(self):
        return self.next_page


class SkillsAPI:
    def __init__(self, page=None):
        self.page = page or Page([])
        self.uploads, self.deleted = [], []
        self.versions = SimpleNamespace(
            list=lambda **kwargs: Page([SimpleNamespace(id="version-created", version="1")]),
            delete=self.delete_version,
        )

    def list(self, **kwargs):
        self.list_payload = kwargs
        return self.page

    def create(self, **kwargs):
        self.uploads.append(kwargs)
        return SimpleNamespace(
            id="skill-created", latest_version_id="version-created", default_version="1"
        )

    def delete(self, skill_id, **kwargs):
        self.deleted.append(("skill", skill_id))

    def delete_version(self, version, *, skill_id, **kwargs):
        self.deleted.append(("version", skill_id, version))


class MessagesAPI:
    def __init__(self, responses):
        self.responses, self.requests = iter(responses), []

    def create(self, **kwargs):
        self.requests.append(deepcopy(kwargs))
        result = next(self.responses)
        if isinstance(result, BaseException):
            raise result
        return result

    def retrieve(self, response_id):
        return self.create(retrieve=response_id)


def anthropic_response(reason="end_turn"):
    return SimpleNamespace(
        content=[
            {"type": "text", "text": "answer"},
            {
                "type": "server_tool_use",
                "id": "tool",
                "name": "bash_code_execution",
                "input": {"command": "true"},
            },
        ],
        container=SimpleNamespace(id="container-owned"),
        stop_reason=reason,
        usage=SimpleNamespace(model_dump=lambda: {"input_tokens": 30, "output_tokens": 10}),
    )


def openai_response(status="completed", identifier="response-1"):
    return SimpleNamespace(
        id=identifier,
        status=status,
        output_text="answer",
        output=[
            SimpleNamespace(
                type="shell_call", environment=SimpleNamespace(container_id="container-owned")
            )
        ],
        usage=SimpleNamespace(model_dump=lambda: {"input_tokens": 30, "output_tokens": 10}),
    )


@pytest.fixture
def selected_skill(tmp_path):
    directory = tmp_path / "calculator"
    (directory / "scripts").mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        "---\nname: calculator\ndescription: Calculate numeric expressions.\n---\nUse the script."
    )
    (directory / "scripts/calculate.py").write_text("print(42)")
    (directory / ".env").write_text("EXCLUDED=synthetic")
    (directory / "capture.json").write_text("excluded")
    return directory


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_managed_discovery_reuses_match_on_later_pages_without_ownership(provider, selected_skill):
    from t12_skills import anthropic_app, openai_app

    app = anthropic_app if provider == "anthropic" else openai_app
    skills = SkillsAPI(
        Page(
            [SimpleNamespace(id="unrelated", name="other", display_name="other")],
            Page([SimpleNamespace(id="reused", name="calculator", display_name="calculator")]),
        )
    )
    client = SimpleNamespace(skills=skills, beta=SimpleNamespace(skills=skills))
    owned = {}
    assert app.get_or_create_skill("calculator", selected_skill, client, owned=owned) == "reused"
    assert owned == {} and skills.uploads == []
    app.delete_skills(client, owned)
    assert skills.deleted == []


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_managed_upload_tracks_only_created_resource_and_allowlisted_files(
    provider, selected_skill
):
    from t12_skills import anthropic_app, openai_app

    app = anthropic_app if provider == "anthropic" else openai_app
    skills = SkillsAPI()
    client = SimpleNamespace(skills=skills, beta=SimpleNamespace(skills=skills))
    owned = {}
    assert (
        app.get_or_create_skill("calculator", selected_skill, client, owned=owned)
        == "skill-created"
    )
    assert set(owned) == {"skill-created"}
    upload = skills.uploads[0]
    if provider == "openai":
        with zipfile.ZipFile(io.BytesIO(upload["files"][0][1])) as archive:
            assert archive.namelist() == ["calculator/SKILL.md", "calculator/scripts/calculate.py"]
    else:
        assert [file[0] for file in upload["files"]] == [
            "calculator/SKILL.md",
            "calculator/scripts/calculate.py",
        ]
    app.delete_skills(client, owned)
    assert ("skill", "skill-created") in skills.deleted
    assert all("unrelated" not in item for item in skills.deleted)


def test_openai_zip_is_deterministic_and_rejects_escape(selected_skill, tmp_path):
    from t12_skills.openai_app import zip_skill

    assert zip_skill(selected_skill) == zip_skill(selected_skill)
    outside = tmp_path / "outside.py"
    outside.write_text("outside-content")
    (selected_skill / "scripts/calculate.py").unlink()
    (selected_skill / "scripts/calculate.py").symlink_to(outside)
    with pytest.raises(ValueError):
        zip_skill(selected_skill)


def test_anthropic_preserves_blocks_betas_and_container_across_pause_and_turns():
    from t12_skills.anthropic_app import Conversation

    api = MessagesAPI(
        [anthropic_response("pause_turn"), anthropic_response(), anthropic_response()]
    )
    conversation = Conversation(
        SimpleNamespace(beta=SimpleNamespace(messages=api)),
        "selected",
        "configured-model",
        max_tokens=512,
    )
    conversation.ask("first")
    conversation.ask("second")
    request = api.requests[0]
    assert request["model"] == "configured-model" and request["max_tokens"] == 512
    assert request["container"]["skills"] == [
        {"type": "custom", "skill_id": "selected", "version": "latest"}
    ]
    assert "code-execution-2025-08-25" in request["betas"]
    assert request["tools"] == [{"type": "code_execution_20250825", "name": "code_execution"}]
    assert api.requests[1]["container"]["id"] == "container-owned"
    assert api.requests[1]["messages"][-1]["content"] == anthropic_response().content
    assert api.requests[2]["messages"][-1] == {"role": "user", "content": "second"}


def test_openai_hosted_shell_uses_selected_skill_and_previous_response():
    from t12_skills.openai_app import Conversation

    api = MessagesAPI([openai_response(), openai_response(identifier="response-2")])
    conversation = Conversation(
        SimpleNamespace(responses=api), "selected", "configured-model", max_tokens=512
    )
    conversation.ask("first")
    conversation.ask("second")
    request = api.requests[0]
    assert request["model"] == "configured-model" and request["max_output_tokens"] == 512
    assert request["tools"][0]["environment"]["skills"] == [
        {"type": "skill_reference", "skill_id": "selected"}
    ]
    assert request["tools"][0]["environment"]["type"] == "container_auto"
    assert api.requests[1]["previous_response_id"] == "response-1"
    assert api.requests[1]["tools"][0]["environment"] == {
        "type": "container_reference",
        "container_id": "container-owned",
    }


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_managed_continuation_is_bounded_and_missing_apis_are_explicit(provider):
    from t12_skills import anthropic_app, openai_app

    app = anthropic_app if provider == "anthropic" else openai_app
    response = (
        anthropic_response("pause_turn")
        if provider == "anthropic"
        else openai_response("in_progress")
    )
    api = MessagesAPI([response] * 11)
    client = SimpleNamespace(beta=SimpleNamespace(messages=api), responses=api)
    conversation = app.Conversation(client, "selected", "configured-model", max_tokens=128)
    with pytest.raises(RuntimeError, match="10"):
        conversation.ask("continue")
    assert len(api.requests) == 10
    with pytest.raises(RuntimeError, match="capability"):
        app.Conversation(SimpleNamespace(), "selected", "configured-model").ask("test")


def test_openai_in_progress_retrieves_without_new_generation():
    from t12_skills.openai_app import Conversation

    api = MessagesAPI([openai_response("in_progress"), openai_response()])
    Conversation(SimpleNamespace(responses=api), "selected", "model").ask("calculate")
    assert api.requests[1] == {"retrieve": "response-1"}


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_cleanup_preserves_concurrent_versions_and_unrelated_resources(provider):
    from t12_skills import anthropic_app, openai_app

    app = anthropic_app if provider == "anthropic" else openai_app
    skills = SkillsAPI()
    skills.versions.list = lambda **kwargs: Page(
        [SimpleNamespace(id="version-created", version="1")],
        Page([SimpleNamespace(id="someone-else", version="2")]),
    )
    owned = {"skill-created": {"version-created" if provider == "anthropic" else "1"}}
    warnings = app.delete_skills(SimpleNamespace(skills=skills), owned)
    assert warnings and skills.deleted == [
        ("version", "skill-created", next(iter(owned["skill-created"])))
    ]


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
@pytest.mark.parametrize("failure", [RuntimeError("primary-failure"), KeyboardInterrupt()])
def test_managed_main_cleans_owned_after_query_failure_without_masking(
    provider, failure, monkeypatch
):
    from t12_skills import anthropic_app, openai_app

    app = anthropic_app if provider == "anthropic" else openai_app
    skills = SkillsAPI()
    closed = []

    class Client:
        def __enter__(self):
            self.skills = skills
            return self

        def __exit__(self, *args):
            closed.append(True)

    monkeypatch.setattr(
        app,
        "anthropic_settings" if provider == "anthropic" else "dial_settings",
        lambda: SimpleNamespace(model="configured", client_kwargs=lambda: {}),
    )
    monkeypatch.setattr(
        app.anthropic if provider == "anthropic" else app,
        "Anthropic" if provider == "anthropic" else "OpenAI",
        lambda **kwargs: Client(),
    )

    def fail_chat(*args, **kwargs):
        raise failure

    def fail_delete(**kwargs):
        raise RuntimeError("synthetic-sensitive-error")

    monkeypatch.setattr(app, "chat", fail_chat)
    skills.delete = fail_delete
    with pytest.raises(type(failure)) as caught:
        app.main(["--query", "test"])
    assert caught.value is failure and closed == [True]


@pytest.mark.parametrize("value", ["1", "512", "8192"])
def test_managed_cli_accepts_bounded_integer_tokens(value):
    from t12_skills.managed import arguments

    assert arguments(["--max-tokens", value]).max_tokens == int(value)


@pytest.mark.parametrize("value", ["0", "8193", "bad"])
def test_managed_cli_rejects_bad_tokens(value):
    from t12_skills.managed import arguments

    with pytest.raises(SystemExit):
        arguments(["--max-tokens", value])


@pytest.mark.parametrize("command", ["exit", "quit", None])
def test_managed_interactive_exit_and_eof_never_calls_provider(command):
    from t12_skills.managed import interact

    def input_fn(prompt):
        if command is None:
            raise EOFError
        return command

    assert interact(SimpleNamespace(), input_fn=input_fn) == []


def test_managed_query_is_one_turn_and_usage_reported(capsys):
    from t12_skills.managed import interact

    calls = []
    conversation = SimpleNamespace(
        ask=lambda query: calls.append(query) or openai_response(),
        text=lambda response: response.output_text,
    )
    assert len(interact(conversation, query="one query")) == 1
    assert calls == ["one query"] and "input_tokens" in capsys.readouterr().out
