# Anthropic API

## Request

The Anthropic API is a RESTful API — meaning you interact with it using standard HTTP requests (just like your browser does when you open a website).
Base URL: https://api.anthropic.com
Main endpoint: POST /v1/messages
That's it! At its core, the Anthropic API is just one endpoint that you send messages to and get responses back from. It's a regular HTTP POST request with a JSON body.

### Making a Request

```shell
curl -X POST "https://api.anthropic.com/v1/messages" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-07-01" \
  -d '{
    "system": "You are a helpful assistant.",
    "model": "claude-v1",
    "max_tokens": 100,
    "stream": false,
    "messages": [
      {
        "role": "user",
        "content": "Hello, how are you?"
      },
      {
        "role": "assistant",
        "content": "I'm doing well, thank you!"
      }
    ]
  }'
```

### Headers (Authentication & Metadata)

Every request needs 3 headers:

| Header | Purpose | Example value |
|---|---|---|
| `x-api-key` | Authenticates your request. | Your Anthropic API key |
| `anthropic-version` | Selects the API version to use. | `2023-06-01` |
| `content-type` | Specifies the format of the request body. | `application/json` |

Let's examine each field:
* `model` (required): Which Claude model to use. You must specify the exact model version.
* `max_tokens` (required): The maximum number of tokens Claude can generate in its response. Think of tokens as word-pieces (1 token ≈ ¾ of a word).

>💡 Claude may stop before reaching this limit if it finishes its thought. This only sets the upper bound.

* `messages` (required): An array of message objects representing the conversation. Each message has:
  * `role` — Who is speaking: "user" or "assistant"
  * `content` — What they said (string or array of content blocks)

>💡 Important: There is no "system" role in messages! System prompts go into a separate top-level system parameter (see below).

>💡 The API is stateless. Claude doesn't remember previous calls. For multi-turn conversations, you must send the entire conversation history every time.

* `system` (optional): A top-level system prompt that sets Claude's behavior and context
* `stream` (optional): Whether to receive the response as a stream (token by token) or all at once.

### Non-Streaming Responses

When `stream` is set to `false` (or omitted), the API will return the full response once Claude has finished generating it. The response will be a JSON object containing the conversation history, including the assistant's reply.

```json
{
  "id": "msg_example123",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Hello! How can I help you today?"
    }
  ],
  "model": "your-model-name",
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": {
    "input_tokens": 12,
    "output_tokens": 9
  }
}
```

### Response Fields

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier for the message. |
| `type` | string | Response object type; `"message"` for a message response. |
| `role` | string | The speaker; `"assistant"` for Claude's response. |
| `content` | array | Content blocks returned by the model. |
| `model` | string | The model that generated the response. |
| `stop_reason` | string or `null` | Why generation stopped. |
| `stop_sequence` | string or `null` | The custom stop sequence that ended generation, if applicable. |
| `usage` | object | Input and output token counts, with cache-related counts when applicable. |

### Content Blocks

The `content` array contains one or more typed blocks. A simple text response typically contains a block like this:

```json
{
  "type": "text",
  "text": "Hello! How can I help you today?"
}
```

When tools are enabled, Claude can return a `tool_use` block instead of (or alongside) text:

```json
{
  "type": "tool_use",
  "id": "toolu_example123",
  "name": "get_weather",
  "input": {
    "location": "Paris"
  }
}
```

The `tool_use` block is a request for your application to run the named tool; it is not the tool's result.

### Stop Reasons

| `stop_reason` | Meaning |
|---|---|
| `"end_turn"` | Claude finished its response. |
| `"max_tokens"` | Generation reached the request's `max_tokens` limit; the response may be incomplete. |
| `"stop_sequence"` | Generation stopped after matching a custom stop sequence. |
| `"tool_use"` | Claude is requesting that your application run a tool. |

### Usage

| Field | Description |
|---|---|
| `input_tokens` | Tokens used by the input. |
| `output_tokens` | Tokens generated in the response. |
| `cache_creation_input_tokens` | Input tokens written to the prompt cache, when applicable. |
| `cache_read_input_tokens` | Input tokens read from the prompt cache, when applicable. |

Usage counts can include cache-related fields depending on the request. Token prices vary by model.

### Streaming Response

Set `"stream": true` in the request to receive the response incrementally as Server-Sent Events (SSE).

### Example: Text Stream

Each SSE event has an `event:` line and a `data:` line. Events are separated by a blank line:

```text
event: message_start
data: {"type":"message_start","message":{"id":"msg_stream_example","type":"message","role":"assistant","content":[],"model":"your-model-name","stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":12,"output_tokens":1}}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" there!"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":4}}

event: message_stop
data: {"type":"message_stop"}
```

The text deltas combine to form `Hello there!`. A real stream may include `ping` events or additional content blocks.

### Streaming Events

| Event | When it occurs | What it contains |
|---|---|---|
| `message_start` | At the beginning of the stream. | The initial message object, including its ID, model, and input-token usage. |
| `content_block_start` | At the start of a content block. | The block and its index in the `content` array. |
| `content_block_delta` | As a content block is generated. | An incremental update, such as a text piece in `delta.text`. |
| `content_block_stop` | At the end of a content block. | The index of the completed block. |
| `message_delta` | Near the end of the stream; may occur more than once. | Message-level changes, including the final `stop_reason` and usage updates. |
| `message_stop` | At the end of the stream. | Signals that the stream has ended. |
| `ping` | Periodically, if sent. | A keepalive event; it carries no message content. |
| `error` | If an error occurs during streaming. | Error details; handle this as an error, not as a successful response. |

For tool-use streams, `content_block_delta` can contain partial JSON for the tool input instead of text. Accumulate the fragments and parse the complete input when the block ends.

## Useful links

* [API Reference](https://docs.anthropic.com/en/api/messages)
* [Streaming Docs](https://docs.anthropic.com/en/api/messages-streaming)
