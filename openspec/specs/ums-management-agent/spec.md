# ums-management-agent Specification

## Purpose
Provide a local, DIAL-backed users-management agent that combines UMS (HTTP) and
DuckDuckGo (Podman STDIO) MCP tools with skill-guided, bounded tool use, Presidio
redaction of card and salary data, Redis conversation persistence, and a
sanitized streaming browser UI.

## Requirements

### Requirement: Provider configuration is model-agnostic and DIAL-only
The agent SHALL read its provider settings only from `OPENAI_BASE_URL`,
`OPENAI_MODEL`, and `OPENAI_API_KEY` (root `.env`, exported values taking
precedence), authenticate with an `Api-Key` header, and send no
model-specific request parameters.

#### Scenario: Configured deployment is used as-is
- **WHEN** the app starts with any configured DIAL deployment, including a non-GPT model
- **THEN** every chat completion targets that base URL and model
- **AND** no `reasoning_effort`, temperature, or model-name literal is added

#### Scenario: Missing or unsafe configuration fails fast
- **WHEN** a required variable is missing, the URL embeds credentials, or the host is the public OpenAI API
- **THEN** startup fails with a message naming the variable, never its value

### Requirement: Skill-guided startup prompt
On startup the app SHALL load validated skill metadata from the skills
directory and build a system prompt containing an escaped
`<available_skills>` XML block (name, description, and optional license,
compatibility, metadata, allowed-tools) plus instructions to load
`/<skill-name>/SKILL.md` with `read_skill` before acting. Full skill bodies
SHALL NOT be preloaded.

#### Scenario: Completed UMS skill is advertised
- **WHEN** the app starts with the completed `ums-user-management` skill
- **THEN** the system prompt advertises it with its description, license, and metadata
- **AND** the prompt does not contain the skill's workflow sections

#### Scenario: Skill content matches the real tools
- **WHEN** the skill file is checked against tools discovered from both MCP servers
- **THEN** every documented tool name exists and the operating rules require confirmation before add-after-enrichment and before delete

### Requirement: Confined skill file reads
`read_skill` SHALL return UTF-8 content only for regular files inside the
skills root, accepting paths with or without a leading slash.

#### Scenario: Valid skill path
- **WHEN** the model requests `/ums-user-management/SKILL.md`
- **THEN** the file content is returned as the tool result

#### Scenario: Escape or missing file
- **WHEN** the path traverses outside the root, is absolute elsewhere, follows a symlink outside the root, is a directory, or does not exist
- **THEN** a tool error string is returned with the same tool call ID and no outside content

### Requirement: Multi-MCP tool registry
The app SHALL register `read_skill`, every tool discovered from the UMS MCP
server over streamable HTTP, and every tool discovered from the DuckDuckGo MCP
server launched over STDIO with Podman, each advertised with its server schema.

#### Scenario: Both servers contribute tools
- **WHEN** startup completes with both servers reachable
- **THEN** UMS CRUD/search tools and DuckDuckGo search/fetch tools are callable through the agent

#### Scenario: Startup dependency unavailable
- **WHEN** an MCP server, Podman, or Redis is unavailable at startup
- **THEN** startup fails with a clear error and already-opened MCP sessions, STDIO containers, and Redis connections are closed

#### Scenario: Shutdown releases resources
- **WHEN** the app stops
- **THEN** both MCP sessions and the Redis client are closed and the STDIO container exits

### Requirement: Bounded Tool Use loop
The agent SHALL execute requested tool calls, append correlated tool messages,
and continue until the model returns a final answer, up to a fixed maximum
number of tool rounds in both streaming and non-streaming modes.

#### Scenario: Tool round then answer
- **WHEN** the model requests one or more tool calls and then answers
- **THEN** history contains the assistant tool-call message, one tool message per call ID, and the final assistant message in order

#### Scenario: Unknown tool or bad arguments
- **WHEN** the model calls an unregistered tool, sends invalid JSON arguments, or a tool raises
- **THEN** a tool error message with the matching tool call ID is appended and the loop continues

#### Scenario: Round limit reached
- **WHEN** the model keeps requesting tools past the limit
- **THEN** the loop stops and returns a clear limit message without another provider call

### Requirement: Streaming chat over SSE
Streaming chat SHALL emit `data: ` SSE events in this order: a
`conversation_id` event, interleaved `tool_activity` events (`call` with name
and arguments, `result` with name and redacted content) and OpenAI-style
`choices` content deltas, a final chunk with `finish_reason` `stop`, then
`data: [DONE]`. Fragmented streamed tool-call names, IDs, and arguments SHALL be
reassembled by index.

