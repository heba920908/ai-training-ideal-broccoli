## ADDED Requirements

### Requirement: Preserve stateless MCP behavior with authenticated SDK transport

The system SHALL use the existing T11 FastMCP tools and SDK client interfaces with a pinned
compatible dependency set. Authenticated `server/discover`, `tools/list`, and `tools/call`
requests SHALL use stateless MCP `2026-07-28` without legacy initialization or sessions.
Replacing HTTP auth headers SHALL affect the next request without reconnecting the client.

#### Scenario: Exercise the same transport before and after a header update
- **WHEN** a local-socket SDK client discovers the server, lists tools, updates its auth header,
  and invokes a tool using the same client
- **THEN** the server observes the current credential on every request without a reconnect
- **AND** the five existing T11 tool names and schemas remain unchanged

### Requirement: Protect every MCP request with an environment-configured API key

The API-key server SHALL validate a nonempty `MCP_API_KEY` using constant-time comparison
before MCP dispatch. Missing or incorrect keys SHALL return HTTP 401 with a generic error.
The API-key client SHALL send the key on discovery, listing, and tool calls. Missing server
configuration SHALL fail startup rather than accept an empty credential.

#### Scenario: Deny missing and incorrect API keys
- **WHEN** a caller omits the key or sends an incorrect key
- **THEN** the server returns HTTP 401 without executing a tool or exposing the configured key

#### Scenario: Permit a correctly authenticated API-key client
- **WHEN** the client uses the configured key for discovery, listing, and a tool invocation
- **THEN** all requests pass authentication and return correlated MCP responses

### Requirement: Validate access tokens and distinguish authorization failures

The OAuth server SHALL verify Bearer access tokens against cached Keycloak JWKS using RS256,
the expected issuer, required expiry, and an explicit MCP audience. The realm configuration
SHALL add that audience to access tokens. The server SHALL require the configured realm role,
return 401 for missing/invalid credentials with a Bearer challenge, and return 403 for valid
tokens lacking the role without exposing token claims. JWKS requests SHALL have finite timeouts.

#### Scenario: Reject invalid JWTs before dispatch
- **WHEN** a request has a missing, malformed, expired, wrong-signature, wrong-issuer,
  wrong-audience, or expiry-free token
- **THEN** it receives HTTP 401 and no user tool executes

#### Scenario: Distinguish a missing role from an invalid token
- **WHEN** a correctly signed, unexpired token has the expected issuer and audience but not
  the required realm role, including malformed role claims
- **THEN** the server returns HTTP 403 without attempting token refresh or exposing claims

#### Scenario: Use cached keys and handle key retrieval failures safely
- **WHEN** normal tokens use a cached key, an unfamiliar key ID appears, or JWKS retrieval fails
- **THEN** normal validation uses the cache, an unfamiliar ID permits at most one refetch per
  validation attempt, and unavailable keys never grant access
- **AND** key-service unavailability without usable keys yields a sanitized service-unavailable
  response rather than falsely reporting a user authorization decision

### Requirement: Complete browser Authorization Code with S256 PKCE safely

The OAuth token manager SHALL generate a fresh verifier, S256 challenge, and state, bind a
loopback callback listener before opening the browser, validate callback path/state/error/code,
and exchange the code with the verifier. Callback waiting SHALL end within 120 seconds.
The listener and its thread SHALL be released on success, failure, timeout, and cancellation.
Credentials, callback codes, verifiers, and token payloads SHALL NOT be logged or sent to DIAL.

#### Scenario: Authenticate through a valid callback
- **WHEN** the browser returns a code with the matching state
- **THEN** the manager exchanges it with the original verifier, validates and stores the token
  response, and closes the callback listener

#### Scenario: Reject bad callbacks without leaking resources
- **WHEN** a callback has a wrong path/state, OAuth error, or missing code, or the login times
  out or is cancelled
- **THEN** no unvalidated code is exchanged, errors are sanitized, and owned callback resources
  are released no later than the bounded login attempt ends
- **AND** an invalid callback does not prevent a later valid callback before the deadline

### Requirement: Refresh credentials proactively without replaying tool calls

The token manager SHALL track token expiry with a monotonic clock and a 30-second safety
margin. The OAuth client SHALL ensure freshness before discovery, listing, and tool calls,
serialize concurrent refreshes, preserve or rotate refresh tokens correctly, and update headers
on the existing HTTP client without reconnecting MCP. Invalid refresh responses SHALL NOT
partially replace valid token state. HTTP 403 SHALL NOT trigger refresh. Tool calls SHALL NOT
be automatically replayed after HTTP 401.

