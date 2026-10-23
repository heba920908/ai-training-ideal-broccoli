# T3: Content Generation

Work with multimodal AI APIs to generate and process images, speech, and audio: vision (image → text),
image generation and editing (text/image → image), speech-to-text, text-to-speech, and speech-to-speech.

> **Scope note:** All five OpenAI tasks run through the OpenAI-compatible **EPAM DIAL** proxy. The Gemini/Imagen
> bonus is covered indirectly (`gemini-3.1-flash-image` is the image fallback, `gemini-3.8-flash` handles audio
> understanding in T5); the native `generativelanguage.googleapis.com` calls are skipped.

## Source

| Language | Repository | Task folder |
|----------|------------|-------------|
| Python (used here) | <https://github.com/epam/ai-applications-development-from-api-to-agents> | `t3_content_generation` |
| Java | <https://github.com/epam/java-ai-applications-development-from-api-to-agents> | `t3.content.generation` |
| JS | <https://github.com/epam/js-ai-applications-development-from-api-to-agents> | `t3_content_generation` |

Course files (fork clone, local only):
[`workspace/ai-applications-development-from-api-to-agents/t3_content_generation/`](../../workspace/ai-applications-development-from-api-to-agents/t3_content_generation/)
(input assets `logo.png`, `audio_sample.mp3`, `question.mp3` are read from there).

## Provider: EPAM DIAL instead of OpenAI

```bash
set -a; source .env; set +a   # exports OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_API_KEY
```

DIAL behaves differently from `api.openai.com` for multimodal models. These were the findings during probing:

| Course endpoint | On DIAL | Adaptation |
|-----------------|---------|------------|
| `/v1/chat/completions` + `image_url` parts | ✅ works on vision deployments | unchanged (URL + `data:image/png;base64,...`) |
| `/v1/images/generations` | ❌ `403 Forbidden route` | `chat/completions` → image returned as `custom_content.attachments[].url` |
| `/v1/images/edits` (multipart) | ❌ `403 Forbidden route` | input image sent as inline base64 DIAL attachment |
| `/v1/audio/transcriptions` (multipart) | ❌ `403 Forbidden route` | mp3 sent as `audio/mpeg` attachment; transcript in `message.content` |
| `/v1/audio/speech` | ❌ `403 Forbidden route` | `chat/completions` → `audio/mpeg` attachment; `voice` via `custom_fields.configuration` |
| `/v1/chat/completions` + `input_audio` | ❌ no `gpt-4o-audio-preview` deployment | pipeline: audio-understanding model → TTS |

Other adaptations:

- `_dial_client.py` derives the DIAL root from `OPENAI_BASE_URL`
  (`.../openai/deployments/<model>` → `.../openai`), calls `.../deployments/<model>/chat/completions`, and downloads
  attachments from `GET {host}/v1/{url}`. Auth uses the `Api-Key` header.
- **Model resolution:** each task tries `OPENAI_MODEL` from `.env` first, then DIAL deployments found suitable,
  **max 3 attempts per task**. A candidate is rejected when it is not deployed, when its `input_attachment_types`
  (from `GET /openai/models`) does not accept the input MIME type, or when the call fails or returns the wrong
  output (for example text instead of an image).
- Logs redact the API key, the per-key DIAL bucket id (`files/<bucket>/...`), and long base64 payloads.

## Tasks

**1. Image Analysis (Vision)**: [t1/image_analysis.py](../../workspace/ai-applications-development-from-api-to-agents/t3_content_generation/t1/image_analysis.py)
- [x] Analyse the remote elephant URL and local `logo.png` (base64) in a single message
- [x] Ask the model to generate a poem based on both images

