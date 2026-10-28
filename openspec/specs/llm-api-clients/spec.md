# llm-api-clients Specification

## Purpose
An interactive console chat that talks to LLMs through several vendor APIs (OpenAI Chat Completions,
OpenAI Responses, Anthropic Messages, Gemini). Each vendor is called through its official SDK and
through raw HTTP, with sync and streaming modes, and all configuration comes from environment variables
so it runs against EPAM DIAL.

## Requirements

### Requirement: Interactive chat loop
The chat CLI SHALL read user input in a loop, send the full conversation history (all prior user and
assistant turns) to the selected client, display the reply, and append both messages to the history.
It SHALL terminate when the user enters `exit` (case-insensitive, surrounding whitespace ignored) and
SHALL skip empty input without calling the API.

#### Scenario: Multi-turn context is preserved
- **WHEN** the user says "My name is Ana" and then asks "What is my name?"
- **THEN** the second request contains both prior turns and the reply references "Ana"

#### Scenario: Exit
- **WHEN** the user enters ` EXIT `
- **THEN** the loop ends without calling the API

#### Scenario: Streaming vs synchronous mode
- **WHEN** the chat is started in streaming mode
- **THEN** the reply is printed incrementally as chunks arrive
- **WHEN** the chat is started in synchronous mode
- **THEN** the full reply is printed once it is received

### Requirement: Client contract
Every client SHALL take the conversation history, prepend or attach the configured system prompt in the
vendor's native format, return the reply as a single assistant-role message whose content is the full
reply text, and print that text to the console. In streaming mode the returned content SHALL equal the
concatenation of all printed chunks.

#### Scenario: System prompt is applied
- **WHEN** any client sends a request
- **THEN** the request carries the configured system prompt in the vendor-specific field (system message, `instructions`, `system`, or `system_instruction`)

#### Scenario: Streamed content equals returned content
- **WHEN** a streaming call completes
- **THEN** the returned message content equals the text printed to the console

### Requirement: SDK and raw-HTTP variants per vendor
For each vendor (OpenAI Chat Completions, OpenAI Responses, Anthropic, Gemini) there SHALL be one client
using the vendor's official SDK and one using plain HTTP. The raw-HTTP client SHALL parse the vendor's
streaming wire format (Server-Sent Events) itself, without the SDK.

#### Scenario: Raw-HTTP streaming parses SSE
- **WHEN** the raw-HTTP client streams a reply
- **THEN** it reads `data:` lines, extracts text deltas from each event, ignores non-text events, and stops at the vendor's end marker (`[DONE]`, `response.completed`, `message_stop`, or end of stream)

#### Scenario: HTTP error surfaces
- **WHEN** the API returns a non-200 status
- **THEN** the raw-HTTP client raises an error containing the status code and response body

### Requirement: API key validation and auth formatting
Clients SHALL reject a missing, empty, or whitespace-only API key with a `ValueError` at construction time.
OpenAI-style raw-HTTP clients SHALL send the key as `Authorization: Bearer <key>`.

#### Scenario: Empty key rejected
- **WHEN** a client is constructed with `api_key="  "`
- **THEN** a `ValueError` is raised before any network call

#### Scenario: Bearer formatting
- **WHEN** an OpenAI-style client is constructed with key `k`
- **THEN** its stored authorization value is `Bearer k`

### Requirement: Environment-driven DIAL configuration
Endpoints, model names, and API keys SHALL be read from environment variables, with defaults pointing to
the EPAM DIAL proxy. No API key SHALL appear in source code, documentation, or committed artifacts.

#### Scenario: Chat Completions uses OPENAI_BASE_URL and OPENAI_MODEL
- **WHEN** `OPENAI_BASE_URL` and `OPENAI_MODEL` are set
- **THEN** Chat Completions requests go to `<OPENAI_BASE_URL>/chat/completions` with that model

#### Scenario: Missing key fails fast
- **WHEN** the required key variable is unset
- **THEN** starting the app raises the empty-key `ValueError`

#### Scenario: No secrets in solution
- **WHEN** the solution code is copied into the repo and committed
- **THEN** the secret-scanning pre-commit hook passes
