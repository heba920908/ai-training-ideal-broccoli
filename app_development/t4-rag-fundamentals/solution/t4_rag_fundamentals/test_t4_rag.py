from types import SimpleNamespace

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS

from t4_rag_fundamentals.app import MicrowaveRAG, create_clients, dial_root, relevance_score


class OfflineEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text):
        return [1.0, 0.0] if "clock" in text.lower() else [0.0, 1.0]


def test_retrieval_filters_irrelevant_chunks():
    rag = MicrowaveRAG.__new__(MicrowaveRAG)
    rag.vectorstore = FAISS.from_documents(
        [Document(page_content="Set the clock."), Document(page_content="Clean the oven.")],
        OfflineEmbeddings(),
        normalize_L2=True,
        relevance_score_fn=relevance_score,
    )
    assert rag.retrieve_context("clock", k=2, score=0.5) == "Set the clock."


def test_prompt_and_generation_preserve_context_and_question():
    class RecordingChat:
        def invoke(self, messages):
            assert messages[0].type == "system"
            assert "only" in messages[0].content.lower()
            assert "RAG CONTEXT" in messages[1].content
            assert "Set the clock." in messages[1].content
            assert "How do I set the clock?" in messages[1].content
            return SimpleNamespace(content="Press CLOCK.")

    rag = MicrowaveRAG.__new__(MicrowaveRAG)
    rag.llm_client = RecordingChat()
    prompt = rag.augment_prompt("How do I set the clock?", "Set the clock.")
    assert rag.generate_answer(prompt) == "Press CLOCK."


def test_index_is_created_and_reused_without_reembedding(tmp_path):
    manual = tmp_path / "manual.txt"
    manual.write_text("Set the clock.\n\nClean the oven.", encoding="utf-8")
    index = tmp_path / "index"
    first = MicrowaveRAG(OfflineEmbeddings(), None, manual_path=manual, index_path=index)
    assert (index / "index.faiss").is_file()
    assert first.retrieve_context("clock", score=0.5)

    class QueryOnlyEmbeddings(OfflineEmbeddings):
        def embed_documents(self, texts):
            pytest.fail("Loading an existing index must not embed documents again")

    second = MicrowaveRAG(QueryOnlyEmbeddings(), None, manual_path=manual, index_path=index)
    assert second.retrieve_context("clock", score=0.5)


def test_empty_context_prompt_does_not_invent_manual_information():
    rag = MicrowaveRAG.__new__(MicrowaveRAG)
    prompt = rag.augment_prompt("What is DIALX?", "")
    assert "No relevant manual context" in prompt


@pytest.mark.parametrize("k, score", [(0, 0.3), (4, -0.1), (4, 1.1)])
def test_invalid_retrieval_settings_are_rejected(k, score):
    rag = MicrowaveRAG.__new__(MicrowaveRAG)
    with pytest.raises(ValueError):
        rag.retrieve_context("clock", k=k, score=score)


@pytest.mark.parametrize("distance, expected", [(0, 1), (1, 0.5), (2, 0), (4, 0)])
def test_normalized_squared_l2_is_converted_to_bounded_cosine(distance, expected):
    assert relevance_score(distance) == expected


def test_dial_root_removes_deployment_and_completion_route():
    assert dial_root("https://dial.example/openai/deployments/custom/chat/completions") == "https://dial.example/openai"


@pytest.mark.parametrize("url", ["https://api.openai.com/v1", "https://openai.com", "http://dial.example", "https://user:password@dial.example"])
def test_non_dial_or_credential_bearing_hosts_are_rejected(url):
    with pytest.raises(ValueError):
        dial_root(url)


def test_discovery_prefers_text_embeddings_over_vision(monkeypatch):
    import httpx

    monkeypatch.setenv("OPENAI_BASE_URL", "https://dial.example/openai/deployments/chat")
    monkeypatch.setenv("OPENAI_MODEL", "custom-chat")
    monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
    response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://dial.example/openai/models"),
        json={"data": [{"id": "azure-vision-embeddings"}, {"id": "text-embedding-custom"}]},
    )
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: response)
    embeddings, chat = create_clients()
    assert embeddings.model == "text-embedding-custom"
    assert chat.model_name == "custom-chat"