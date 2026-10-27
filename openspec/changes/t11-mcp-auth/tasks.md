## Execution Status

User explicitly approved the reviewed change, including the `mcp-users` audience,
before implementation. Verified 2026-10-27: 161 offline tests pass in both the
fork and standalone delivery; scoped Ruff lint/format, source comparison, secret
scan, and permanent links pass. Real API-key discovery/CRUD and configured-DIAL
single-query checks pass with owned-fixture cleanup. Isolated UMS uses 8042 to
avoid the existing T10 listener on 8041; no T9/T10 services or data were removed.

Task card and scenario mapping:
[T11 delivery](../../../app_development/t11-mcp-auth/README.md).
Sanitized live/runtime/verification evidence is local and ignored under the
solution's `output/` directory. No credentials were committed or captured; no
commits or pushes were made.

**Blocked:** Keycloak passwords are not configured. Both user-driven browser
logins, live JWT negatives/post-expiry refresh, and OAuth DIAL acceptance remain
unverified. Tasks 6.3, 6.4, 7.4, and 7.5 remain unchecked; do not archive.

## 1. Plan Review Gate

- [x] 1.1 Validate this change with `openspec validate t11-mcp-auth --strict`, present proposal/design/spec/tasks for review, and obtain explicit user approval before implementation or live experiments. Confirm the explicit MCP audience decision; leave all implementation tasks unchecked until verified.

## 2. Stateless SDK Contract and API-Key Slice

- [x] 2.1 In the course fork, add failing `t11_mcp_auth/test_clients.py` local-socket tests for authenticated discovery/list/call, preserved T11 schemas, same-client header replacement, and no initialization/session reconnect. Resolve and pin a compatible FastMCP/MCP/httpx2 test/runtime set in `requirements.txt`; run `python -m pytest -q t11_mcp_auth/test_clients.py` and require this contract to pass before proceeding.
- [x] 2.2 Add failing configuration and API-key tests in `test_auth.py` and `test_agent.py`; implement `config.py`, placeholder-only `.env.example` additions, `auth/api_key_auth.py`, and `api_key_mcp_server.py`. Require a nonempty environment key, constant-time comparison, loopback app binding, and 401 before dispatch for absent/wrong keys. Verify with `python -m pytest -q t11_mcp_auth/test_auth.py t11_mcp_auth/test_agent.py`.
- [x] 2.3 Complete `ApiKeyMCPClient` using the contract-tested transport; add failing tests for auth on every request, schema preservation, complete/empty/error results, and resource closure on normal/failed entry. Implement minimal lifecycle/result helpers within the existing client boundary and rerun `test_clients.py`.

## 3. JWT Boundary and Local Keycloak Configuration

- [x] 3.1 Add generated-RSA-key tests in `test_auth.py` for valid JWTs, missing/malformed credentials, missing expiry, wrong signature/issuer/audience, expiry, absent/malformed roles, and no downstream dispatch on denial. Implement `auth/oauth.py` and `oauth_mcp_server.py` with RS256, required issuer/expiry/audience, Bearer 401 challenge, generic 403, finite JWKS timeouts, cache reuse, bounded unknown-key refetch, and sanitized fail-closed key-service errors; rerun `test_auth.py`.
- [x] 3.2 Add a credential-free Keycloak realm template and environment-driven runtime rendering in the existing `keycloak/` boundary. Configure S256 public-client login, explicit MCP audience mapper, allowed/no-role accounts, and 60-second token TTL without committed passwords or enabled password grant. Update compose for loopback ports and isolated T11 storage. Add offline rendering/realm-configuration checks to `test_auth.py`, including absence of secrets in tracked templates; rerun those tests without starting live services.

## 4. PKCE, Callback Cleanup, and Proactive Refresh

