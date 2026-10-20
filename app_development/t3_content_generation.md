# AI Content Generation

## ITT: Image-to-Text (Image Analysis)

### What is it?

Multimodal LLMs accept images as part of the input and generate a text response. This enables use cases like:

* Describing what's in a photo
* Answering questions about a chart or diagram
* Extracting text from screenshots (OCR-like behavior)
* Medical image interpretation

### Models that support image input

| Provider | Model |
|----------|-------|
| OpenAI | `gpt-5+` |
| Anthropic | `claude-sonnet-4-5` |
| Google | `gemini-3-flash` |

Many other LLMs also support image input.

### How to pass images in the OpenAI API

The `content` field in a message becomes an array when you want to mix text and images.

#### Option A — URL

The image must be publicly accessible (direct download link):

```bash
curl https://api.openai.com/v1/chat/completions \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $OPENAI_API_KEY" \
-d '{
  "model": "gpt-5.2",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "What is in this image?"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png"
          }
        }
      ]
    }
  ]
}'
```

#### Option B — Base64 Encoded

Use this when the image is local or not publicly accessible:

```bash
curl https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
  "model": "gpt-5.2",
  "messages": [
    {
      "role": "user",
      "content": [
        { "type": "text", "text": "Describe this image." },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/jpeg;base64,<BASE64_ENCODED_IMAGE>"
          }
        }
      ]
    }
  ]
}'
```

Tip: To encode an image to base64 in Python:

```python
import base64

with open("image.jpg", "rb") as f:
    b64 = base64.b64encode(f.read()).decode("utf-8")
```