**2. Image Generation**: [t2/gpt_image_generation.py](../../workspace/ai-applications-development-from-api-to-agents/t3_content_generation/t2/gpt_image_generation.py), [t2/gpt_image_edit.py](../../workspace/ai-applications-development-from-api-to-agents/t3_content_generation/t2/gpt_image_edit.py)
- [x] Generate `"Smiling catdog"` with `gpt-image-2`, decode and save locally
- [x] Edit `logo.png` with `gpt-image-2` adding sparkles / glow / mystical aura, save locally

**3. Speech to Text**: [t3/speech_to_text.py](../../workspace/ai-applications-development-from-api-to-agents/t3_content_generation/t3/speech_to_text.py)
- [x] Transcribe `audio_sample.mp3`
- [x] Compare `whisper-1` (`whisper-001` on DIAL) and `gpt-4o-transcribe`

**4. Text to Speech**: [t4/text_to_speech.py](../../workspace/ai-applications-development-from-api-to-agents/t3_content_generation/t4/text_to_speech.py)
- [x] Convert text to speech and save `.mp3` files
- [x] Experiment with voices from the `Voice` class (`alloy`, `nova`, `onyx`; `coral` rejected by DIAL)
- [x] Send `instructions` (accepted, but no effect: `gpt-4o-mini-tts` is not deployed, only `tts-1`/`tts-1-hd`)

**5. Speech to Speech**: [t5/speech_to_speech.py](../../workspace/ai-applications-development-from-api-to-agents/t3_content_generation/t5/speech_to_speech.py)
- [x] Send `question.mp3` as base64 `input_audio` with `modalities=["text","audio"]`; all native attempts rejected
- [x] Fallback: answer the spoken question via `gemini-3.8-flash` and voice it with `tts-001` (`ballad` → `fable`)
- [x] Save the answer as `.mp3`

