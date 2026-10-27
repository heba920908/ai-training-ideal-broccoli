## Context

T11 already defines a FastMCP server, five user tools, two Starlette auth middlewares,
two SDK-client wrappers, and an OAuth token manager. Its TODOs span API-key validation,
JWT/JWKS handling, S256 PKCE, token exchange and refresh, client lifecycle, and agent wiring.
The starter also embeds credentials, imports T9 types, specifies model-dependent generation
parameters, and recurses without a tool-round bound.

T10 provides the relevant delivery pattern: independently authenticated stateless MCP requests,
model-agnostic DIAL configuration, offline socket regressions, standalone packaging, and local
redacted evidence. T11 is not a request to replace FastMCP with T10's hand-written server.
The existing T10 open change and unrelated user files remain untouched.

## Goals / Non-Goals

**Goals:** Complete all T11 TODOs, preserve the starter's public class and tool interfaces,
prove request-level authentication and refresh without reconnecting, and produce reproducible
offline and live acceptance evidence in both the fork and standalone solution.

**Non-goals:** A custom raw MCP client/server, T10 changes, web-search integration, public
deployment, full MCP OAuth discovery/resource-metadata support, arbitrary identity providers,
fine-grained per-tool authorization, automated replay of mutating calls, commits, or pushes.

## Decisions

### 1. Retain the course abstractions and verify compatibility first

Keep `FastMCP`, `ApiKeyMCPClient`, `OauthHttpMCPClient`, `OAuthTokenManager`, and
`T11MCPClient`. Preserve the exact T11 tool names and argument schemas:
`get_user_by_id`, `delete_user`, `search_user`, `add_user`, and `update_user`.
Run the synchronous shared user-service client via worker threads where needed to avoid
blocking the async server. Bundle only the shared modules actually required by T11.

The first executable check is a local-socket SDK/FastMCP contract test. Pin one dependency
set only after it demonstrates `server/discover`, listing, and a call without legacy
initialization or session reconnects. A second request after HTTP-header replacement must
carry the replacement value on the same client. Do not assume the T10 dependency pins
or the starter's loose `httpx2` requirement are sufficient.

Alternative: copying T10's raw server would increase scope and discard the course's FastMCP
learning surface. Completing only marked TODOs would leave incompatible DIAL and lifecycle
behavior. Retaining the abstractions with focused compatibility fixes is the selected approach.

### 2. Environment configuration and local infrastructure

Use the nearest ancestor root `.env`, preserving exported environment values, as in T10.
Keep the provider contract limited to `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY`.
Use configured DIAL HTTPS endpoints and `Api-Key` authentication, rejecting public OpenAI
hosts and credential-bearing URLs. Do not add fixed model parameters or fallback models.

Authentication configuration includes `MCP_API_KEY`, `KEYCLOAK_URL`, `KEYCLOAK_REALM`,
`MCP_CLIENT_ID`, `MCP_REQUIRED_ROLE`, and a documented explicit `MCP_AUDIENCE` setting.
Use non-secret local defaults for URLs, realm, client ID, role, and audience; require the
API key and local Keycloak passwords from environment configuration without literal defaults.
Add only placeholder values to `.env.example`. Tests generate secrets and signing keys at
runtime rather than embedding them in source.

Bind UMS, Keycloak, both MCP endpoints, and callback listener to loopback. Use a separate
compose project and T11 data storage, preserving other exercises' containers and volumes.
Use a tracked credential-free realm template and render any credential-bearing import into
ignored local output at runtime. Disable default seeded credentials and render only the two
course test accounts plus required local administrator configuration. Never capture the
rendered credentials. Preserve the course token lifetime of 60 seconds and disable password
grant authentication; live authentication must exercise browser PKCE.

### 3. Authenticate before dispatch

Build both apps with `mcp.http_app(stateless_http=True)` and attach the corresponding
middleware before any MCP dispatch. Every MCP request is checked, including discovery/listing.
API-key comparison uses constant-time comparison against the configured nonempty key.
Missing/wrong keys return generic HTTP 401 without reaching a tool; missing server key
configuration fails startup rather than allowing an empty key.

JWT handling accepts a Bearer access token, pins RS256, verifies signature, issuer, required
expiry, and configured audience, then checks the exact required role in a well-formed
`realm_access.roles` list. Missing/invalid credentials return 401 with a Bearer challenge.
Valid tokens without the role return 403 without listing the token's claims or roles.

Cache JWKS in memory for normal validation. An unknown signing-key ID permits one bounded
refetch per validation attempt; do not recursively retry validation. Failed JWKS retrieval
with no usable key fails closed with a sanitized service-unavailable error, not authorization
success or a false assertion that the user supplied bad credentials. Use finite HTTP timeouts.

Audience validation intentionally differs from the starter's `verify_aud=False`: configure a
realm mapper adding the explicit MCP audience to access tokens and reject tokens for other
resources. This is a material decision included in the requested plan review. This remains a
local OAuth training integration, not proof of complete MCP authorization-spec compliance.

### 4. PKCE and callback lifecycle

Generate a fresh verifier, its unpadded SHA256 base64url challenge, and a fresh random state
for each login. Build the public-client authorization request with S256 and the configured
callback. Bind the listener before opening the browser, validate callback path/state and OAuth
errors, reject missing codes, and exchange the code with the verifier via form POST.

