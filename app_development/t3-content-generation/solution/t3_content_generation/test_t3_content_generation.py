import json
import os
from pathlib import Path
from typing import Any

import pytest

import t3_content_generation._dial_client as dial
from t3_content_generation._dial_client import MAX_ATTEMPTS, DialClient, Logger, dial_root, redact
from t3_content_generation.t2 import gpt_image_generation

FAKE_KEY = "fake-key-9999"
ROOT = "https://ai-proxy.lab.epam.com/openai"
MODELS = {
    "data": [
        {"id": "text-only", "input_attachment_types": None},
        {"id": "vision", "input_attachment_types": ["image/*"]},
        {"id": "image-gen", "input_attachment_types": ["image/*"]},
        {"id": "stt", "input_attachment_types": ["audio/mpeg"]},
        {"id": "omni", "input_attachment_types": ["*/*"]},
    ]
}


class FakeResponse:
    def __init__(self, status: int, payload: Any = None, content: bytes = b""):
        self.status_code = status
        self._payload = payload
        self.content = content
        self.text = json.dumps(payload) if payload is not None else content.decode(errors="ignore")

    def json(self) -> Any:
        return self._payload


class FakeSession:
    """Records requests; ``replies`` maps a deployment name to its chat response."""

    def __init__(self, replies: dict[str, FakeResponse] | None = None):
        self.replies = replies or {}
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, headers: dict, timeout: int) -> FakeResponse:
        self.calls.append({"method": "GET", "url": url, "headers": headers})
        if url.endswith("/openai/models"):
            return FakeResponse(200, MODELS)
        return FakeResponse(200, content=b"\x89PNG-bytes")

    def post(self, url: str, headers: dict, json: dict, timeout: int) -> FakeResponse:
        self.calls.append({"method": "POST", "url": url, "headers": headers, "json": json})
        model = url.split("/deployments/")[1].split("/")[0]
        return self.replies.get(model, FakeResponse(200, chat_reply("plain text")))


def chat_reply(content: str = "", attachments: list[dict] | None = None) -> dict:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if attachments:
        message["custom_content"] = {"attachments": attachments}
    return {"choices": [{"message": message}]}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(dial, "OPENAI_API_KEY", FAKE_KEY)

    def build(replies: dict[str, FakeResponse] | None = None) -> tuple[DialClient, FakeSession]:
        session = FakeSession(replies)
        c = DialClient(log=Logger(tmp_path / "test.log"), session=session, base_url=f"{ROOT}/deployments/any-model")
        return c, session

    return build


def test_dial_root_strips_deployment_path() -> None:
    assert dial_root(f"{ROOT}/deployments/DeepSeek-V4/") == ROOT
    assert dial_root(ROOT) == ROOT


def test_redact_hides_key_bucket_and_base64(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dial, "OPENAI_API_KEY", FAKE_KEY)
    text = redact(f"key={FAKE_KEY} url=files/6QQKs3wcUDfrfeFfP9MPJpvVRPkeyim/appdata/x.png data: {'A' * 400}")
    assert FAKE_KEY not in text
    assert "files/<bucket>/appdata/x.png" in text
    assert "<400 b64 chars>" in text


def test_chat_uses_api_key_header_and_deployment_endpoint(client) -> None:
    c, session = client()
    c.chat("vision", [{"role": "user", "content": "hi"}])
    post = session.calls[-1]
    assert post["url"] == f"{ROOT}/deployments/vision/chat/completions"
    assert post["headers"] == {"Api-Key": FAKE_KEY}


def test_resolve_skips_unsuitable_models_by_metadata(client) -> None:
    c, session = client()
    res = c.resolve("t", ["text-only", "missing-model", "vision"], lambda m: m.upper(), input_mime="image/png")
    assert res.model == "vision" and res.result == "VISION"
    assert [a.ok for a in res.attempts] == [False, False, True]
    assert "does not accept" in res.attempts[0].reason
    assert "not deployed" in res.attempts[1].reason
    assert not [call for call in session.calls if call["method"] == "POST"]


def test_resolve_stops_after_max_attempts(client) -> None:
    c, _ = client()
    tried: list[str] = []

    def always_fail(model: str) -> None:
        tried.append(model)
        raise ValueError("unsuitable")

    res = c.resolve("t", ["vision", "image-gen", "stt", "omni"], always_fail)
    assert res.model is None
    assert len(res.attempts) == MAX_ATTEMPTS
    assert tried == ["vision", "image-gen", "stt"]


def test_image_generation_rejects_text_only_reply_then_downloads_attachment(client) -> None:
    attachment = {"type": "image/png", "title": "Image", "url": "files/bucket/appdata/img.png"}
    c, session = client({"image-gen": FakeResponse(200, chat_reply(attachments=[attachment]))})
    res = c.resolve("t2", ["text-only", "image-gen"], lambda m: gpt_image_generation.generate(c, m))
    assert res.model == "image-gen"
    assert res.result == b"\x89PNG-bytes"
    assert "no image attachment" in res.attempts[0].reason
    assert session.calls[-1]["url"] == "https://ai-proxy.lab.epam.com/v1/files/bucket/appdata/img.png"


def test_attachment_is_inline_base64(tmp_path: Path) -> None:
    f = tmp_path / "q.mp3"
    f.write_bytes(b"ID3")
    assert DialClient.attachment(f, "audio/mpeg") == {"type": "audio/mpeg", "title": "q.mp3", "data": "SUQz"}


live = pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="needs OPENAI_* from .env")


@live
def test_live_t1_image_analysis(tmp_path: Path) -> None:
    from t3_content_generation.t1 import image_analysis
    assert image_analysis.main(str(tmp_path)).model


@live
def test_live_t2_image_generation_and_edit(tmp_path: Path) -> None:
    from t3_content_generation.t2 import gpt_image_edit
    assert gpt_image_generation.main(str(tmp_path)).model
    assert gpt_image_edit.main(str(tmp_path)).model
    assert len(list(tmp_path.glob("t2_*.png"))) == 2


@live
def test_live_t3_speech_to_text(tmp_path: Path) -> None:
    from t3_content_generation.t3 import speech_to_text
    results = speech_to_text.main(str(tmp_path))
    assert all("discord" in (r.result or "").lower() for r in results.values())


@live
def test_live_t4_text_to_speech(tmp_path: Path) -> None:
    from t3_content_generation.t4 import text_to_speech
    saved = text_to_speech.main(str(tmp_path))
    assert "coral" not in saved and {"alloy", "nova", "onyx"} <= saved.keys()


@live
def test_live_t5_speech_to_speech(tmp_path: Path) -> None:
    from t3_content_generation.t5 import speech_to_speech
    answer = speech_to_speech.main(str(tmp_path))
    assert answer and answer.audio and answer.text
