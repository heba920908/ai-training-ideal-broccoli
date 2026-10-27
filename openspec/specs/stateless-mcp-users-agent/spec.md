# stateless-mcp-users-agent Specification

## Purpose
Provide the T10 course exercise's standalone stateless MCP server and dual-client
DIAL agent with reproducible protocol checks and evidence from real executions.

## Requirements

### Requirement: Process independent stateless MCP requests

The server SHALL support `server/discover`, `tools/list`, and `tools/call` over
HTTP POST using protocol version `2026-07-28`, without requiring initialization
or a session. Successful results SHALL include `resultType: complete` and server
identity metadata. Discovery and tool listings SHALL include `ttlMs` and
`cacheScope` caching hints. GET and DELETE on the MCP endpoint SHALL return 405.

#### Scenario: Discover and list without a handshake
- **WHEN** a client sends valid discovery and tool-list requests independently
- **THEN** the server returns correlated complete results with server identity,
  supported versions, tool capabilities, and five user-tool schemas
- **AND** neither request requires a session identifier

### Requirement: Validate transport and protocol boundaries

The server SHALL validate local browser origins, acceptance of JSON and SSE,
required protocol-version and client-capability metadata, and matching protocol,
method, and tool-name headers. It SHALL reject legacy initialization, unsupported
versions, and unknown methods with the course-documented HTTP/JSON-RPC errors.
It SHALL decode non-ASCII tool-name header values using the documented base64
sentinel. Accepted notifications SHALL receive HTTP 202 without a JSON-RPC body.

#### Scenario: Reject invalid request metadata and headers
- **WHEN** requests omit required metadata, mismatch routing headers, or request
  an unsupported protocol version
- **THEN** the server returns HTTP 400 with respectively `-32602`, `-32020`, or
  `-32022`, preserving request correlation where an ID was supplied

#### Scenario: Reject invalid origins and media negotiation
- **WHEN** a request has a disallowed origin or does not accept both response types
- **THEN** the server returns HTTP 403 or HTTP 406 respectively with a JSON-RPC error

#### Scenario: Reject obsolete and unknown operations
- **WHEN** the client requests legacy initialization or an unknown method
- **THEN** the server returns respectively HTTP 400 with `-32022` or HTTP 404
  with `-32601`

### Requirement: Execute user tools with distinct error semantics

The server SHALL expose get, search, create, update, and delete user tools with
JSON schemas and text results backed by the local user service. Unknown tools
SHALL produce JSON-RPC `-32602` errors with HTTP 200. Tool execution failures
SHALL produce complete results with `isError: true`, not protocol error envelopes.

#### Scenario: Manage an owned synthetic fixture
- **WHEN** a client creates, reads, searches, updates, and deletes its own profile
- **THEN** the results reflect each operation and the deleted profile cannot be read

#### Scenario: Distinguish a missing tool from a failed operation
- **WHEN** the client invokes an unknown tool and then invokes a known tool that fails
- **THEN** the former returns a JSON-RPC error and the latter returns an error-marked tool result

### Requirement: Support SDK and custom HTTP clients

Both client modes SHALL discover tools and invoke the stateless server. The
custom client SHALL attach metadata and routing headers on every request,
consume JSON and SSE replies, correlate response IDs, ignore preceding SSE
notifications, and report protocol errors. Both modes SHALL release HTTP and
SDK resources on normal exit and failed setup.

#### Scenario: Consume a streamed response
- **WHEN** an SSE reply arrives in split network reads with a notification before
  the final correlated response
- **THEN** the custom client returns the complete response rather than the notification

#### Scenario: Report a JSON protocol error
- **WHEN** an HTTP error response contains a JSON-RPC error envelope
- **THEN** the custom client reports its code and message rather than treating it
  as a successful tool result

### Requirement: Route a bounded agent through model-agnostic DIAL

The agent SHALL use only the configured `OPENAI_BASE_URL`, `OPENAI_MODEL`, and
`OPENAI_API_KEY` provider settings, load ancestor environment configuration
without overriding exported variables, and authenticate to DIAL without logging
credentials. It SHALL NOT call public OpenAI or require a fixed model or
model-specific generation parameters. The agent SHALL route tools to their
advertising server, reject duplicate names, preserve tool-call IDs, return tool
failures to the model, and stop after a finite documented number of tool rounds.

#### Scenario: Execute the course query through each client mode
- **WHEN** a learner submits the specified Arkadiy Dobkin query with the SDK or
  custom client connected to UMS and web-search servers
- **THEN** the agent checks the user directory and, if absent, searches the web
  and adds a profile using the respective discovered tools
- **AND** its actual tool trace and final response can be captured without credentials

#### Scenario: Recover from invalid model tool arguments
- **WHEN** the model requests an unknown tool or supplies malformed or non-object arguments
- **THEN** the conversation receives a correlated tool error rather than crashing

### Requirement: Deliver a reproducible standalone evidence bundle

The exercise SHALL include final code, required shared modules, dependency and
compose configuration, source references needed from workspace materials,
offline regression tests, and a T7-style task card. Commands SHALL run without
the ephemeral course clone and SHALL reproduce HTTP/Postman-equivalent probes
and both live agent modes. Generated captures SHALL reside in local
`solution/output/`. Reported results SHALL come from actual executions; blocked
checks SHALL be identified as unverified, not replaced with sample output.

#### Scenario: Reproduce captured checks without the clone
- **WHEN** a learner follows the packaged setup and verification commands
- **THEN** imports resolve within the standalone solution, offline tests run
  without DIAL, and live probes save requests, statuses, and real responses
- **AND** the task card states observed outcomes, safe fixture cleanup, and any
  external-service blockers without embedding secrets or durable workspace links