The callback wait is bounded to 120 seconds. Always close the listener and join its thread on
success, timeout, cancellation, or browser/token-exchange failure. Invalid callbacks must not
prevent a later valid callback within the deadline. The callback must not report successful
authentication until its required checks succeed. Never log query strings containing codes,
verifiers, tokens, passwords, or raw token-endpoint error bodies.

### 5. Refresh at the request boundary without reconnecting

Track expiry from `expires_in` using a controlled monotonic clock and the course's 30-second
safety margin. Validate token responses before publishing new state; preserve an existing
refresh token if the refresh response omits a replacement. Serialize concurrent refreshes and
recheck expiry after acquiring the refresh lock so callers do not rotate a token twice.

Before discovery, listing, or a tool call, ensure the access token is fresh. After refresh,
update the existing HTTP client's Authorization header; do not recreate or re-enter the MCP
client. Refresh failure or a missing refresh token produces a sanitized actionable error
requiring a new explicit login, with no silent browser reopening or password-grant fallback.
Do not refresh for HTTP 403. Do not automatically replay a tool call after HTTP 401 because
the call may mutate data. A fake-clock test covers the boundary without real waiting.

Both wrappers close SDK and HTTP resources on normal exit, exceptions, and partial entry
failure. Tool discovery preserves JSON schemas; tool results handle empty/multiple text
content and `isError` consistently instead of blindly selecting the first item.

### 6. DIAL agent and evidence

Replace the T9 type import with the T11 client interface. Add `--auth api-key|oauth`, optional
single-query capture, and interactive input with exit/quit/EOF handling. Keep tool-call IDs
and recover from invalid tool arguments. Use a maximum of ten model/tool rounds per query,
a 90-second DIAL timeout with at most one retry, and 60-second MCP HTTP request timeouts.

Only auth clients receive MCP credentials; only the model client receives DIAL credentials.
Never send tokens, passwords, API keys, callback codes, or verifiers to the model. Redact
authentication headers and sensitive response fields before writing any captures.

Provide a probe for API-key failures/success, OAuth failures/success, and synthetic CRUD
with cleanup in `finally`. Capture browser-PKCE success for the permitted account, 403 for
the account without the required role, and a successful post-refresh request without
reconnection. Record only safe statuses, tool traces, refresh events, and runtime metadata.
Human login is entered directly in the browser, never through chat or an agent question tool.

## Planned File Ownership

All code is developed first under the course fork's `t11_mcp_auth/` directory.

| Surface | Responsibility |
| --- | --- |
| `config.py`, `requirements.txt`, `ruff.toml` | Environment contract, compatible pinned runtime/test dependencies, scoped static checks |
| `mcp_server/auth/api_key_auth.py`, `api_key_mcp_server.py` | API-key boundary and app assembly |
| `mcp_server/auth/oauth.py`, `oauth_mcp_server.py` | JWT/JWKS/role boundary and app assembly |
| `mcp_server/_server.py` | Existing T11 tools and nonblocking service delegation |
| `agent/mcp_clients/_base.py`, `api_key_mcp_client.py`, `oauth_mcp_client.py` | Existing interfaces, SDK lifecycle, auth headers, results |
| `agent/mcp_clients/_oauth_keycloak.py` | PKCE callback, exchange, expiry, serialized refresh |
| `agent/_agent.py`, `agent/app.py` | Bounded DIAL conversation and auth-mode CLI |
| `docker-compose.yml`, `keycloak/`, `probe.py` | Isolated local services, credential-free realm source, real redacted checks |
| `test_clients.py`, `test_auth.py`, `test_oauth.py`, `test_agent.py`, `test_probe.py` | Focused offline contract and regression coverage |

Consolidate tests in these owning files rather than creating a separate file for each case.
Final delivery is `app_development/t11-mcp-auth/solution/`, with required shared `commons/`
modules, the source task reference, and ignored `solution/output/`. Tracked task-card links
must resolve within the delivered repository, not depend on the ephemeral fork.

## Risks / Trade-offs

- SDK/FastMCP version drift: resolve with the first socket test before full implementation.
- Header snapshots inside the transport: falsify with a same-client two-request regression.
- Browser callback race or occupied port: report the conflict, clean up owned resources, and
  never terminate an unrelated listener automatically.
- Keycloak realm imports do not necessarily update existing realms: use an isolated T11 realm
  store and document recreation only as a user-approved destructive operation.
- HTTP loopback is acceptable only for this local exercise. Public deployment and HTTPS
  termination are outside the approved scope.
- Live services or browser interaction may be unavailable: leave corresponding acceptance
  tasks unchecked and report a blocker instead of manufacturing evidence or archiving early.

## Verification and Approval

For each implementation task, write and run the focused failing test, implement the smallest
change, then rerun the same check. Offline tests must not contact DIAL, external Keycloak, or
UMS. Use local socket servers, generated RSA keys, fake clocks, and mocked HTTP dependencies.
Run full T11 tests plus scoped Ruff lint/format checks in the fork and standalone copies.
Run real local auth/CRUD probes and both real DIAL auth modes, recording post-expiry refresh.
Scan tracked artifacts and generated captures without printing secrets. Validate OpenSpec
strictly and reconcile every scenario to evidence before marking tasks complete or archiving.

This document, the proposal, delta specification, and tasks form the reviewable OpenSpec plan.
Implementation awaits explicit user approval. Approval authorizes autonomous in-scope
execution, not material scope changes, destructive operations, commits, or pushes.