- [x] 4.1 Add failing `test_oauth.py` tests for PKCE challenge generation, authorization parameters, listener readiness, path/state/error/code validation, invalid-then-valid callback, and cleanup on success/timeout/cancellation/token-exchange failure. Complete the corresponding `_oauth_keycloak.py` helpers using bounded HTTP requests and a 120-second callback deadline; run `python -m pytest -q t11_mcp_auth/test_oauth.py`.
- [x] 4.2 Add fake-clock/concurrency tests for the 30-second refresh margin, invalid token responses, refresh-token preservation/rotation, missing refresh tokens, and refresh failures. Implement atomic token storage and serialized refresh with expiry recheck; rerun `test_oauth.py` without real waits or external services.
- [x] 4.3 Complete `OauthHttpMCPClient` with freshness checks before discovery/list/call and header replacement on the existing HTTP client. Extend `test_clients.py` to prove one refresh for concurrent requests, no reconnect, no browser reopening, no 403 refresh, no automatic 401 tool replay, and SDK/HTTP cleanup after failed auth/discovery. Rerun `test_clients.py` and `test_oauth.py`.

## 5. Model-Agnostic DIAL Agent

- [x] 5.1 Add failing `test_agent.py` tests for ancestor environment loading/export precedence, DIAL request shape, unsafe-provider rejection, credential separation, T11-only imports, malformed tool arguments, correlated errors, and a ten-round bound. Adapt `_agent.py` and `app.py` to the approved provider contract, 60-second MCP/90-second DIAL timeouts, and at most one DIAL retry; rerun `test_agent.py`.
- [x] 5.2 Add and test `--auth api-key|oauth`, optional single-query/output capture, and interactive exit/quit/EOF paths. Ensure captures redact auth headers, tokens, callback codes, verifiers, and token-endpoint errors before writing; rerun `test_agent.py` and client regressions.

## 6. Real Acceptance and Safe Evidence

- [x] 6.1 Add failing `test_probe.py` checks for safe capture serialization, nonzero failure exit, and owned-fixture cleanup in `finally`; implement `probe.py` for real auth/status/discovery/CRUD checks and verify with `python -m pytest -q t11_mcp_auth/test_probe.py`. Ensure no captured auth value or unrelated record is exposed or altered.
- [x] 6.2 Check local port ownership and start only the isolated T11 services. Run real API-key success/failure and synthetic CRUD probes; capture sanitized requests/statuses/responses and cleanup evidence. Do not stop or delete existing T9/T10 services, records, or volumes to force a test branch.
- [ ] 6.3 Exercise browser PKCE with both course accounts, recording allowed access and role-denied 403. Verify JWT negative cases and a successful post-expiry proactive refresh without reconnecting. Have the user enter login secrets directly in the browser; leave this task blocked and unchecked when required interaction or services are unavailable.
- [ ] 6.4 Run an actual configured-DIAL single query in each auth mode using owned synthetic data, recording safe tool traces and final responses. Record runtime versions/image digests, refresh events, fixture cleanup, and a machine-readable acceptance summary. Report blockers rather than inventing output.

## 7. Standalone Delivery and Completion

- [x] 7.1 Copy final code, only required shared modules, pinned dependencies, safe realm sources, compose configuration, source-task reference, and tests into `app_development/t11-mcp-auth/solution/`. Add ignore rules for local output and generated realm secrets. Run imports and the full offline suite with the fork excluded from the import path.
- [x] 7.2 Run `python -m pytest -q t11_mcp_auth`, `ruff check t11_mcp_auth`, and `ruff format --check t11_mcp_auth` in both fork and standalone directories using the pinned environment. Capture real verification output, compare delivered source content, and scan copied artifacts/captures for secrets without printing their values.
- [x] 7.3 Write the T10-style task card with source revision, exact dependency/startup/probe/auth-mode/test/cleanup commands, expected browser steps, observed outcomes, audience decision, and local-only authorization limitations. Update the root progress table, check permanent links, and preserve the existing topic notes and unrelated work.
- [ ] 7.4 Reconcile every delta-spec scenario to tests or real evidence; mark only verified tasks complete and run `openspec validate t11-mcp-auth --strict`. If any required check is blocked, report it and do not archive or declare acceptance complete.
- [ ] 7.5 After all acceptance evidence is complete, sync/archive the change, move its archive into `workspace/openspec/archive/`, and validate the resulting living specification. Leave all work uncommitted and unpushed unless separately authorized.