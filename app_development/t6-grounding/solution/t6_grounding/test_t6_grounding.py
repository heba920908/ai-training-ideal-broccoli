import importlib
import json

import httpx
import pytest


def core():
    try:
        return importlib.import_module("t6_grounding.grounding")
    except ModuleNotFoundError:
        pytest.fail("T6 grounding implementation is missing")


def test_prompt_projection_excludes_sensitive_fields():
    user = {
        "id": 1,
        "name": "Ada",
        "about_me": "hiking",
        "credit_card": {"cvv": "secret"},
        "salary": 42,
    }
    assert core().public_user(user) == {"id": 1, "name": "Ada", "about_me": "hiking"}


def test_output_grounding_rejects_unknown_deleted_and_duplicate_ids():
    module = core()

    def handler(request):
        if request.url.path == "/v1/users/1":
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "name": "Current Ada",
                    "about_me": "hiking",
                    "credit_card": {"cvv": "secret"},
                },
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        service = module.UserService("http://127.0.0.1:8041", http)
        groups, rejected = module.ground_output(
            {"groups": [{"hobby": "hiking", "user_ids": [1, 1, 2, 999]}]},
            {1, 2},
            service,
        )
    assert groups == {
        "hiking": [{"id": 1, "name": "Current Ada", "about_me": "hiking"}]
    }
    assert rejected == [2, 999]


def test_output_grounding_does_not_swallow_service_failure():
    module = core()
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(503))
        ) as http,
        pytest.raises(RuntimeError, match="503"),
    ):
        module.ground_output(
            {"groups": [{"hobby": "hiking", "user_ids": [1]}]},
            {1},
            module.UserService("http://127.0.0.1:8041", http),
        )


def test_dial_routes_and_embedding_order():
    module = core()
    seen = []

    def handler(request):
        seen.append(
            (
                request.url.path,
                request.headers.get("Api-Key"),
                json.loads(request.content) if request.content else None,
            )
        )
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "text-embedding-test"}]})
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"index": 1, "embedding": [0.0, 1.0]},
                        {"index": 0, "embedding": [1.0, 0.0]},
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "answer"}}],
                "usage": {"total_tokens": 7},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        dial = module.Dial(
            "https://dial.example/openai/deployments/chat-test",
            "chat-test",
            "test-key",
            http=http,
        )
        assert dial.embed(["first", "second"]) == [[1.0, 0.0], [0.0, 1.0]]
        assert dial.complete("system", "question") == "answer"
        assert dial.total_tokens == 7
    assert [item[0] for item in seen] == [
        "/openai/models",
        "/openai/deployments/text-embedding-test/embeddings",
        "/openai/deployments/chat-test/chat/completions",
    ]
    assert all(item[1] == "test-key" for item in seen)
    assert "temperature" not in seen[-1][2]


@pytest.mark.parametrize(
    "url",
    [
        "https://openai.com",
        "https://api.openai.com/v1",
        "https://openai.com./",
        "https://api.openai.com./v1",
        "http://dial.example",
        "https://key@dial.example",
        "https://dial.example?key=secret",
    ],
)
def test_dial_rejects_unsafe_urls(url):
    with pytest.raises(ValueError):
        core().Dial(url, "model", "key")


def test_schema_rejects_string_ids():
    with pytest.raises(ValueError):
        core().Groups.model_validate(
            {"groups": [{"hobby": "hiking", "user_ids": ["1"]}]}
        )


class Embeddings:
    def __init__(self):
        self.inputs = []

    def embed(self, texts):
        self.inputs.extend(texts)
        return [[1.0, 0.0] if "hiking" in text else [0.0, 1.0] for text in texts]


@pytest.mark.parametrize("backend", ["faiss", "chroma"])
def test_vector_ranking_threshold_and_empty_index(backend):
    module = core()
    assert hasattr(module, "VectorIndex"), "Vector retrieval is not implemented"
    index = module.VectorIndex(Embeddings(), backend)
    assert index.search("hiking", 3, 0.5) == []
    index.sync([{"id": 1, "about_me": "hiking"}, {"id": 2, "about_me": "painting"}])
    matches = index.search("hiking", 3, 0.5)
    assert [user["id"] for user, score in matches] == [1]
    assert matches[0][1] == pytest.approx(1.0)


def test_chroma_sync_tracks_additions_changes_and_deletions():
    module = core()
    assert hasattr(module, "VectorIndex"), "Vector synchronization is not implemented"
    embeddings = Embeddings()
    index = module.VectorIndex(embeddings, "chroma")
    index.sync([{"id": 1, "about_me": "hiking"}, {"id": 2, "about_me": "painting"}])
    assert len(embeddings.inputs) == 2
    index.sync([{"id": 1, "about_me": "hiking"}, {"id": 2, "about_me": "painting"}])
    assert len(embeddings.inputs) == 2
    index.sync([{"id": 2, "about_me": "hiking"}, {"id": 3, "about_me": "painting"}])
    assert len(embeddings.inputs) == 4
    assert [user["id"] for user, score in index.search("hiking", 3, 0.5)] == [2]
    assert set(index.collection.get()["ids"]) == {"2", "3"}
    index.sync([])
    assert index.collection.count() == 0
    assert index.search("hiking", 3, 0.0) == []


