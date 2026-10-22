import importlib
import json

import httpx
import pytest


def adapter():
    return importlib.import_module("t5_rag_advanced.dial")


def test_discovery_and_configured_chat(monkeypatch):
    monkeypatch.setenv(
        "OPENAI_BASE_URL",
        "https://dial.example/openai/deployments/configured/chat/completions",
    )
    monkeypatch.setenv("OPENAI_MODEL", "configured")
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")

    def respond(request):
        assert request.headers["Api-Key"] == "test-placeholder"
        assert request.url.host == "dial.example"
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "a-vision-embedding"},
                        {"id": "text-embedding-test"},
                    ]
                },
            )
        payload = json.loads(request.content)
        if request.url.path.endswith("/embeddings"):
            assert payload == {
                "model": "text-embedding-test",
                "input": ["first", "second"],
            }
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"index": 1, "embedding": [0.0, 1.0]},
                        {"index": 0, "embedding": [1.0, 0.0]},
                    ]
                },
            )
        assert request.url.path == "/openai/deployments/configured/chat/completions"
        assert payload["model"] == "configured"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "manual answer"}}]}
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        client = adapter().DialClient.from_env(transport=transport)
        assert client.embed(["first", "second"]) == [[1.0, 0.0], [0.0, 1.0]]
        assert (
            client.complete([{"role": "user", "content": "question"}])
            == "manual answer"
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "http://dial.example/openai",
        "https://user:password@dial.example",
    ],
)
def test_rejects_unsafe_urls(url):
    with pytest.raises(ValueError):
        adapter().dial_root(url)


@pytest.mark.parametrize(
    "vectors", [[[0.0, 0.0]], [[float("nan"), 1.0]], [[1.0], [1.0, 2.0]], [[]]]
)
def test_invalid_vectors(vectors):
    with pytest.raises(ValueError):
        adapter().validate_vectors(vectors)


