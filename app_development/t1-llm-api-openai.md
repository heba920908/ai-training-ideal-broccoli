# OpenAI Chat completions

## Request

A chat completion sends a conversation to the API and returns the assistant's next response.

**URL:** `https://api.openai.com/v1/chat/completions`

**Headers:**

| Header | Value | Purpose |
|---|---|---|
| `Content-Type` | `application/json` | Tells the server we're sending JSON. |
| `Authorization` | `Bearer {API Key}` | Your API key for authentication. |

### The Request Body (JSON)

This is where all the magic happens. The body is a JSON object with the following fields:

#### Request Body Fields

| Field | Required | Description |
|---|---|---|
| `model` | Yes | The model to use for the response. |
| `messages` | Yes | The conversation as an array of message objects. Each message has a `role` and `content`. |
| `stream` | No | Set to `false` (the default) to receive the complete response at once, or `true` to receive it in chunks as it is generated. |
| `stream_options` | No | Optional streaming settings, such as requesting token usage in the final chunk. |

Each message has a `role` that identifies the speaker and `content` containing the message text:

| Role | Purpose | Example |
|---|---|---|
| `system` | Sets the assistant's behavior and instructions. | `"You are a helpful coding assistant. Be concise."` |
| `user` | Contains the end user's question or request. | `"What is a REST API?"` |
| `assistant` | Contains a previous assistant response in a multi-turn conversation. | `"A REST API is..."` |

The `content` field contains the actual text of the message.

### How Multi-Turn Conversation Works

The model has no memory between API calls. To have a multi-turn conversation, you must send the entire conversation history every time:

```text
Call 1: [system, user] → assistant replies
Call 2: [system, user, assistant, user] → assistant replies
Call 3: [system, user, assistant, user, assistant, user] → assistant replies
```

## Non-Streaming Response

When `stream` is not set or is `false`, the server will return the complete response only after it has finished generating it. This is the default behavior.

Example request body for a non-streaming response:
```shell
curl -X POST "https://api.openai.com/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {API Key}" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is a REST API?"}
    ],
    "stream": false
  }'
```

Example response for a non-streaming request:
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "gpt-4o",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "A REST API is..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 5,
    "total_tokens": 15
  }
}
```

### Response Structure Overview

The response JSON has these top-level fields:

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier for this completion (useful for logging and debugging). |
| `object` | string | Always `"chat.completion"` for non-streaming responses. |
| `created` | integer | Unix timestamp of when the response was generated. |
| `model` | string | The model version that generated the response. |
| `choices` | array | The model's response or responses. Usually contains one item. |
| `usage` | object | Token usage statistics for cost tracking. |

### The `choices` Field

The `choices` field is an array containing the model's responses. Each item in the array has the following structure:

| Field | Type | Description |
|---|---|---|
| `index` | integer | The position of this choice in the array (usually `0`). |
| `message.role` | string | The role of the message sender (for example, `"assistant"`). |
| `message.content` | string | The assistant's response text. |
| `finish_reason` | string | Why generation stopped (for example, `"stop"` or `"length"`). |

To get the answer, access `choices[0].message.content`; that is the text to display to the user.

## Streaming Response

When using streaming, the server sends partial responses as they are generated. This allows you to display the assistant's reply in real-time, similar to how ChatGPT types out its responses.

To enable streaming, set the `stream` field in the request body to `true`. The server will then send a series of events, each containing a chunk of the response.

Example request body for streaming:
```json
{
  "model": "gpt-4o",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is a REST API?"}
  ],
  "stream": true,
  "stream_options": {
    "include_usage": true
  }
}
```

### What You Receive: Server-Sent Events (SSE)

Instead of a single JSON response, you receive a stream of events using the Server-Sent Events (SSE) protocol. This is a standard web technology for server-to-client streaming over HTTP.

Each event is a text line starting with `data:` followed by a JSON object. Events are separated by blank lines. The stream ends with the special line `data: [DONE]`.

Example SSE events:
```text
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"delta":{"role":"assistant","content":"Hello"},"index":0,"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"delta":{},"index":0,"finish_reason":"stop"}]}