def engine():
    try:
        return importlib.import_module("t6_grounding.runner")
    except ModuleNotFoundError:
        pytest.fail("T6 flow orchestration is missing")


class Chat(Embeddings):
    calls = total_tokens = 0

    def __init__(self, responses):
        super().__init__()
        self.responses = iter(responses)

    def complete(self, system, message, schema=None):
        self.calls += 1
        return next(self.responses)


def test_api_no_extracted_parameters_does_not_fetch_all_users():
    module = engine()

    def handler(request):
        pytest.fail("An unfiltered API request must not be made")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        runner = module.Runner(
            Chat([{"name": None, "surname": None, "email": None}]),
            core().UserService(http=http),
        )
        result = runner.run("api", "Who likes hiking?")
    assert result["candidates"] == []
    assert "No specific search" in result["answer"]


def test_api_rejects_invented_filter():
    module = engine()
    runner = module.Runner(
        Chat([{"name": "Invented", "surname": None, "email": None}]), None
    )
    with pytest.raises(ValueError, match="explicit"):
        runner.run("api", "Who is Ada?")


def test_baseline_all_no_matches_skips_final_generation():
    module = engine()
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json=[{"id": 1, "name": "Ada", "about_me": "hiking"}]
            )
        )
    ) as http:
        runner = module.Runner(
            Chat(["NO_MATCHES_FOUND"]), core().UserService(http=http)
        )
        result = runner.run("no", "Find Nobody")
    assert result["answer"] == "No users found."


def test_inout_uses_retrieved_allowlist_and_live_records():
    module = engine()

    def handler(request):
        if request.url.path == "/v1/users":
            return httpx.Response(
                200, json=[{"id": 1, "name": "Stale", "about_me": "hiking"}]
            )
        if request.url.path == "/v1/users/1":
            return httpx.Response(
                200, json={"id": 1, "name": "Current", "about_me": "hiking"}
            )
        pytest.fail("Unknown generated IDs must not be fetched")

    dial = Chat([{"groups": [{"hobby": "hiking", "user_ids": [1, 999]}]}])
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        runner = module.Runner(dial, core().UserService(http=http))
        result = runner.run("inout", "hiking")
    assert result["answer"] == {
        "hiking": [{"id": 1, "name": "Current", "about_me": "hiking"}]
    }
    assert result["rejected_ids"] == [999]


def test_environment_loads_ancestor_file_without_overriding_exports(
    tmp_path, monkeypatch
):
    module = core()
    (tmp_path / ".env").write_text(
        "OPENAI_BASE_URL=https://dial.example/openai\nOPENAI_MODEL=file-model\nOPENAI_API_KEY=test-only-key\n"
    )
    monkeypatch.setattr(module, "__file__", str(tmp_path / "nested" / "grounding.py"))
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "exported-model")
    dial = module.Dial.from_env()
    try:
        assert dial.root == "https://dial.example/openai"
        assert dial.model == "exported-model"
        assert dial.key == "test-only-key"
    finally:
        dial.close()


def test_api_success_forwards_explicit_field_to_service():
    module = engine()

    def handler(request):
        if request.url.path == "/v1/users/search" and dict(request.url.params) == {
            "name": "Ada"
        }:
            return httpx.Response(
                200, json=[{"id": 1, "name": "Ada", "about_me": "hiking"}]
            )
        return httpx.Response(400)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        runner = module.Runner(
            Chat([{"name": "Ada"}, "Ada enjoys hiking."]), core().UserService(http=http)
        )
        result = runner.run("api", "Who is Ada?")
    assert result["candidates"] == [1]
    assert result["answer"] == "Ada enjoys hiking."
    assert result["api_calls"] == 2


def test_baseline_aggregates_multiple_matching_batches():
    module = engine()
    users = [
        {"id": 1, "name": "Ada", "about_me": "hiking"},
        {"id": 2, "name": "Bea", "about_me": "hiking"},
    ]
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=users))
    ) as http:
        runner = module.Runner(
            Chat(["Ada", "Bea", "Ada and Bea enjoy hiking."]),
            core().UserService(http=http),
            batch_size=1,
            workers=1,
        )
        result = runner.run("no", "Who enjoys hiking?")
    assert result["answer"] == "Ada and Bea enjoy hiking."
    assert result["candidates"] == [1, 2]
    assert result["batches"] == 2
    assert result["api_calls"] == 3