def test_missing_response_index():
    def respond(request):
        return httpx.Response(
            200, json={"data": [{"index": 1, "embedding": [1.0, 0.0]}]}
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        client = adapter().DialClient(
            "https://dial.example/openai",
            "configured",
            "test-placeholder",
            "text-embedding-test",
            transport,
        )
        with pytest.raises(ValueError, match="indices"):
            client.embed(["only input"])


def test_http_failure_does_not_expose_body():
    def respond(request):
        return httpx.Response(401, json={"error": "sensitive-response-marker"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        client = adapter().DialClient(
            "https://dial.example/openai",
            "configured",
            "test-placeholder",
            "text-embedding-test",
            transport,
        )
        with pytest.raises(RuntimeError, match="HTTP 401") as error:
            client.embed(["input"])
        assert "sensitive-response-marker" not in str(error.value)


def test_chunk_overlap():
    from t5_rag_advanced.utils.text import chunk_text

    assert chunk_text("abcdefghij", 5, 2) == ["abcde", "defgh", "ghij"]


@pytest.mark.parametrize("size, overlap", [(0, 0), (5, 5), (5, -1)])
def test_invalid_chunk_options(size, overlap):
    from t5_rag_advanced.utils.text import chunk_text

    with pytest.raises(ValueError):
        chunk_text("", size, overlap)


def test_metric_scores_and_operator_validation():
    from t5_rag_advanced.embeddings.text_processor import search_settings

    assert search_settings("cosine", 0.75) == ("<=>", 0.25)
    assert search_settings("euclidean", 0.5) == ("<->", 1.0)
    with pytest.raises(ValueError):
        search_settings("cosine; DROP TABLE vectors", 0.5)


class FixedEmbeddings:
    model_name = "deterministic-test"
    root = "https://dial.example/openai"

    def get_embeddings(self, inputs, dimensions=None):
        texts = [inputs] if isinstance(inputs, str) else inputs
        return {
            position: ([1.0, 0.0] if "clock" in text else [0.0, 1.0])
            for position, text in enumerate(texts)
        }


@pytest.fixture
def processor():
    from t5_rag_advanced.embeddings.text_processor import TextProcessor

    return TextProcessor(
        FixedEmbeddings(),
        {
            "host": "127.0.0.1",
            "port": 5433,
            "database": "t5_test",
            "user": "postgres",
            "password": "postgres",
        },
    )


class TestPostgres:
    def test_source_identity_filter_and_export(self, processor, tmp_path):
        manual = tmp_path / "manual.txt"
        manual.write_text("clock timer", encoding="utf-8")
        processor.process_text_file(manual, truncate=True)
        for mode in ("cosine", "euclidean"):
            assert processor.search("lemon", search_mode=mode, min_score=0.9) == []
        destination = tmp_path / "output" / "embeddings.json"
        processor.export_embeddings(destination)
        payload = json.loads(destination.read_text(encoding="utf-8"))
        assert payload["metadata"]["dimensions"] == 2
        assert payload["vectors"][0]["embedding"] == [1.0, 0.0]
        assert payload["vectors"][0]["text"] == "clock timer"
        manual.write_text("changed clock timer", encoding="utf-8")
        with pytest.raises(ValueError, match="reload"):
            processor.process_text_file(manual)

    def test_roundtrip_metrics_reuse_and_identity(self, processor, tmp_path):
        manual = tmp_path / "manual.txt"
        manual.write_text("clock time\n" + "odor lemon\n", encoding="utf-8")
        assert (
            processor.process_text_file(manual, chunk_size=11, overlap=0, truncate=True)
            == 2
        )
        assert processor.process_text_file(manual, chunk_size=11, overlap=0) == 2
        for mode in ("cosine", "euclidean"):
            results = processor.search(
                "clock", search_mode=mode, top_k=1, min_score=0.9
            )
            assert len(results) == 1
            assert "clock" in results[0]["text"]
            assert results[0]["score"] == pytest.approx(1.0)
            assert results[0]["distance"] == pytest.approx(0.0)
        processor.embeddings_client.model_name = "different-test-model"
        with pytest.raises(ValueError, match="reload"):
            processor.process_text_file(manual, chunk_size=11, overlap=0)
        processor.embeddings_client.model_name = "deterministic-test"

    def test_failed_reload_preserves_index(self, processor, tmp_path, monkeypatch):
        manual = tmp_path / "manual.txt"
        manual.write_text("clock timer", encoding="utf-8")
        processor.process_text_file(manual, truncate=True)

        def fail_insert(*args):
            raise RuntimeError("simulated insert failure")

        monkeypatch.setattr(processor, "_save_chunk", fail_insert)
        with pytest.raises(RuntimeError, match="simulated"):
            processor.process_text_file(manual, truncate=True)
        assert "clock" in processor.search("clock", min_score=0.9)[0]["text"]

    def test_dimension_mismatch_is_real_and_nondestructive(self, processor, tmp_path):
        import psycopg2

        manual = tmp_path / "manual.txt"
        manual.write_text("clock timer", encoding="utf-8")
        processor.process_text_file(manual, truncate=True)
        with pytest.raises(psycopg2.Error, match="dimensions"):
            processor.dimension_mismatch("clock")
        assert len(processor.search("clock", min_score=0.9)) == 1


def test_cli_rejects_invalid_options_before_network(monkeypatch):
    from t5_rag_advanced.app import main

    monkeypatch.setattr("sys.argv", ["app", "--overlap", "300", "--chunk-size", "300"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


def test_no_context_avoids_generation():
    from t5_rag_advanced.app import answer

    class EmptyProcessor:
        def search(self, *args, **kwargs):
            return []

    class NoChat:
        def get_completion(self, messages):
            raise AssertionError("No context must not trigger generation")

    assert "does not contain" in answer(
        "unrelated", EmptyProcessor(), NoChat(), "cosine", 5, 0.5
    )