> 📖 [OpenAI Docs: Image Analysis](https://developers.openai.com/api/docs/guides/images-vision#analyze-images)

## TTI: Text-to-Image (Image Generation)

### What is it?

Text-to-image models accept a text prompt and return a generated image. They are useful for:

* Creating illustrations, mockups, or concept art
* Generating marketing visuals
* Rapid prototyping of design ideas

### Models

#### OpenAI

`gpt-image-2`: OpenAI's newer generation model with improved instruction following.

**Key parameters:**

| Parameter | Options |
|-----------|---------|
| `size` | `1024x1024`, `1024x1792`, `1792x1024` |
| `style` | `natural` (realistic), `vivid` (hyper-real) |
| `quality` | `standard`, `hd` |

**Example (curl):**

```bash
curl https://api.openai.com/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-image-2",
    "prompt": "A futuristic city at night with neon lights reflecting on wet streets",
    "size": "1024x1024",
    "style": "vivid",
    "quality": "hd"
  }'
```

> 📖 [OpenAI Docs — Image Generation API](https://developers.openai.com/api/reference/resources/images/methods/generate)
>
> ⚠️ Note: Image generation is significantly more expensive than text generation. Plan your usage accordingly.

#### Google: Imagen

Google offers image generation through Imagen 3 via Vertex AI and the Generative Language API.

**Endpoint:**

```text
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:predict
```

**Example request:**

```bash
curl -X POST \
    "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
        "instances": [
          {
            "prompt": "Robot holding a red skateboard"
          }
        ],
        "parameters": {
          "sampleCount": 4
        }
      }'
```

> 📖 [Google Imagen](https://ai.google.dev/gemini-api/docs/imagen)

#### Google Nano Banana

**Example request:**

```bash
curl -s -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{
      "parts": [
        {"text": "Create a picture of a nano banana dish in a fancy restaurant with a Gemini theme"}
      ]
    }]
  }'
```

> 📖 [Google Nano Banana](https://ai.google.dev/gemini-api/docs/image-generation)

## STT: Speech-to-Text (Transcription)

### What is it?

Speech-to-text models convert audio content into text. Common use cases:

* Transcribing meeting recordings
* Building voice-controlled interfaces
* Multilingual transcription and translation

### Models

| Model | Description |
|-------|-------------|
| `whisper-1` | OpenAI's open-source model; can be self-hosted via `openai/whisper` |
| `gpt-4o-transcribe` | OpenAI's latest, more accurate transcription model |

### OpenAI API — Transcription

The audio file is sent as `multipart/form-data`:

```bash
curl https://api.openai.com/v1/audio/transcriptions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: multipart/form-data" \
  --form file=@/path/to/recording.mp3 \
  --form model=gpt-4o-transcribe
```

For translation (audio in any language → English text), use the `/translations` endpoint:

```bash
curl https://api.openai.com/v1/audio/translations \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: multipart/form-data" \
  --form file=@/path/to/german_audio.mp3 \
  --form model=whisper-1
```

**Supported audio formats:** `mp3`, `mp4`, `mpeg`, `mpga`, `m4a`, `wav`, `webm`

> 📖 [OpenAI Docs: Speech to Text](https://developers.openai.com/api/docs/guides/speech-to-text)

## TTS: Text-to-Speech (Synthesis)

### What is it?

Text-to-speech models convert text into spoken audio. Use cases:

* Voice assistants and chatbots
* Audiobook generation
* Accessibility features
* Podcast-style content generation

### Models

| Model | Description |
|-------|-------------|
| `gpt-4o-mini-tts` / `gpt-4o-tts` | OpenAI's latest; supports voice instructions |
| `tts-1`, `tts-1-hd` | OpenAI's previous generation (still available) |
| `coqui` | Open-source, self-hostable |
| `piper` | Lightweight open-source TTS, great for local/edge deployment |

### OpenAI API Speech Generation

```bash
curl https://api.openai.com/v1/audio/speech \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini-tts",
    "input": "Welcome to the AI content generation course!",
    "voice": "coral",
    "instructions": "Speak in a warm and enthusiastic tone.",
    "speed": 1.0,
    "response_format": "mp3"
  }' \
  --output welcome.mp3
```

**Output parameters:**

| Parameter | Options |
|-----------|---------|
| `voice` | `alloy`, `ash`, `ballad`, `coral`, `fable`, `nova`, `onyx`, `sage`, `shimmer` |
| `speed` | 0.25 to 4.0 |
| `response_format` | `mp3`, `opus`, `aac`, `flac`, `wav`, `pcm` |
| `instructions` | Free-text instructions for tone, style, accent |

> 📖 [OpenAI Docs: Text to Speech](https://developers.openai.com/api/docs/guides/text-to-speech)

## STS: Speech-to-Speech (Voice Conversion)

### What is it?

Speech-to-speech (also called audio chat) allows the model to accept audio input and respond with audio output, enabling real-time, natural voice conversations without separate STT and TTS pipeline steps.

### Model

* `gpt-4o-audio-preview`: OpenAI's multimodal model supporting audio I/O

### OpenAI API Audio

Both input and output audio are passed as base64-encoded data:

```bash
curl https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-4o-audio-preview",
    "modalities": ["text", "audio"],
    "audio": { "voice": "alloy", "format": "wav" },
    "messages": [
      {
        "role": "user",
        "content": [
          { "type": "text", "text": "Please respond to this voice message." },
          {
            "type": "input_audio",
            "input_audio": {
              "data": "<BASE64_ENCODED_WAV>",
              "format": "wav"
            }
          }
        ]
      }
    ]
  }'
```

The response will contain a base64-encoded audio object alongside the text response. You decode it to save or play the audio file.

> ⚠️ Note: STS/audio generation is more expensive than standard text completion. Monitor your usage.

> 📖 [OpenAI Docs: Add Audio to Your Application](https://developers.openai.com/api/docs/guides/audio#add-audio-to-your-existing-application)

## TTV: Text-to-Video (Video Generation)

### What is it?

Text-to-video models generate short video clips from a text prompt. This is one of the newest frontiers in generative AI.

### Models

#### OpenAI: Sora

* Generates realistic video clips up to 1 minute long
* Understands complex scene descriptions and physical interactions
* Available via the OpenAI platform for certain tiers

#### Google: Veo 2

* Google's state-of-the-art video generation model
* Available through Vertex AI and Google AI Studio
* Supports high-resolution video generation with fine control over camera motion and cinematography

#### Other notable models

| Model | Description |
|-------|-------------|
| Runway Gen-3 | Popular in the creative industry |
| Kling | High-quality video generation from the Chinese AI lab Kuaishou |
| LTX Video | Open-source alternative |

These models are still maturing rapidly. Quality, latency, and pricing vary significantly across providers.

## Summary

Modern AI is not limited to text. The table below recaps everything we covered:

| Type | Input | Output | OpenAI Model Example |
|------|-------|--------|----------------------|
| Text-to-Text | Text | Text | `gpt-4o`, `gpt-5.3` |
| Image-to-Text | Image + Text | Text | `gpt-4o`, `gpt-5.3` |
| Text-to-Image | Text | Image | `dall-e-3`, `gpt-image-1` |
| Speech-to-Text | Audio | Text | `whisper-1`, `gpt-4o-transcribe` |
| Text-to-Speech | Text | Audio | `gpt-4o-mini-tts` |
| Speech-to-Speech | Audio | Audio | `gpt-4o-audio-preview` |
| Text-to-Video | Text | Video | OpenAI Sora, Google Veo |

**Key takeaways:**

* The same OpenAI API style (messages array with typed content) is used across modalities, once you know it for text, the jump to images and audio is small.
* Multimodal inputs are expressed as arrays of content objects with a `type` field (`text`, `image_url`, `input_audio`).
* Different modalities have very different cost profiles, image and audio generation are significantly more expensive than text.
