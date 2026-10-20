from t3_content_generation._dial_client import (
    DialClient, Resolution, asset, main_logger, output_dir,
)

# https://developers.openai.com/api/docs/guides/speech-to-text
# DIAL note: `/audio/transcriptions` (multipart/form-data) is a forbidden route. The mp3 is sent as an inline
# base64 `audio/mpeg` attachment to `/chat/completions`; the transcription is returned as message content.
# `whisper-1` is deployed on DIAL as `whisper-001`.

COMPARED_MODELS = ["whisper-001", "gpt-4o-transcribe"]


def transcribe(client: DialClient, model: str, file: str = "t3/audio_sample.mp3") -> str:
    message = {
        "role": "user",
        "content": "",
        "custom_content": {"attachments": [DialClient.attachment(asset(file), "audio/mpeg")]},
    }
    text = DialClient.content(client.chat(model, [message])).strip()
    if not text:
        raise ValueError("empty transcription")
    return text


def main(out_dir: str | None = None, client: DialClient | None = None) -> dict[str, Resolution]:
    out = output_dir(out_dir)
    client = client or DialClient(log=main_logger("t3_speech_to_text", out))
    results = {
        model: client.resolve(f"T3 STT {model}", [model], lambda m: transcribe(client, m), input_mime="audio/mpeg")
        for model in COMPARED_MODELS
    }
    client.log("\n📊 Comparison:")
    for model, resolution in results.items():
        client.log(f"  {model:<20} -> {resolution.result!r}")
    (out / "t3_transcriptions.md").write_text(
        "\n".join(f"- `{m}`: {r.result}" for m, r in results.items()) + "\n", encoding="utf-8")
    return results


if __name__ == "__main__":
    main()