data: [DONE]
```

### Anatomy of a Streaming Chunk

Each chunk is a JSON object with a structure very similar to the non-streaming response, but with key differences:

| Aspect | Non-Streaming | Streaming Chunk |
|---|---|---|
| Object type | `"chat.completion"` | `"chat.completion.chunk"` |
| Content field | `message` (complete text) | `delta` (incremental piece) |
| How content arrives | All at once | Token by token |
| `finish_reason` | Set on the response | `null` until the final chunk, then `"stop"` |
| End signal | Response body ends | Special `data: [DONE]` line |

The key concept is `delta` instead of `message`. Each chunk's `choices[0].delta.content` contains a small piece of text (usually one or a few tokens). Concatenate the pieces to build the full response.

### The Three Phases of a Stream

1. **First chunk (role announcement):** The first chunk announces the role. `delta` contains `{"role": "assistant", "content": ""}`. Its content is empty; it indicates that the assistant is about to respond.
2. **Content chunks:** Each subsequent chunk has `delta` containing text, such as `{"content": "some text"}`. Chunks arrive one by one. Display each piece as it arrives for a real-time typing effect.
3. **Final chunk and completion signal:** The last data chunk has an empty `delta` (`{}`) and `finish_reason` set to `"stop"`. The stream then sends `data: [DONE]` to signal the end.

### How to Parse Streaming Responses

The algorithm for parsing a stream is:

1. Read the HTTP response as a stream (line by line, not all at once).
2. For each line, check whether it starts with `data:`.
3. If the data is `[DONE]`, stop; the stream is complete.
4. Otherwise, parse the JSON after `data:`.
5. Extract `choices[0].delta.content`, the new text piece.
6. Append it to your buffer and display it to the user.
7. Repeat until `[DONE]`.

---

# OpenAI Responses

## Request

It's Still Just a REST Call!

The Responses API follows the same HTTP pattern: a POST request with a JSON body and an Authorization header.

```shell
curl https://api.openai.com/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-4.1-mini",
    "input": "Hello!"
  }'
```

URL: https://api.openai.com/v1/responses

Headers:

| Header | Value | Purpose |
| --- | --- | --- |
| Content-Type | application/json | Tells the server we're sending JSON |
| Authorization | Bearer {API_KEY} | Your API key for authentication |

### Request Body (JSON):

* `model` (required): Which AI Model to Use
* `input` (required): The Conversation. This is the equivalent of messages in Chat Completions, but more flexible. It accepts two formats:
  * Simple string format: You can pass a plain text string directly as input. The API treats it as a single user message. This is the simplest possible way to call the API.
  * Messages array format: Same structure as Chat Completions — an array of objects with role and content. Roles are the same: user, assistant, developer (replaces system).
* `instructions` (optional): System-Level Guidance. In Chat Completions, system instructions were embedded as a system role message inside the messages array. The Responses API separates them into a dedicated instructions field. This is equivalent to the system message but lives at the top level of the request. The model treats instructions as higher-priority guidance, similar to how the system role worked.
* `stream` (optional): Real-Time Streaming
* `previous_response_id` (optional): Stateful Conversations. This is the biggest convenience of the Responses API. Instead of resending the entire conversation history, you can pass the id of a previous response, and the API automatically includes all prior context.
  * 💡 This requires `store: true` (the default). The server stores the conversation and reconstructs context automatically. You no longer need to manage message history yourself.
  * You can still manage context manually by passing the full messages array in input — exactly like Chat Completions. Both approaches work.
Call 1: Send `input: "What is Python?"` → get response with id: "resp_abc123"
Call 2: Send `input: "Give me an example"` + `previous_response_id: "resp_abc123"` → the model has full context
* `store` (optional): Controls whether the response is stored server-side.
  * `true` (default): Response is stored server-side, can be retrieved later, enables `previous_response_id`.
  * `false`: Response is not stored, stateless mode.

## Non-Streaming Response

```json
{
  "id": "resp_67b73f697ba4819183a15cc17d011509",
  "object": "response",
  "status": "completed",
  "created_at": 1746128400,
  "model": "your-model-name",
  "error": null,
  "incomplete_details": null,
  "output": [
    {
      "id": "msg_67b73f697ba4819183a15cc17d011509",
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "output_text",
          "text": "Hello! How can I help you today?",
          "annotations": []
        }
      ]
    }
  ],
  "usage": {
    "input_tokens": 8,
    "input_tokens_details": {
      "cached_tokens": 0
    },
    "output_tokens": 9,
    "output_tokens_details": {
      "reasoning_tokens": 0
    },
    "total_tokens": 17
  }
}
```


The response JSON has these top-level fields:

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (for example, `"resp_abc123..."`); use it as `previous_response_id` in a follow-up request. |
| `object` | string | Always `"response"`. |
| `created_at` | number | Unix timestamp for when the response was created. |
| `model` | string | The exact model version used. |
| `status` | string | The completion status; this replaces `finish_reason`. |
| `output` | array | The model's output items. |
| `usage` | object | Token usage statistics. |
| `error` | object or `null` | Error details if the response failed. |
| `incomplete_details` | object or `null` | Why the response is incomplete when `status` is `"incomplete"`. |
| `instructions` | string or `null` | The instructions provided with the request. |
| `metadata` | object | Custom key-value metadata attached to the response. |

### The `output` Field

This is the biggest structural difference from Chat Completions. Instead of `choices[0].message`, the Responses API returns an array of typed items. Each item's `type` field identifies what it contains.

For a simple text response, the `output` array typically contains one message item:

| Field | Value | Description |
|---|---|---|
| `id` | string | Unique ID of this output item. |
| `type` | `"message"` | Identifies the item as a message. |
| `role` | `"assistant"` | Identifies the model output as an assistant message. |
| `status` | `"completed"` | Status of this specific item. |
| `content` | array | Content parts that make up the message. |

The message's `content` array contains content parts, each with its own type:

| Field | Value | Description |
|---|---|---|
| `type` | `"output_text"` | Identifies a text content part. |
| `text` | string | The response text. |
| `annotations` | array | Citations, file references, and other annotations. |

### Getting the Response Text

- **Quick method:** Read the top-level `output_text` field. It concatenates the text from all message items.
- **Detailed method:** Find the item in `output` whose `type` is `"message"`, then read `output[N].content[0].text`.

> The `output_text` helper is the Responses API equivalent of `choices[0].message.content`. For simple text responses, use `output_text`.

### When the Output Contains Multiple Items

For reasoning models, the `output` array may contain multiple items:

| Item type | Description |
|---|---|
| `"reasoning"` | Reasoning content. May contain a `summary` field with a human-readable summary. |
| `"message"` | The assistant's response to the user. Contains the text to display. |
| `"function_call"` | A request to call one of your custom functions. |
| `"web_search_call"` | A call to the built-in web search tool. |
| `"file_search_call"` | A call to the built-in file search tool. |
| `"code_interpreter_call"` | A call to the built-in code interpreter. |
| `"mcp_call"` | A call to an MCP (Model Context Protocol) server. |

A typical non-reasoning response contains a single `"message"` item. A reasoning response may contain a `"reasoning"` item followed by a `"message"` item.

### Response Status

The Responses API uses a `status` field instead of `finish_reason`:

| Status | Meaning | Action |
|---|---|---|
| `"completed"` | The model finished generating the response. | Use the response. |
| `"incomplete"` | The response was cut off or otherwise not completed. | Check `incomplete_details.reason` for details. |
| `"failed"` | An error occurred. | Check the `error` field. |
| `"in_progress"` | The response is still generating in background mode. | Poll or wait for completion. |
| `"cancelled"` | The response was cancelled. | No further action. |

## Streaming Responses

### Enable Streaming

Set `"stream": true` in your request body. Everything else stays the same.

### Example Request

Send this JSON body to `POST /v1/responses`:

```json
{
  "model": "your-model-name",
  "input": [
    {
      "role": "user",
      "content": "Explain how streaming responses work in one sentence."
    }
  ],
  "stream": true
}
```

Replace `"your-model-name"` with a model available to your API account.

### Example Streamed Output

With streaming enabled, the HTTP response is a sequence of Server-Sent Events (SSE), not one JSON document. Each event has an `event:` line and a `data:` line. This abbreviated example shows text deltas and the final completed response; a real stream can include additional lifecycle events.

```text
event: response.output_text.delta
data: {"type":"response.output_text.delta","delta":"Streaming responses send text as it is generated."}