#### Scenario: Streamed tool call is reassembled
- **WHEN** a tool call arrives across several deltas
- **THEN** exactly one call with the concatenated name and arguments is executed and announced

#### Scenario: Provider failure mid-stream
- **WHEN** the provider or a tool fails during streaming
- **THEN** an `error` SSE event with a safe message is emitted, no secret or stack trace is included, and the stream ends

### Requirement: Redis conversation persistence
Conversations SHALL be stored as JSON under `conversation:<id>` and indexed in
the `conversations:list` sorted set by last update time. The first chat turn
SHALL inject the system prompt; every completed turn SHALL persist the full
updated message list.

#### Scenario: Conversation lifecycle
- **WHEN** a client creates, lists, reads, chats in, and deletes a conversation
- **THEN** list results are newest-first summaries with message counts, reads return the full message list, and after deletion both the key and index entry are gone

#### Scenario: Unknown conversation
- **WHEN** a client reads, chats in, or deletes an unknown ID
- **THEN** the API returns 404 and nothing is created

#### Scenario: Persisted history stays replayable
- **WHEN** a streamed turn completes, fails, or the client disconnects
- **THEN** stored history never contains an assistant tool-call message without its matching tool messages

### Requirement: REST API
The app SHALL expose `GET /health`, `POST /conversations`,
`GET /conversations`, `GET /conversations/{id}`,
`DELETE /conversations/{id}`, and `POST /conversations/{id}/chat` (stream
defaults to true; non-streaming returns `content` and `conversation_id`), and
SHALL serve the chat UI at `GET /`.

#### Scenario: Non-streaming chat
- **WHEN** a client posts a user message with `stream: false`
- **THEN** the response is JSON with the final assistant content and the conversation ID

#### Scenario: Invalid request
- **WHEN** the body is missing a message or uses a non-user role
- **THEN** the API returns a 4xx validation error without calling the provider

### Requirement: Local-only network exposure
The app SHALL bind to 127.0.0.1:8011, allow CORS only for loopback origins
without credentials, and all Compose services SHALL publish only on
127.0.0.1 under an isolated project using pinned image digests.

#### Scenario: Non-loopback origin
- **WHEN** a browser request carries a non-loopback Origin
- **THEN** no CORS allow header is returned

### Requirement: Safe browser rendering
The UI SHALL load conversations, create a conversation titled from the first 50
characters of the first message (with `...` when longer), stream responses with
live tool indicators and a tool-history dropdown, delete conversations, and
render model Markdown only after sanitization with pinned, integrity-checked
libraries.

#### Scenario: Script injection in model output
- **WHEN** an assistant or tool message contains HTML such as `<img src=x onerror=...>` or `<script>`
- **THEN** no script executes and no event-handler attribute reaches the DOM

#### Scenario: End-to-end browser chat
- **WHEN** an operator sends a request that triggers tools in the served UI
- **THEN** a live tool indicator appears, content streams into one assistant bubble, the tool-history dropdown lists each call and result, and the sidebar shows the conversation

### Requirement: PII guardrail on tool results
Every tool result SHALL be redacted for credit card number, CVV, expiry date,
and salary values (YAML-like, JSON, Python-dict, and plain-text forms, without
Luhn validation) before it is sent to the model, emitted over SSE, or persisted.

#### Scenario: UMS user record is redacted
- **WHEN** a UMS tool returns a user with salary and credit card fields
- **THEN** those values are replaced with `***` in the model input, the SSE `result` event, and Redis
- **AND** non-sensitive fields such as name and email are unchanged

#### Scenario: Non-PII content is unchanged
- **WHEN** a tool result contains no matching values, including `salary: None`
- **THEN** the content is returned unchanged

### Requirement: Course sample requests succeed live
With the Compose stack running and DIAL configured, the five course sample
requests SHALL complete through the agent using agent-owned fixture users for
any mutation.

#### Scenario: Search, add, update, delete, and web summary
- **WHEN** the operator runs the surname search, add-with-enrichment, update-email, delete-with-confirmation, and web-news requests
- **THEN** each produces the expected tool sequence and a coherent answer
- **AND** add shows the proposed profile and delete warns and waits before mutating
- **AND** only fixture users created during the run are changed and they are removed afterwards

### Requirement: Standalone delivery
The tracked solution SHALL run and pass its offline tests from
`app_development/t13-final-task/solution/` without importing the fork, contain
no secrets or images, and document exact setup, run, test, and shutdown
commands.

#### Scenario: Standalone verification
- **WHEN** the offline suite and lint run from the standalone root
- **THEN** they pass and copied files match the fork byte for byte
