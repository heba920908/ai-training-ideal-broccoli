import base64
from dataclasses import dataclass

from t3_content_generation._dial_client import (
    DialClient, DialError, asset, default_candidates, main_logger, output_dir,
)
from t3_content_generation.t3.speech_to_text import transcribe
from t3_content_generation.t4.text_to_speech import Voice, speak

# https://developers.openai.com/api/docs/guides/audio#add-audio-to-your-existing-application
# DIAL notes:
#   - `gpt-4o-audio-preview` is not deployed. Native audio-in/audio-out (`input_audio` + `modalities=["text","audio"]`)
#     is attempted on up to 3 models; DIAL's gpt-4o rejects `input_audio` content blocks.
#   - Fallback pipeline (same outcome, 2 hops): an audio-understanding model (Gemini, accepts `*/*` attachments)
#     answers the spoken question as text, then `tts-001` voices the answer. `ballad` is not a tts-1 voice, so the
#     closest supported storyteller voice `fable` is used.

NATIVE_CANDIDATES = default_candidates("gpt-4o", "gpt-5.6-terra-2026-07-09")
UNDERSTANDING_CANDIDATES = default_candidates("gemini-3.8-flash", "gemini-3.5-flash")
TTS_MODEL = "tts-001"
REQUESTED_VOICE = Voice.ballad
FALLBACK_VOICE = Voice.fable
QUESTION_PROMPT = "Answer the question asked in this audio message in 2-3 concise sentences."


@dataclass
class SpeechAnswer:
    route: str
    text: str
    audio: bytes


def native(client: DialClient, model: str) -> SpeechAnswer:
    question = DialClient.attachment(asset("t5/question.mp3"), "audio/mpeg")["data"]
    response = client.chat(
        model,
        [{"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": question, "format": "mp3"}}]}],
        modalities=["text", "audio"],
        audio={"voice": REQUESTED_VOICE, "format": "mp3"},
    )
    audio = response["choices"][0]["message"].get("audio") or {}
    if not audio.get("data"):
        raise ValueError("no audio returned in message.audio")
    return SpeechAnswer(f"native:{model}", audio.get("transcript", ""), base64.b64decode(audio["data"]))


def understand(client: DialClient, model: str) -> str:
    message = {
        "role": "user",
        "content": QUESTION_PROMPT,
        "custom_content": {"attachments": [DialClient.attachment(asset("t5/question.mp3"), "audio/mpeg")]},
    }
    answer = DialClient.content(client.chat(model, [message])).strip()
    if not answer:
        raise ValueError("empty answer")
    return answer


def main(out_dir: str | None = None, client: DialClient | None = None) -> SpeechAnswer | None:
    out = output_dir(out_dir)
    client = client or DialClient(log=main_logger("t5_speech_to_speech", out))

    resolution = client.resolve("T5 STS native", NATIVE_CANDIDATES, lambda m: native(client, m))
    if resolution.model:
        answer: SpeechAnswer = resolution.result
    else:
        client.log("\n↪️ Falling back to pipeline: audio understanding -> TTS")
        client.log(f"🎧 Question transcript (gpt-4o-transcribe): {transcribe(client, 'gpt-4o-transcribe', 't5/question.mp3')!r}")
        text_res = client.resolve(
            "T5 STS understanding", UNDERSTANDING_CANDIDATES, lambda m: understand(client, m), input_mime="audio/mpeg")
        if not text_res.model:
            return None
        try:
            audio = speak(client, TTS_MODEL, REQUESTED_VOICE, text_res.result)
            voice = REQUESTED_VOICE
        except DialError as e:
            client.log(f"⚠️ voice '{REQUESTED_VOICE}' rejected ({e}); using '{FALLBACK_VOICE}'")
            audio = speak(client, TTS_MODEL, FALLBACK_VOICE, text_res.result)
            voice = FALLBACK_VOICE
        answer = SpeechAnswer(f"pipeline:{text_res.model}+{TTS_MODEL}({voice})", text_res.result, audio)

    target = out / "t5_answer.mp3"
    target.write_bytes(answer.audio)
    (out / "t5_answer.md").write_text(f"<!-- route: {answer.route} -->\n{answer.text}\n", encoding="utf-8")
    client.log(f"\n💬 Answer [{answer.route}]: {answer.text}\n🔊 Saved {len(answer.audio)} bytes -> {target.name}")
    return answer


if __name__ == "__main__":
    main()