#### Scenario: Refresh once before an expired credential is used
- **WHEN** concurrent callers reach the refresh threshold
- **THEN** only one refresh occurs, subsequent requests carry the replacement access token,
  and the MCP client remains connected without repeating browser login

#### Scenario: Handle refresh rotation and failure
- **WHEN** refresh supplies a replacement refresh token, omits that field, fails, or is unavailable
- **THEN** the manager respectively stores the replacement, retains the existing refresh token,
  or reports a sanitized explicit-login-required failure without sending an expired request

### Requirement: Release authenticated client resources and preserve tool results

Both auth clients SHALL release SDK and HTTP resources on normal exit, exceptions, and
partial setup failure. Tool discovery SHALL preserve JSON schemas. Result conversion SHALL
handle empty and multiple content entries and surface `isError` rather than report success.

#### Scenario: Clean up a failed discovery
- **WHEN** client setup fails during authenticated discovery
- **THEN** all resources opened during setup are closed and the original failure is reported safely

#### Scenario: Preserve complete tool output
- **WHEN** a tool returns empty content, multiple text items, or an error-marked result
- **THEN** the client returns an intelligible complete result with error semantics preserved

### Requirement: Run a bounded model-agnostic DIAL agent in either authentication mode

The agent SHALL support API-key and OAuth CLI modes, interactive input, and single-query
capture. It SHALL use only the configured `OPENAI_BASE_URL`, `OPENAI_MODEL`, and
`OPENAI_API_KEY` provider settings, preserve exported environment precedence, authenticate
to DIAL, and reject public OpenAI hosts and credential-bearing provider URLs. It SHALL NOT
require a fixed model, model-specific generation parameters, or T9 modules. Tool processing
SHALL preserve call IDs, recover from malformed arguments, and stop after ten model/tool
rounds. MCP and DIAL timeouts SHALL be 60 and 90 seconds respectively; DIAL retries SHALL
be limited to one. MCP auth credentials SHALL NOT enter model messages.

#### Scenario: Execute a user query in either auth mode
- **WHEN** a learner selects API-key or OAuth mode and submits a query
- **THEN** the agent uses authenticated discovered tools through configured DIAL and can save
  a redacted trace without embedding any MCP credentials in the model conversation

#### Scenario: Bound invalid or repeated tool requests
- **WHEN** the model supplies malformed arguments or repeatedly requests tools
- **THEN** the agent returns correlated tool errors where appropriate and stops at the documented
  round bound instead of recursing indefinitely

### Requirement: Deliver isolated standalone code and truthful verification evidence

The exercise SHALL include final T11 code, required shared modules, source references,
pinned dependencies, credential-free infrastructure sources, offline tests, and a T10-style
task card under `app_development/t11-mcp-auth/`. Services SHALL bind to loopback and use
isolated T11 storage. Secrets SHALL come from environment configuration, with only
placeholders committed; credential-bearing realm imports SHALL be generated into ignored
storage. Evidence SHALL be redacted and local under `solution/output/`.

#### Scenario: Verify without the ephemeral course clone
- **WHEN** a learner follows the standalone setup and verification commands
- **THEN** imports, offline tests, and scoped Ruff checks run without the course clone or DIAL
  credentials, and the task card contains no durable dependency on ephemeral workspace links

#### Scenario: Capture live auth and refresh behavior
- **WHEN** real local services and configured DIAL are available
- **THEN** probes capture API-key success/failure, OAuth success/401/403, both account outcomes,
  and successful proactive refresh across the 60-second token lifetime without reconnecting
- **AND** synthetic CRUD fixtures are cleaned up without altering unrelated records or services

#### Scenario: Keep incomplete acceptance visible
- **WHEN** a live dependency or browser interaction prevents required verification
- **THEN** the task card records the blocker, affected tasks stay unchecked, and no sample
  transcript or premature archive is substituted for actual evidence

### Requirement: Gate implementation on reviewed OpenSpec approval

The proposal, design, acceptance scenarios, and ordered tasks SHALL be validated and presented
for explicit user approval before implementation or live experiments. After approval, routine
in-scope work SHALL continue autonomously through verified delivery and archiving. Material
scope/security changes, destructive actions, and user-decision blockers SHALL require renewed
approval. Plan approval SHALL NOT authorize commits or pushes.

#### Scenario: Review before autonomous execution
- **WHEN** the planning artifacts are ready but not approved
- **THEN** the agent requests review and does not implement the exercise
- **AND** after explicit approval it executes the reviewed tasks without repeated routine
  permission requests, subject to the stated exceptions