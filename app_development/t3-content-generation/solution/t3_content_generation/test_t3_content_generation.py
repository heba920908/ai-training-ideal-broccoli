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
        if url.endswith("/voice.mp3"):
            import io
            import wave
            audio = io.BytesIO()
            with wave.open(audio, "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(24000)
                output.writeframes(b"\xe8\x03" * 2400)
            return FakeResponse(200, content=audio.getvalue())
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


def test_septima_ola_join_speech_inserts_timed_pauses(tmp_path: Path) -> None:
    from array import array
    import imageio_ffmpeg
    from t3_content_generation.t4 import septima_ola_intro as intro
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    tone = intro.run_ffmpeg(
        ffmpeg, "-f", "lavfi", "-i", "sine=frequency=440:duration=0.2",
        "-f", "wav", "pipe:1",
    )
    target = tmp_path / "joined.mp3"
    intro.join_speech([tone, tone, tone], target, ffmpeg)
    decoded = intro.run_ffmpeg(
        ffmpeg, "-i", str(target), "-f", "s16le", "-ar", "24000", "-ac", "1", "pipe:1",
    )
    samples = array("h", decoded)
    assert len(samples) / 24000 == pytest.approx(2.9, abs=0.03)
    for start, end in ((0.3, 0.9), (1.3, 2.6)):
        assert max(abs(sample) for sample in samples[int(start * 24000):int(end * 24000)]) < 5
    for start, end in ((0.03, 0.17), (1.03, 1.17), (2.73, 2.87)):
        assert max(abs(sample) for sample in samples[int(start * 24000):int(end * 24000)]) > 1000


@pytest.mark.parametrize("segments", [[], [b"invalid audio"]])
def test_septima_ola_join_rejects_invalid_audio(tmp_path: Path, segments: list[bytes]) -> None:
    import imageio_ffmpeg
    from t3_content_generation.t4 import septima_ola_intro as intro
    target = tmp_path / "joined.mp3"
    with pytest.raises((ValueError, RuntimeError)):
        intro.join_speech(segments, target, imageio_ffmpeg.get_ffmpeg_exe())
    assert not target.exists()
    assert not target.with_suffix(".tmp.mp3").exists()


def test_septima_ola_narration() -> None:
    from t3_content_generation.t4 import septima_ola_intro as intro
    assert all(place in intro.TEXT for place in ("Ciudad de México", "Valle de Chalco", "Coacalco", "Puerto Rico"))
    assert "Con ustedes" in intro.TEXT
    assert "Séptima Ola" in intro.TEXT
    assert "Que se escuche fuerte para" not in intro.TEXT


def test_septima_ola_fallback_and_files(client, monkeypatch, tmp_path: Path) -> None:
    from t3_content_generation.t4 import septima_ola_intro as intro
    attachment = {"type": "audio/mpeg", "url": "files/bucket/voice.mp3"}
    c, session = client({"tts-hd-001": FakeResponse(200, chat_reply(attachments=[attachment]))})
    c._models = {name: {} for name in ("text-only", "tts-hd-001", "tts-001")}
    monkeypatch.setattr(intro, "default_candidates", lambda *models: ["text-only", *models])

    def mix(clean, target, ffmpeg, background_audio=None):
        decoded = intro.run_ffmpeg(
            ffmpeg, "-i", str(clean), "-f", "s16le", "-ar", "24000", "-ac", "1", "pipe:1",
        )
        assert len(decoded) / 48000 == pytest.approx(6.2, abs=0.03)
        assert background_audio is None
        target.write_bytes(b"mixed-audio")

    monkeypatch.setattr(intro, "mix_intro", mix)
    saved = intro.main(str(tmp_path), client=c)
    assert saved["mix"].read_bytes() == b"mixed-audio"
    assert saved["text"].read_text(encoding="utf-8").strip() == intro.TEXT
    payloads = [call["json"] for call in session.calls if "/tts-hd-001/" in call["url"]]
    assert [payload["messages"][0]["content"] for payload in payloads] == list(intro.PHRASES)
    assert all(payload["custom_fields"]["configuration"] == {
        "voice": "nova", "instructions": intro.INSTRUCTIONS,
    } for payload in payloads)


def test_septima_ola_no_model_fails(client, monkeypatch, tmp_path: Path) -> None:
    from t3_content_generation.t4 import septima_ola_intro as intro
    c, _ = client()
    monkeypatch.setattr(intro, "default_candidates", lambda *models: ["missing"])
    with pytest.raises(RuntimeError, match="No suitable speech model"):
        intro.main(str(tmp_path), client=c)
    assert not list(tmp_path.glob("*.mp3"))


@pytest.mark.parametrize("background_duration", [None, 0.3, 9])
def test_septima_ola_real_mix(tmp_path: Path, background_duration: float | None) -> None:
    import subprocess
    import imageio_ffmpeg
    from t3_content_generation.t4 import septima_ola_intro as intro
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    clean, target = tmp_path / "clean.wav", tmp_path / "mix.mp3"
    subprocess.run([ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=1", str(clean)], check=True)
    background = None
    if background_duration is not None:
        background = tmp_path / "A2.wav"
        subprocess.run([ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                        f"sine=frequency=110:duration={background_duration}", str(background)], check=True)
        intro.mix_intro(clean, target, ffmpeg, background_audio=background)
    else:
        intro.mix_intro(clean, target, ffmpeg)
    decoded = subprocess.run([ffmpeg, "-v", "error", "-i", str(target), "-f", "s16le",
                              "-ar", "24000", "-ac", "1", "pipe:1"], capture_output=True, check=True).stdout
    assert 4 < len(decoded) / 48000 < 7
    assert any(decoded)
    assert target.stat().st_size > 1000
    if background_duration is not None:
        from array import array
        samples = array("h", decoded)
        assert max(abs(sample) for sample in samples) < 32767
        assert sum(abs(sample) for sample in samples[72000:84000]) > 1000


def test_septima_ola_background_is_quiet_but_audible(tmp_path: Path) -> None:
    from array import array
    import math
    import imageio_ffmpeg
    from t3_content_generation.t4 import septima_ola_intro as intro
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    clean, background, target = tmp_path / "silence.wav", tmp_path / "music.wav", tmp_path / "mix.mp3"
    intro.run_ffmpeg(ffmpeg, "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "1", str(clean))
    intro.run_ffmpeg(ffmpeg, "-f", "lavfi", "-i", "sine=frequency=110:duration=6", str(background))
    reference = intro.run_ffmpeg(
        ffmpeg, "-i", str(background), "-af",
        "atrim=duration=5,asetpts=PTS-STARTPTS,loudnorm=I=-32:TP=-9:LRA=7,aresample=44100",
        "-f", "f32le", "-ar", "44100", "-ac", "2", "pipe:1",
    )
    intro.mix_intro(clean, target, ffmpeg, background_audio=background)
    mixed = intro.run_ffmpeg(
        ffmpeg, "-i", str(target), "-f", "f32le", "-ar", "44100", "-ac", "2", "pipe:1",
    )
    levels = []
    for decoded in (reference, mixed):
        samples = array("f", decoded)[158760:194040]
        levels.append(math.sqrt(sum(sample * sample for sample in samples) / len(samples)))
    assert levels[0] > 0
    assert levels[1] / levels[0] == pytest.approx(0.25, rel=0.08)


@pytest.mark.parametrize("kind", ["missing", "corrupt", "empty"])
def test_septima_ola_invalid_background_before_api(client, tmp_path: Path, kind: str) -> None:
    import subprocess
    import imageio_ffmpeg
    from t3_content_generation.t4 import septima_ola_intro as intro
    background = tmp_path / "bad.wav"
    if kind == "corrupt":
        background.write_bytes(b"not audio")
    elif kind == "empty":
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", "-f", "lavfi",
                        "-i", "anullsrc=r=24000:cl=mono", "-t", "0", str(background)], check=True)
    c, session = client()
    with pytest.raises((ValueError, FileNotFoundError, RuntimeError)):
        intro.main(str(tmp_path / "out"), client=c, background_audio=background)
    assert not session.calls


def test_septima_ola_forwards_background(client, monkeypatch, tmp_path: Path) -> None:
    import subprocess
    import imageio_ffmpeg
    from t3_content_generation.t4 import septima_ola_intro as intro
    background = tmp_path / "A2.wav"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=110:duration=0.3", str(background)], check=True)
    attachment = {"type": "audio/mpeg", "url": "files/bucket/voice.mp3"}
    c, _ = client({"tts-hd-001": FakeResponse(200, chat_reply(attachments=[attachment]))})
    c._models = {"tts-hd-001": {}}
    monkeypatch.setattr(intro, "default_candidates", lambda *models: list(models))

    def mix(clean, target, ffmpeg, background_audio=None):
        assert background_audio == background
        target.write_bytes(b"mixed-audio")

    monkeypatch.setattr(intro, "mix_intro", mix)
    assert intro.main(str(tmp_path / "out"), client=c, background_audio=background)["mix"].exists()


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
