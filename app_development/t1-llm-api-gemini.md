# Gemini API

## Request

A content-generation request sends a conversation to the API and returns the model's next response.
This guide covers Google's native Gemini `generateContent` API, not its OpenAI-compatible interface or Interactions API.

**Base URL:** `https://generativelanguage.googleapis.com`

| Endpoint | Purpose |
|---|---|
| `POST /v1beta/models/{model}:generateContent` | Return the complete response at once. |
| `POST /v1beta/models/{model}:streamGenerateContent?alt=sse` | Stream partial responses as Server-Sent Events (SSE). |

Unlike OpenAI Chat Completions, Gemini selects streaming through a different endpoint, not a `"stream": true` field. The JSON request body can be the same for both Gemini endpoints.
The model name goes in the URL, not in the body.

**Headers:**

| Header | Value | Purpose |
|---|---|---|
| `Content-Type` | `application/json` | Tells the server we're sending JSON. |
| `x-goog-api-key` | The value of `GEMINI_API_KEY` | Authenticates the request with a Google Gemini API key. |

Google also supports a `key` query parameter, but the examples use the header to keep credentials out of URLs and URL logs.
Do not use a DIAL key with Google's native endpoint. The repository's default exercises still use the OpenAI-compatible DIAL API; these examples specifically demonstrate Google's native API.

### Shell Setup

The commands below use Bash and `curl`. Run them from the repository root.

In your local, git-ignored [`.env`](../.env), set `GEMINI_API_KEY` to your Google API key and `GEMINI_MODEL` to an available model ID.
The following shows placeholders only; replace them locally before running the requests:

```dotenv
GEMINI_API_KEY=<your-gemini-key>
GEMINI_MODEL=<available-gemini-model-id>
```

Use a bare model ID, without a `models/` prefix. Model availability and supported options depend on your account and the model.
See Google's [model documentation](https://ai.google.dev/gemini-api/docs/models).
Do not commit your local environment file or paste a real key into documentation.

Load the variables into your shell:

```shell
set -a
source ./.env
set +a

: "${GEMINI_API_KEY:?Set GEMINI_API_KEY in the root .env}"
: "${GEMINI_MODEL:?Set GEMINI_MODEL in the root .env}"
```

Only source an environment file you trust: `source` executes shell code.
Do not enable shell tracing (`set -x`) or verbose HTTP logging when using real credentials.

### The Request Body (JSON)

| Field | Required | Description |
|---|---|---|
| `contents` | Yes | The conversation as an array of content objects. |
| `systemInstruction` | No | Separate instructions that guide the model's behavior. Currently text only. |
| `generationConfig` | No | Generation settings, such as `maxOutputTokens` and `temperature`, where supported. |
| `safetySettings` | No | Per-category safety settings, where supported. |
| `tools` | No | Tool declarations, such as functions the model may request. |

Each item in `contents` has a `role` and a `parts` array:

| Role | Purpose | Example |
|---|---|---|
| `user` | The end user's question or request. | `{"role": "user", "parts": [{"text": "What is a REST API?"}]}` |
| `model` | A previous model response in a multi-turn conversation. | `{"role": "model", "parts": [{"text": "A REST API is..."}]}` |

For a single-turn request, the role can be omitted; these examples include it explicitly.
Gemini uses `model`, not OpenAI's `assistant`, and system instructions belong in `systemInstruction`, not in a `system` message.

The `parts` array can contain text, media, function calls, or other supported part types. For a text-only request, use `{"text": "..."}`:

```json
{
  "systemInstruction": {
    "parts": [
      {"text": "You are a helpful coding assistant. Be concise."}
    ]
  },
  "contents": [
    {
      "role": "user",
      "parts": [
        {"text": "What is a REST API?"}
      ]
    }
  ],
  "generationConfig": {
    "maxOutputTokens": 1024
  }
}
```

`maxOutputTokens` limits generated tokens. On thinking models, the output budget can also be consumed by thinking, so a small limit may leave little room for the visible answer.
Supported settings and limits vary by model.

