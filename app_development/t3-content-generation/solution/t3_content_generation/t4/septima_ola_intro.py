"""T4-1: Spanish concert introduction with locally mixed atmospheric effects."""

import argparse
import math
from pathlib import Path
import shutil
import subprocess

import imageio_ffmpeg

from t3_content_generation._dial_client import (
    DialClient, default_candidates, main_logger, output_dir,
)

PHRASES = (
    "Buenas noches! ¡Que alegr\u00eda compartir esta noche con ustedes!",
    "Desde Ciudad de M\u00e9xico, Valle de Chalco, Coacalco y Puerto Rico, llega una ola de ritmo, alma y libertad!",
    "La música marca el pulso. El jazz, el reggae y la buena vibra abren el horizonte y llega una ola de ritmo, alma y libertad!",
    "Con ustedes!",
    "S\u00e9ptima Ola!",
)
TEXT = "\n\n".join(PHRASES)
INSTRUCTIONS = (
    "Habla en espa\u00f1ol latino con un tono c\u00e1lido, alegre y acogedor, "
    "como quien presenta un concierto y recibe con cari\u00f1o a su gente. "
    "Deja que se escuche una sonrisa en tu voz y transmite alegr\u00eda genuina al saludar. "
    "Aumenta la emoci\u00f3n de forma natural, sin gritar ni exagerar. "
    "Pronuncia con claridad y conserva una entonaci\u00f3n natural. "
)
VOICES = ("alloy", "echo", "fable", "nova", "onyx", "shimmer")


def run_ffmpeg(ffmpeg: str, *args: str, input_data: bytes | None = None) -> bytes:
    result = subprocess.run(
        [ffmpeg, "-nostdin", "-v", "error", *args], capture_output=True, input=input_data,
    )
    if result.returncode:
        raise RuntimeError(f"FFmpeg failed: {result.stderr.decode(errors='replace')[-1500:]}")
    return result.stdout


def speak(client: DialClient, model: str, voice: str, text: str = TEXT, speed: float = 1.0) -> bytes:
    response = client.chat(
        model, [{"role": "user", "content": text}],
        custom_fields={"configuration": {"voice": voice, "speed": speed, "instructions": INSTRUCTIONS}},
    )
    audio = DialClient.attachments(response, "audio/")
    if not audio:
        raise ValueError("No audio attachment returned")
    data = client.download(audio[0]["url"])
    if not data:
        raise ValueError("Empty audio attachment")
    return data


def join_speech(segments: list[bytes], target: Path, ffmpeg: str) -> None:
    if not segments:
        raise ValueError("No speech segments to join")
    pcm = bytearray()
    for index, segment in enumerate(segments):
        decoded = run_ffmpeg(
            ffmpeg, "-i", "pipe:0", "-f", "s16le", "-ar", "24000", "-ac", "1", "pipe:1",
            input_data=segment,
        )
        if not decoded:
            raise ValueError("Speech segment contains no decodable audio")
        pcm.extend(decoded)
        if index < len(segments) - 1:
            pause = 1.5 if index == len(segments) - 2 else 0.8
            pcm.extend(b"\x00" * round(pause * 24000) * 2)
    temporary = target.with_suffix(".tmp.mp3")
    try:
        run_ffmpeg(
            ffmpeg, "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", "pipe:0",
            "-c:a", "libmp3lame", "-b:a", "192k", str(temporary), input_data=bytes(pcm),
        )
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def validate_background(background_audio: str | Path, ffmpeg: str) -> Path:
    background = Path(background_audio).expanduser()
    if not background.is_file():
        raise FileNotFoundError(f"Background audio file not found: {background}")
    pcm = run_ffmpeg(
        ffmpeg, "-i", str(background), "-map", "0:a:0", "-t", "0.1",
        "-f", "s16le", "-ar", "24000", "-ac", "1", "pipe:1",
    )
    if not pcm:
        raise ValueError(f"Background contains no decodable audio: {background}")
    return background