event: response.output_text.delta
data: {"type":"response.output_text.delta","delta":" Each event is typed so you can handle updates as they arrive."}

event: response.completed
data: {"type":"response.completed","response":{"id":"resp_example123","object":"response","status":"completed","model":"your-model-name","output":[{"id":"msg_example123","type":"message","role":"assistant","content":[{"type":"output_text","text":"Streaming responses send text as it is generated. Each event is typed so you can handle updates as they arrive.","annotations":[]}]}],"usage":{"input_tokens":14,"output_tokens":20,"total_tokens":34}}}

```

### What the Stream Contains

Responses streaming uses Server-Sent Events (SSE). Unlike Chat Completions, which streams chunks with a common chunk structure, Responses emits typed events. Each event type identifies a particular update or lifecycle stage.

An SSE event typically contains an `event:` line, a `data:` line with a JSON payload, and a blank line:

```text
event: response.output_text.delta
data: {"type":"response.output_text.delta","delta":"Hello"}

```

The event stream can include lifecycle, content, tool, and error events. The exact sequence depends on the response; not every request emits every event below.

### Common Text-Response Events

| Event | Purpose |
|---|---|
| `response.created` | The response has been created. |
| `response.in_progress` | The response is being generated. |
| `response.output_item.added` | An output item, such as an assistant message, has started. |
| `response.content_part.added` | A content part has started. |
| `response.output_text.delta` | A piece of generated text is available. This event may occur many times. |
| `response.output_text.done` | The text content part is complete. |
| `response.content_part.done` | The content part is complete. |
| `response.output_item.done` | The output item is complete. |
| `response.completed` | Generation completed successfully; the event includes the completed response object. |
| `response.incomplete` | Generation ended without completing the response. Check the response's status and `incomplete_details`. |
| `response.failed` | Generation failed. Check the response's error details. |
| `error` | An error event was emitted. Handle the event's error information. |

### Read Text Deltas

For a real-time text display, listen for `response.output_text.delta` and append each event's `delta` value to the text buffer:

| Payload field | Description |
|---|---|
| `type` | Event type, `"response.output_text.delta"`. |
| `delta` | The new text piece to append. |
| `output_index` | Index of the output item this text belongs to. |
| `content_index` | Index of the content part within that item. |
| `item_id` | ID of the output item. |
| `sequence_number` | Event sequence number. |

The `delta` value plays a role similar to `choices[0].delta.content` in Chat Completions streaming.

### Chat Completions and Responses Streaming Compared

| Aspect | Chat Completions | Responses API |
|---|---|---|
| Event format | `data:` lines containing chunks with a common structure. | Typed SSE events with event-specific payloads. |
| Text content | `choices[0].delta.content` | `delta` on `response.output_text.delta` events. |
| Successful completion | A final chunk with `finish_reason`, followed by `data: [DONE]`. | `response.completed`, which contains the completed response. |
| Usage data | Can be requested with `stream_options`. | Available on the completed response when returned by the API. |
| Event types | Chat completion chunks. | Multiple event types for response lifecycle, text, tools, and errors. |

### Parse a Responses Stream

1. Read the HTTP response as an SSE stream.
2. Parse each event's type and JSON payload.
3. On `response.output_text.delta`, append `delta` to the text buffer and display the new text.
4. On `response.completed`, use the completed response and its status and usage data.
5. On `response.incomplete`, `response.failed`, or `error`, handle the corresponding incomplete or error details.
6. Handle other event types only if the application uses related features, such as tools or structured output.

Unlike Chat Completions, Responses streams do not use `data: [DONE]` as the normal successful-completion signal. Use typed completion and error events to determine how the stream ended.

### Reasoning Summary Events

Some requests can emit reasoning-summary events:

| Event | Description |
|---|---|
| `response.reasoning_summary_text.delta` | A piece of a reasoning summary. |
| `response.reasoning_summary_text.done` | The completed reasoning summary text. |

These events are distinct from the assistant's user-facing text. Their presence and order depend on the model and request.

## Summary

### Common Mistakes to Avoid

| Mistake | What happens | Better approach |
|---|---|---|
| Sending `messages` instead of `input` | The request uses the wrong parameter. | Send `input`, as a string or an array of messages. |
| Using Chat Completions' `response_format` parameter | The parameter is not the Responses API format. | Use `text.format` for supported structured-output requests. |
| Using `max_completion_tokens` | This is not the Responses API output-token parameter. | Use `max_output_tokens`. |
| Checking `finish_reason` on a Responses API response | The Responses API uses a different completion status. | Check `status`, such as `"completed"`, `"incomplete"`, or `"failed"`. |
| Reading `choices[0].message.content` | That path belongs to Chat Completions. | Read `output_text` in an SDK that provides it, or find text in the response's `output` items. |
| Expecting `data: [DONE]` from a Responses stream | That is not the Responses API's normal completion event. | Handle `response.completed`, and also handle incomplete or error events. |
| Setting `store: false` and then using `previous_response_id` | The previous response is not available for server-side chaining. | Keep response storage enabled when using `previous_response_id`, or manage context in the request yourself. |

### Responses API and Chat Completions Compared

| Aspect | Chat Completions | Responses API |
|---|---|---|
| Endpoint | `/v1/chat/completions` | `/v1/responses` |
| Input | `messages` array | `input` string or array of messages |
| System guidance | `system` role in `messages` | `instructions` field or `developer` role |
| Text output | `choices[0].message.content` | `output` array; SDKs may provide `output_text` |
| Conversation state | Resend message history | Use `previous_response_id` or manage history manually |
| Completion status | `finish_reason` on a choice | `status` on the response |
| Token usage | `usage.prompt_tokens` and `usage.completion_tokens` | `usage.input_tokens` and `usage.output_tokens` |
| Streaming | Chunk events, ending with `data: [DONE]` | Typed SSE events such as `response.output_text.delta` |
| Built-in tools | No built-in tools in the endpoint | Supports tools such as web search and file search |
| Multiple choices | Supports `n` in supported configurations | Generates a single response per request |
| Storage | Not stored by default | Stored by default unless disabled |

## Useful resources

* [Responses API reference: Create a response](https://developers.openai.com/api/reference/resources/responses/methods/create)
* [Streaming API responses](https://developers.openai.com/api/docs/guides/streaming-responses)