### How Multi-Turn Conversation Works

These REST endpoints do not reconstruct a conversation from a previous response ID.
Send the conversation history on every call:

```text
Call 1: [user] -> model replies
Call 2: [user, model, user] -> model replies
Call 3: [user, model, user, model, user] -> model replies
```

Send `systemInstruction` again when you need the same instructions on a later request.
For a text-only conversation, a second request can look like this:

```shell
curl --fail-with-body --show-error \
  "https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent" \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: ${GEMINI_API_KEY}" \
  --data-binary @- <<'JSON'
{
  "systemInstruction": {
    "parts": [{"text": "You are a helpful coding assistant. Be concise."}]
  },
  "contents": [
    {
      "role": "user",
      "parts": [{"text": "What is a REST API?"}]
    },
    {
      "role": "model",
      "parts": [{"text": "A REST API exposes resources through standard HTTP methods."}]
    },
    {
      "role": "user",
      "parts": [{"text": "Give me an example of a GET request."}]
    }
  ]
}
JSON
```

The previous model response above is illustrative. In an application, reuse the actual returned `content` object, preserving its parts and any thought signatures required by the model, especially for tool use.

## Non-Streaming Response

### Example Request

Call `generateContent` to receive one JSON response after generation finishes.
After completing the shell setup, copy and run:

```shell
curl --fail-with-body --show-error \
  "https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent" \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: ${GEMINI_API_KEY}" \
  --data-binary @- <<'JSON'
{
  "systemInstruction": {
    "parts": [{"text": "You are a helpful coding assistant. Be concise."}]
  },
  "contents": [
    {
      "role": "user",
      "parts": [{"text": "What is a REST API?"}]
    }
  ],
  "generationConfig": {
    "maxOutputTokens": 1024
  }
}
JSON
```

`--data-binary` makes this a POST request. The quoted heredoc delimiter (`'JSON'`) keeps the shell from expanding characters in the JSON body.
`--fail-with-body` makes HTTP errors return a nonzero exit status while preserving the error response body; it requires curl 7.76.0 or newer.

### Example Response

This is an illustrative, abbreviated response, not captured API output. Text, token counts, model versions, IDs, and optional fields vary:

```json
{
  "candidates": [
    {
      "content": {
        "role": "model",
        "parts": [
          {"text": "A REST API exposes resources through standard HTTP methods such as GET and POST."}
        ]
      },
      "finishReason": "STOP",
      "index": 0
    }
  ],
  "usageMetadata": {
    "promptTokenCount": 20,
    "candidatesTokenCount": 18,
    "totalTokenCount": 38
  },
  "modelVersion": "your-model-version",
  "responseId": "example-response-id"
}
```

### Response Structure Overview

| Field | Type | Description |
|---|---|---|
| `candidates` | array | Generated candidates; a simple text request usually returns one. May be absent when the prompt is blocked. |
| `promptFeedback` | object | Prompt-level feedback, including `blockReason` when a prompt is blocked. |
| `usageMetadata` | object | Token-usage statistics. |
| `modelVersion` | string | The model version used to generate the response. |
| `responseId` | string | An identifier for the response, not a conversation-history handle. |

### The `candidates` Field

| Field | Type | Description |
|---|---|---|
| `index` | integer | The candidate's index, usually `0` in a single-candidate response. |
| `content.role` | string | `model` for generated content. |
| `content.parts` | array | Generated parts, such as text or function calls. |
| `finishReason` | string | Why generation stopped. |
| `safetyRatings` | array | Safety ratings for the candidate, when returned. |

For the simple example, the answer is at `candidates[0].content.parts[0].text`.
In an application, do not assume that path always exists:

1. Handle HTTP errors before treating the body as a generation response.
2. Check `promptFeedback.blockReason` if no candidates are returned.
3. Inspect the selected candidate's `finishReason` for blocked or truncated output.
4. Collect its text parts in order, excluding parts marked `"thought": true` from the normal user-facing answer.
5. Handle non-text parts separately rather than treating missing text as a successful empty answer.