def mix_intro(
    clean: Path, target: Path, ffmpeg: str, background_audio: str | Path | None = None,
    pitch_semitones: float = 2.0,
) -> None:
    if not math.isfinite(pitch_semitones) or not -12 <= pitch_semitones <= 12:
        raise ValueError("Pitch must be between -12 and 12 semitones")
    background = validate_background(background_audio, ffmpeg) if background_audio is not None else None
    pcm = run_ffmpeg(ffmpeg, "-i", str(clean), "-f", "s16le", "-ar", "24000", "-ac", "1", "pipe:1")
    duration = len(pcm) / 48000
    if duration <= 0:
        raise ValueError("Speech contains no decodable audio")
    total = duration + 4
    pitch_factor = 2 ** (pitch_semitones / 12)
    voice_filters = (
        f"[0:a]aresample=44100,asetrate={44100 * pitch_factor},"
        f"aresample=44100,atempo={1 / pitch_factor},"
        "aecho=0.8:0.88:180|360:0.16|0.08,adelay=1500:all=1[voice];"
    )
    if background is None:
        background_inputs = [
            "-f", "lavfi", "-i", f"anoisesrc=color=pink:amplitude=0.09:sample_rate=44100:duration={total}:seed=7",
            "-f", "lavfi", "-i", f"sine=frequency=55:sample_rate=44100:duration={total}",
            "-f", "lavfi", "-i", f"sine=frequency=82.4:sample_rate=44100:duration={total}",
        ]
        background_filters = (
            "[1:a]lowpass=f=650,highpass=f=90,tremolo=f=0.25:d=0.8,"
            f"volume=0.22,afade=t=in:d=1.5,afade=t=out:st={total - 2}:d=2[swell];"
            f"[2:a]volume=0.3,afade=t=in:d=1.5,afade=t=out:st={total - 2}:d=2[bass];"
            f"[3:a]volume=0.15,afade=t=in:d=2,afade=t=out:st={total - 2}:d=2[tone];"
            "[voice][swell][bass][tone]amix=inputs=4:duration=longest:normalize=0,"
        )
    else:
        background_inputs = ["-stream_loop", "-1", "-i", str(background)]
        background_filters = (
            f"[1:a:0]atrim=duration={total},asetpts=PTS-STARTPTS,"
            "loudnorm=I=-32:TP=-9:LRA=7,aresample=44100,volume=0.4,"
            f"afade=t=in:d=1.5,afade=t=out:st={total - 2}:d=2[background];"
            "[voice][background]amix=inputs=2:duration=longest:normalize=0,"
        )
    filters = voice_filters + background_filters + (
        f"alimiter=limit=0.95:level=0,afade=t=out:st={total - 1}:d=1[out]"
    )
    temporary = target.with_suffix(".tmp.mp3")
    try:
        run_ffmpeg(
            ffmpeg, "-y", "-i", str(clean),
            *background_inputs,
            "-filter_complex", filters, "-map", "[out]", "-t", str(total),
            "-ac", "2", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k", str(temporary),
        )
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def main(
    out_dir: str | None = None, client: DialClient | None = None, voice: str = "nova",
    background_audio: str | Path | None = None,
    speed: float = 1.0, pitch_semitones: float = 2.0,
) -> dict[str, Path]:
    if voice not in VOICES:
        raise ValueError(f"Unsupported voice: {voice}. Choose from {', '.join(VOICES)}")
    if not math.isfinite(speed) or not 0.25 <= speed <= 4:
        raise ValueError("Speed must be between 0.25 and 4.0")
    if not math.isfinite(pitch_semitones) or not -12 <= pitch_semitones <= 12:
        raise ValueError("Pitch must be between -12 and 12 semitones")
    ffmpeg = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()
    run_ffmpeg(ffmpeg, "-version")
    background = validate_background(background_audio, ffmpeg) if background_audio is not None else None
    out = output_dir(out_dir)
    own_logger = main_logger("t4_1_septima_ola", out) if client is None else None
    try:
        client = client or DialClient(log=own_logger)
        resolution = client.resolve(
            "T4-1 Septima Ola", default_candidates("tts-hd-001", "tts-001"),
            lambda model: speak(client, model, voice, PHRASES[0], speed=speed),
        )
        if not resolution.model:
            raise RuntimeError("No suitable speech model returned audio; see the DIAL attempt log")
        saved = {
            "clean": out / "t4_1_septima_ola_clean.mp3",
            "mix": out / "t4_1_septima_ola.mp3",
            "text": out / "t4_1_septima_ola.txt",
        }
        segments = [resolution.result]
        for phrase in PHRASES[1:]:
            segments.append(speak(client, resolution.model, voice, phrase, speed=speed))
        join_speech(segments, saved["clean"], ffmpeg)
        saved["text"].write_text(TEXT + "\n", encoding="utf-8")
        mix_intro(saved["clean"], saved["mix"], ffmpeg, background_audio=background, pitch_semitones=pitch_semitones)
        client.log(f"Model: {resolution.model}; voice: {voice}; background: {background or 'synthetic effects'}")
        client.log(f"Speed: {speed}; pitch shift: {pitch_semitones:+g} semitones")
        client.log("Inserted pauses: 0.8 s between phrases; 1.5 s before the band name")
        for kind, path in saved.items():
            client.log(f"Saved {kind}: {path}")
        return saved
    finally:
        if own_logger:
            own_logger.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--output-dir", help="Directory for clean speech, final mix, narration, and log")
    parser.add_argument("--voice", choices=VOICES, default="nova", help="DIAL speech voice")
    parser.add_argument("--speed", type=float, default=1.0, help="DIAL speech speed multiplier (0.25 to 4.0)")
    parser.add_argument("--pitch-semitones", type=float, default=2.0, help="Local voice pitch shift (-12 to 12; 0 disables)")
    parser.add_argument("--background-audio", type=Path, help="Local audio file to loop beneath the voice instead of synthetic effects")
    args = parser.parse_args()
    main(args.output_dir, voice=args.voice, background_audio=args.background_audio,
         speed=args.speed, pitch_semitones=args.pitch_semitones)