**4-1. Septima Ola introduction**:
[script](solution/t3_content_generation/t4/septima_ola_intro.py),
[run instructions](solution/t3_content_generation/README.md#4-1-septima-ola-spanish-concert-introduction)
- [x] Approved Spanish narration naming CDMX (spoken as Ciudad de México), Valle de Chalco, Coacalco, and Puerto Rico
- [x] DIAL speech plus locally synthesized swell, bass, and echo using `imageio-ffmpeg` (no system install)
- [x] Preserve clean speech, final MP3 mix, and UTF-8 narration in git-ignored output
- [x] Default to `nova`; optionally replace the synthetic bed using `--background-audio`
- [x] Generate a pulsing A2 (110 Hz) WAV and mix it with existing Nova speech without another DIAL request

**Bonus: Gemini Image Generation**
- [ ] Native Gemini / Imagen 4 API calls skipped (no `GEMINI_API_KEY`); DIAL's `gemini-3.1-flash-image` is the
  configured image fallback

## Model findings (EPAM DIAL)

| Task | Course model | Attempts (max 3) | Selected |
|------|--------------|------------------|----------|
| T1 vision | `gpt-5.6-terra` | `OPENAI_MODEL` (DeepSeek: no `image/*` input) ❌ → `gpt-5.6-terra-2026-07-09` ✅ | `gpt-5.6-terra-2026-07-09` |
| T2 generate | `gpt-image-2` | DeepSeek (wrote a *story* instead of an image) ❌ → `gpt-image-2-2026-04-21` ✅ | `gpt-image-2-2026-04-21` |
| T2 edit | `gpt-image-2` | DeepSeek (no `image/*` input) ❌ → `gpt-image-2-2026-04-21` ✅ | `gpt-image-2-2026-04-21` |
| T3 STT | `whisper-1`, `gpt-4o-transcribe` | both compared directly | `whisper-001`, `gpt-4o-transcribe` |
| T4 TTS | `gpt-4o-mini-tts` | DeepSeek (text reply, no audio) ❌ → `tts-hd-001` ✅ | `tts-hd-001` |
| T5 STS native | `gpt-4o-audio-preview` | DeepSeek `400` ❌ → `gpt-4o` `400` (only text/image_url blocks) ❌ → `gpt-5.6-terra` `422 Audio messages aren't supported` ❌ | none |
| T5 STS pipeline | n/a | DeepSeek (no audio input) ❌ → `gemini-3.8-flash` ✅ + `tts-001` | `gemini-3.8-flash` + `tts-001` |

Other suitable deployments discovered via `GET /openai/models`: `gpt-4o`, `gpt-5.4*` (vision);
`gpt-image-1-mini`, `gpt-image-1.5`, `gpt-image-2.5-*`, `gemini-*-image`, `stability.*` (image);
`tts-001` (TTS); `gemini-*` with `*/*` attachments (audio understanding); `veo-3.1-*` (video).

## How to run

Export the root `.env` first:

```bash
set -a; source .env; set +a
```

### Option A: from `app_development/t3-content-generation/solution` (`uv run`)

Run all steps; images, audio, and `*.log` files land in the git-ignored
`app_development/t3-content-generation/output/`:

```bash
uv run --with requests --directory app_development/t3-content-generation/solution \
  python -m t3_content_generation.run_all --step all
```

Run a single step (`t1`, `t2`, `t3`, `t4`, `t5`), optionally with a custom output dir:

```bash
uv run --with requests --directory app_development/t3-content-generation/solution \
  python -m t3_content_generation.run_all --step t5 --output-dir /tmp/t3-out
```

### Option B: from the course fork

```bash
cd workspace/ai-applications-development-from-api-to-agents
set -a; source ../../.env; set +a
uv run --with requests python -m t3_content_generation.t1.image_analysis
uv run --with requests python -m t3_content_generation.run_all --step all --output-dir ../t3-output
```

### Option C: `pytest`

Offline unit tests (DIAL root derivation, `Api-Key` header, redaction, metadata-based suitability, 3-attempt limit,
attachment download):

```bash
env -u OPENAI_API_KEY uv run --with requests --with pytest --with imageio-ffmpeg \
  --directory app_development/t3-content-generation/solution \
  python -m pytest t3_content_generation/test_t3_content_generation.py -v
```

Live tests (one per task, writes into a pytest `tmp_path`):

```bash
set -a; source .env; set +a
uv run --with requests --with pytest --directory app_development/t3-content-generation/solution \
  python -m pytest -s t3_content_generation/test_t3_content_generation.py -k live
```

## Deliverables

- `solution/t3_content_generation/`: implemented `t1`–`t5` tasks, `_dial_client.py` (DIAL adapter + model
  resolution), `run_all.py` runner, and `test_t3_content_generation.py`. The upstream course `README.md` and
  `_openai_client.py` are retained; the README adds the standalone T4-1 run instructions.
- `solution/commons/constants.py`: model-agnostic `OPENAI_*` configuration (same as T1/T2).
- `output/` (git-ignored): `t1_poem.md`, `t2_catdog_*.png`, `t2_logo_magic_*.png`, `t3_transcriptions.md`,
  `t4_speech_*_<voice>.mp3`, `t5_answer.{mp3,md}`, plus one `<task>.log` per script with the full
  request/response trail.

## Results / notes

Live run against EPAM DIAL (`OPENAI_MODEL=DeepSeek-V4-Flash-2026-04-23`, key `<redacted>`).

- **T4-1 Septima Ola (2026-10-23)**: the configured text model returned no audio;
  `tts-hd-001` with `onyx` produced the approved Spanish introduction. Clean speech:
  15.14 s (323,218 bytes); final stereo MP3 with locally mixed effects: 19.14 s
  (460,843 bytes). Both decoded successfully with nonzero signal and no clipped
  samples. Offline suite: 11 passed, 5 live tests skipped. Accent, pronunciation,
  and artistic quality still require human listening before stage playback.
- **T4-1 optional background extension (2026-10-23)**: `nova` is now the API/CLI
  default. Installed FFmpeg is preferred with bundled fallback. The documented
  command generated `a2_110hz.wav` (12.00 s; measured 110.0 Hz). Existing Nova
  speech was remixed to `nova/t4_1_septima_ola_A2.mp3` (20.10 s; 484,040 bytes),
  without a DIAL request or changes to clean speech. The mix decoded with no
  clipped samples. Full offline suite: 17 passed, 5 live tests skipped, including
  background looping/trimming and missing/corrupt/empty input rejection.

- **T1 vision**: `gpt-5.6-terra` recognised both the elephant (with Kilimanjaro) and the *DIALX Community* logo:
  ```text
  🧪 [T1 image analysis] attempt 1/3: DeepSeek-V4-Flash-2026-04-23
  ❌ [T1 image analysis] DeepSeek-V4-Flash-2026-04-23 rejected: does not accept 'image/png' attachments (None)
  🧪 [T1 image analysis] attempt 2/3: gpt-5.6-terra-2026-07-09
  ✅ [T1 image analysis] gpt-5.6-terra-2026-07-09 is suitable

  Beneath Kilimanjaro's crown of snow,
  an elephant walks—ancient, slow.
  ...
  Like voices joined across a screen,
  a vibrant community grows between:
  ```
- **T2 generation**: the text model "answered" the image prompt with a short story, so the output validator
  rejected it. `gpt-image-2` returned a 1254×1254 PNG (≈3 MB) of a smiling cat/dog hybrid:
  ```text
  ❌ [T2 image generation] DeepSeek-V4-Flash-2026-04-23 rejected: no image attachment returned (text: 'Here is a story about a **Smiling Catdog**. ...')
  ✅ [T2 image generation] gpt-image-2-2026-04-21 is suitable
  🖼️ Saved 3006676 bytes -> t2_catdog_gpt-image-2-2026-04-21.png
  ```
- **T2 edit**: `logo.png` → neon cyan/magenta "DIALX COMMUNITY" with sparkles and a nebula aura
  (`t2_logo_magic_gpt-image-2-2026-04-21.png`, 1254×1254).
- **T3 STT**: `gpt-4o-transcribe` is closer to the spoken brand name:
  ```text
  📊 Comparison:
    whisper-001          -> 'Join Dialects Community on Discord.'
    gpt-4o-transcribe    -> 'Join Dialex Community on Discord.'
  ```
- **T4 TTS**: only `tts-1` voices are allowed. `coral` is rejected, and `instructions` is accepted but ignored:
  ```text
  ⚠️ voice 'coral' not supported by tts-hd-001: HTTP 400: ... allowed values are: nova, shimmer, echo, onyx, fable, alloy
  🔊 Saved 67859 bytes -> t4_speech_tts-hd-001_alloy.mp3
  🔊 Saved 66419 bytes -> t4_speech_tts-hd-001_nova.mp3
  🔊 Saved 61619 bytes -> t4_speech_tts-hd-001_onyx.mp3
  ```
- **T5 STS**: no DIAL model does native audio in/out, so the two-hop pipeline is used:
  ```text
  ❌ [T5 STS native] gpt-4o rejected: HTTP 400: Invalid 'messages[0]'. Content blocks are expected to be either text or image_url type.
  ❌ [T5 STS native] gpt-5.6-terra-2026-07-09 rejected: HTTP 422: Audio messages aren't supported
  ⛔ [T5 STS native] no suitable model after 3 attempts
  ↪️ Falling back to pipeline: audio understanding -> TTS
  🎧 Question transcript (gpt-4o-transcribe): "Why can't we say that black is white?"
  ✅ [T5 STS understanding] gemini-3.8-flash is suitable
  ⚠️ voice 'ballad' rejected (... allowed values are: nova, shimmer, echo, onyx, fable, alloy); using 'fable'
  💬 Answer [pipeline:gemini-3.8-flash+tts-001(fable)]: We cannot say that black is white because they are physically and visually opposite states: ...
  🔊 Saved 449459 bytes -> t5_answer.mp3
  ```