### The `finishReason` Field

Common values include:

| Value | Meaning | Action |
|---|---|---|
| `STOP` | Generation ended normally or reached a configured stop sequence. | Use the returned content. |
| `MAX_TOKENS` | Generation hit the output-token limit. | Treat the answer as potentially incomplete. |
| `SAFETY` | Generation was stopped for safety reasons. | Handle the blocked response explicitly. |
| `RECITATION` | Generation was stopped for potential recitation. | Handle the blocked response explicitly. |
| `OTHER` | Generation stopped for another reason. | Inspect the available feedback. |

This is not an exhaustive enum. Models and features can return other finish reasons, including tool-related failures; do not treat every non-`STOP` value as success.

### The `usageMetadata` Object

```json
{
  "promptTokenCount": 20,
  "candidatesTokenCount": 18,
  "totalTokenCount": 38
}
```

| Field | Description |
|---|---|
| `promptTokenCount` | Tokens in the effective prompt, including cached content when used. |
| `candidatesTokenCount` | Tokens in generated candidate output. |
| `totalTokenCount` | Total token count reported for the request. |
| `cachedContentTokenCount` | Cached prompt tokens, when applicable; a subset of prompt tokens. |
| `thoughtsTokenCount` | Tokens used for model thinking, when applicable. |
| `toolUsePromptTokenCount` | Tokens in tool-use prompts, when applicable. |

The simplified example has no thinking or tool use. Do not assume that `totalTokenCount` always equals just `promptTokenCount + candidatesTokenCount`; thinking and tool-use tokens can also contribute.
Do not add cached tokens to the prompt count a second time.
For pricing, consult the model's current billing rules rather than treating every token category as equally priced.

## Streaming Response

### Enable Streaming

Use `streamGenerateContent` instead of `generateContent`, and add `?alt=sse` to request SSE framing.
Do not add a `stream` field to the JSON body.
Without `alt=sse`, the endpoint uses JSON-array framing rather than SSE.

### Example Request

This uses the same request body as the non-streaming example:

```shell
curl --fail-with-body --show-error --no-buffer \
  "https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:streamGenerateContent?alt=sse" \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: ${GEMINI_API_KEY}" \
  --data-binary @- <<'JSON'
{
  "systemInstruction": {
    "parts": [{"text": "You are a helpful coding assistant. Be concise."}]
  },
  "contents": [
    {
      "role": "user",
      "parts": [{"text": "What is a REST API?"}]
    }
  ],
  "generationConfig": {
    "maxOutputTokens": 1024
  }
}
JSON
```

`--no-buffer` disables curl's output buffering so chunks are displayed as they arrive.
It does not change the API request or guarantee one token per event.

### What You Receive: Server-Sent Events (SSE)

Each SSE event's JSON payload has the `GenerateContentResponse` shape, but contains only the content and metadata available for that chunk.
Events are separated by blank lines. This illustrative stream is abbreviated:

```text
data: {"candidates":[{"content":{"role":"model","parts":[{"text":"A REST API exposes resources"}]},"index":0}]}

data: {"candidates":[{"content":{"role":"model","parts":[{"text":" through standard HTTP methods such as GET and POST."}]},"finishReason":"STOP","index":0}],"usageMetadata":{"promptTokenCount":20,"candidatesTokenCount":18,"totalTokenCount":38},"modelVersion":"your-model-version"}

```

The second event's text is new content to append, not the entire answer so far.
Chunk boundaries are not guaranteed to match tokens, words, or sentences.

Unlike OpenAI Chat Completions, Gemini does not use `data: [DONE]` as its normal stream terminator.
Read until the HTTP stream ends and inspect each candidate's finish reason. There is no required initial role-only event or separate empty final event.

### Anatomy of a Streaming Chunk

