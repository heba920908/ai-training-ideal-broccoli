from t3_content_generation._dial_client import (
    DialClient, DialError, Resolution, default_candidates, main_logger, output_dir,
)


class Voice:
    alloy: str = 'alloy'
    ash: str = 'ash'
    ballad: str = 'ballad'
    coral: str = 'coral'
    echo: str = 'echo'
    fable: str = 'fable'
    nova: str = 'nova'
    onyx: str = 'onyx'
    sage: str = 'sage'
    shimmer: str = 'shimmer'


# https://developers.openai.com/api/docs/guides/text-to-speech
# DIAL notes:
#   - `/audio/speech` is a forbidden route; TTS deployments (`tts-001` = tts-1, `tts-hd-001` = tts-1-hd) answer
#     `/chat/completions` with an `audio/mpeg` attachment url.
#   - `gpt-4o-mini-tts` is not deployed, so `instructions` has no effect (tts-1 accepts but ignores it).
#   - voice/speed/instructions go into `custom_fields.configuration`; only tts-1 voices are allowed
#     (alloy, echo, fable, nova, onyx, shimmer). ash/ballad/coral/sage are rejected with HTTP 400.

TEXT = "Why can't we say that black is white?"
INSTRUCTIONS = "Speak in a cheerful and positive tone."
VOICES = [Voice.coral, Voice.nova, Voice.onyx]
CANDIDATES = default_candidates("tts-hd-001", "tts-001")


def speak(client: DialClient, model: str, voice: str, text: str = TEXT) -> bytes:
    response = client.chat(
        model,
        [{"role": "user", "content": text}],
        custom_fields={"configuration": {"voice": voice, "instructions": INSTRUCTIONS}},
    )
    audio = DialClient.attachments(response, "audio/")
    if not audio:
        raise ValueError(f"no audio attachment returned (text: {DialClient.content(response)[:120]!r})")
    return client.download(audio[0]["url"])


def main(out_dir: str | None = None, client: DialClient | None = None) -> dict[str, str]:
    out = output_dir(out_dir)
    client = client or DialClient(log=main_logger("t4_text_to_speech", out))
    resolution: Resolution = client.resolve(
        "T4 TTS", CANDIDATES, lambda m: speak(client, m, Voice.alloy))
    saved: dict[str, str] = {}
    if not resolution.model:
        return saved
    voices = {Voice.alloy: resolution.result}
    for voice in VOICES:
        client.log(f"\n🎙️ voice={voice}")
        try:
            voices[voice] = speak(client, resolution.model, voice)
        except DialError as e:
            client.log(f"⚠️ voice '{voice}' not supported by {resolution.model}: {e}")
    for voice, audio in voices.items():
        target = out / f"t4_speech_{resolution.model}_{voice}.mp3"
        target.write_bytes(audio)
        saved[voice] = target.name
        client.log(f"🔊 Saved {len(audio)} bytes -> {target.name}")
    return saved


if __name__ == "__main__":
    main()