| Aspect | Non-Streaming | Streaming |
|---|---|---|
| Endpoint | `generateContent` | `streamGenerateContent?alt=sse` |
| HTTP body | One JSON object. | SSE events containing JSON response chunks. |
| Content field | `candidates[].content.parts[]` | The same path, with incremental parts. |
| `finishReason` | Present when generation has stopped. | Can be absent until the candidate finishes. |
| Usage | Request-level `usageMetadata`. | Metadata can arrive in later chunks; do not assume every chunk includes it. |
| End signal | Response body ends. | HTTP stream ends; inspect finish reasons and errors. |

### How to Parse Streaming Responses

1. Check the HTTP status. A failed request can return an ordinary JSON error body rather than SSE.
2. Use an SSE parser: buffer network fragments, collect `data:` lines until a blank line, and join multiple data lines with newlines.
3. Parse each event's data as JSON. Do not assume one network read contains a whole JSON object.
4. Handle an error payload or prompt-level block explicitly.
5. For each candidate, track its `index` and append new user-facing text parts in order. Keep thought and non-text parts separate.
6. Record `finishReason` when it appears. Handle truncation, safety blocks, and other non-success reasons.
7. Retain the latest request-level usage metadata when provided. Do not sum repeated cumulative token counts across chunks.
8. Read until the stream closes. If it ends without a terminal finish reason for an expected candidate, treat it as interrupted rather than successful.

## Summary

### Common Mistakes to Avoid

| Mistake | Better approach |
|---|---|
| Sending `messages` and `content` strings as in OpenAI Chat Completions | Send `contents` with `parts` arrays. |
| Putting `model` in the request body | Put the model ID in the URL path. |
| Using the `assistant` or `system` role | Use `model` for prior responses and `systemInstruction` for instructions. |
| Sending `"stream": true` | Change the endpoint to `streamGenerateContent?alt=sse`. |
| Forgetting `alt=sse` | Add it when your client expects SSE, not JSON-array framing. |
| Reading `choices[0].message.content` | Inspect `candidates[].content.parts[]`. |
| Assuming every response has a text candidate | Check HTTP errors, prompt feedback, finish reasons, and part types. |
| Expecting `data: [DONE]` | Inspect finish reasons and read until the HTTP stream ends. |
| Using `responseId` to continue a chat | Send the conversation history in `contents`. |
| Adding every stream chunk's usage counts | Retain request-level usage instead of double-counting it. |

### Gemini and OpenAI Chat Completions Compared

| Aspect | Gemini Native API | OpenAI Chat Completions |
|---|---|---|
| Non-streaming endpoint | `/v1beta/models/{model}:generateContent` | `/v1/chat/completions` |
| Authentication in these APIs | `x-goog-api-key` | Bearer authorization; proxy requirements may differ. |
| Model selection | URL path | `model` field |
| Conversation | `contents` | `messages` |
| Model role | `model` | `assistant` |
| System guidance | `systemInstruction` | `system` or `developer` message, depending on the model. |
| Message text | `parts[].text` | `content` |
| Generated text | `candidates[].content.parts[].text` | `choices[].message.content` |
| Output-token limit | `generationConfig.maxOutputTokens` | `max_completion_tokens` for supported models. |
| Completion reason | `finishReason`, such as `STOP` | `finish_reason`, such as `stop` |
| Token usage | `usageMetadata` | `usage` |
| Enable streaming | Different endpoint plus `alt=sse` | `"stream": true` |
| Streamed text | `candidates[].content.parts[].text` | `choices[].delta.content` |
| Normal stream ending | HTTP stream closes; inspect finish reasons. | Final chunks followed by `data: [DONE]`. |

## Useful Resources

* [GenerateContent and StreamGenerateContent API reference](https://ai.google.dev/api/generate-content)
* [GenerateContentResponse reference](https://ai.google.dev/api/generate-content#v1beta.GenerateContentResponse)
* [Text generation guide](https://ai.google.dev/gemini-api/docs/text-generation)
* [Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key)
* [Gemini models](https://ai.google.dev/gemini-api/docs/models)
* [Thought signatures](https://ai.google.dev/gemini-api/docs/thought-signatures)
* [Google Gen AI Python SDK](https://googleapis.github.io/python-genai/)
