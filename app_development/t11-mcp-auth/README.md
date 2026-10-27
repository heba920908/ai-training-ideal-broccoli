# T11: MCP Authentication

API-key and Keycloak OAuth protection for the course's stateless FastMCP user
tools, authenticated SDK clients, and a model-agnostic DIAL agent.

**Status:** Implemented and offline-verified. Real API-key CRUD and DIAL checks
passed. Browser OAuth acceptance remains blocked; this change is not archived.

## Source

- Course: <https://github.com/epam/ai-applications-development-from-api-to-agents>.
- Source revision: `2c55dc448f2c80c35962f92a17d5f29d333222b6`.
- Task reference: [solution/t11_mcp_auth/SOURCE.md](solution/t11_mcp_auth/SOURCE.md).
- Final code: [solution/t11_mcp_auth](solution/t11_mcp_auth), with only required
  shared modules in [solution/commons](solution/commons).
- Topic notes: [../t11_mcp_auth.md](../t11_mcp_auth.md).

The solution runs without the ephemeral course clone. It preserves the exact
T11 tool names and nested argument schemas, including `search_user`,
`delete_user`, `user_create_model`, and `user_update_model`. T10's different
tool names and hand-written server are not used.

## Tasks

- [x] Prove authenticated stateless discovery/list/call and same-client header updates.
- [x] Protect every request with a nonempty constant-time API-key check.
- [x] Verify RS256 signature, issuer, expiry, explicit audience, and realm role.
- [x] Complete S256 PKCE, validated callbacks, bounded cleanup, and serialized refresh.
- [x] Complete both client lifecycles, schemas, and empty/multiple/error results.
- [x] Add a bounded DIAL agent, both CLI modes, and redacted captures.
- [x] Add credential-free realm sources and isolated loopback infrastructure.
- [x] Run real API-key auth/CRUD and configured-DIAL checks with fixture cleanup.
- [x] Verify the standalone solution and fork with offline tests and Ruff.
- [ ] Complete allowed/no-role browser logins and live JWT-negative checks.
- [ ] Verify proactive refresh after real token expiry without reconnecting.
- [ ] Run the configured-DIAL single query using browser OAuth.
- [ ] Complete acceptance reconciliation and archive the OpenSpec change.

## Boundaries

Credentials come from the nearest ancestor `.env`, preserving exported values.
Only `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` configure DIAL.
The configured HTTPS endpoint receives `Api-Key`; public OpenAI hosts and
credential-bearing/query/fragment URLs are rejected. There are no fixed models,
temperature, or reasoning settings. DIAL requests have a 90-second timeout and
at most one retry. MCP requests have a 60-second timeout. Each query is bounded
to ten model requests; malformed tool arguments return correlated tool errors.

Configure the T11 values in [../../.env.example](../../.env.example) in the
ignored root `.env`. Never use the template's placeholder values as credentials.
The local accounts are `allowed-user` and `no-role-user`; their passwords and
the administrator password must be supplied locally, not through chat.

The approved audience is **`mcp-users`**, configurable as `MCP_AUDIENCE`.
The realm mapper adds it to access tokens, and the server validates it rather
than disabling audience checks. The default required realm role is `mcp-user`.
Missing/invalid credentials return 401; valid tokens without the role return 403.
JWKS failures return sanitized 503 when no usable key is available.

This is a local HTTP training integration, not a production deployment or full
MCP OAuth discovery/resource-metadata implementation. The role gates all tools,
not individual CRUD permissions. Tokens are held in memory; no password grant,
silent browser reopening, 403 refresh, or automatic 401 tool replay is used.

## Setup

Requires Python 3.11+, `uv`, and Docker Compose or Podman Compose. Run these
commands initially from the repository root:

```bash
ROOT="$PWD"
SOLUTION="$ROOT/app_development/t11-mcp-auth/solution"
REQS="$SOLUTION/t11_mcp_auth/requirements.txt"
OUT="$SOLUTION/output"
mkdir -p "$OUT"
uv venv "$OUT/.venv"
uv pip install --python "$OUT/.venv/bin/python" -r "$REQS"
PY="$OUT/.venv/bin/python"
cd "$SOLUTION"
```

Dependencies are pinned in
[solution/t11_mcp_auth/requirements.txt](solution/t11_mcp_auth/requirements.txt).
The verified transport set is FastMCP 4.0.5, MCP 2.2.0, and httpx2 2.14.0.

### Local Services

First check ownership of the ports; never stop another exercise to free them:

```bash
ss -ltnp '( sport = :8042 or sport = :8089 or sport = :8007 or sport = :8008 or sport = :9999 )'
"$PY" -m t11_mcp_auth.keycloak.render_realm
podman compose -p t11-mcp-auth --env-file "$ROOT/.env" \
  -f "$SOLUTION/t11_mcp_auth/docker-compose.yml" up -d
curl --fail --silent --show-error http://127.0.0.1:8042/health
```

Replace `podman compose` with `docker compose` where appropriate. The realm
renderer requires `KEYCLOAK_ADMIN_PASSWORD`, `MCP_ALLOWED_USER_PASSWORD`, and
`MCP_NO_ROLE_USER_PASSWORD`. It creates a private, ignored import with 0700
directory/0600 file permissions from
[solution/t11_mcp_auth/keycloak/realm-template.json](solution/t11_mcp_auth/keycloak/realm-template.json).
Do not capture that generated file or container environment values.

UMS uses `127.0.0.1:8042`, leaving the existing T10 service on 8041 untouched.
The only shared-client adaptation is an optional `USER_SERVICE_URL`; its
original 8041 default remains unchanged. T11 entry points set 8042 before tool
imports. The mock image can generate initial profiles before becoming healthy;
wait for health before probing and never assume the directory is empty.
Keycloak binds to 8089 with a separate T11 data volume. Realm imports
do not update an existing realm reliably; do not delete/recreate its volume
without reviewing the data and obtaining approval.

In two separate terminals, restore the variables above and run from `SOLUTION`:

```bash
"$PY" -m t11_mcp_auth.mcp_server.api_key_mcp_server
"$PY" -m t11_mcp_auth.mcp_server.oauth_mcp_server
```

These are separate foreground processes on `127.0.0.1:8007/mcp` and
`127.0.0.1:8008/mcp`. Requests use MCP `2026-07-28`, `server/discover`,
`tools/list`, and `tools/call`; no legacy initialization or sessions are needed.
Synchronous UMS operations run in worker threads.

### Probes And Browser Login

```bash
"$PY" -m t11_mcp_auth.probe --auth api-key --output-dir "$OUT/api-key"
"$PY" -m t11_mcp_auth.probe --auth oauth --verify-refresh \
  --output-dir "$OUT/oauth-allowed"
"$PY" -m t11_mcp_auth.probe --auth oauth --expect-forbidden \
  --output-dir "$OUT/oauth-no-role"
```

For the first OAuth run, log in directly in the opened browser as `allowed-user`.
The listener is bound on `http://127.0.0.1:9999/callback` before the browser opens.
PKCE uses S256; the login wait is bounded to 120 seconds. Invalid callbacks do
not consume the valid attempt. The realm's access-token lifetime is 60 seconds,
and the refresh probe waits past expiry before checking a changed credential
on the same SDK/HTTP clients. Normal requests refresh at the 30-second margin.

For the role-denied run, sign out of the previous Keycloak browser session first,
then log in as `no-role-user`; otherwise browser SSO may reuse the allowed user.
Expect discovery 403 with no CRUD dispatch. Do not enter passwords in chat,
shell arguments, screenshots, or captures. No-role and refresh checks require
separate login attempts.

Probes accept `--url` and `--ums-url` loopback overrides. They create only unique
synthetic `example.invalid` fixtures, verify ownership, and clean up in `finally`.
They never delete pre-existing users to force a branch. `summary.json` records
passed/failed/blocked scenarios and exits nonzero on unexpected failures;
`events.json` records sanitized operations. Successful SDK HTTP statuses are
explicitly unavailable in those summaries, not fabricated as 200.

### DIAL Agent

```bash
"$PY" -m t11_mcp_auth.agent.app --auth api-key \
  --query 'Use search_user to find only synthetic training users named T11. Do not modify records.' \
  --output-dir "$OUT/dial-api-key"
"$PY" -m t11_mcp_auth.agent.app --auth oauth \
  --query 'Use search_user to find only synthetic training users named T11. Do not modify records.' \
  --output-dir "$OUT/dial-oauth"
```

Omit `--query` for interactive input; `exit`, `quit`, and EOF close the clients.
Single-query captures contain messages, correlated tool traces, and final answers
in `agent_api-key.json` or `agent_oauth.json`. Auth headers, tokens, callback
codes, verifiers, and credential-bearing errors are redacted before capture or
model submission. DIAL credentials are not passed to MCP clients.

### Verification And Cleanup

```bash
set -o pipefail
env -u PYTHONPATH "$PY" -m pytest -q t11_mcp_auth | tee "$OUT/verification.txt"
"$OUT/.venv/bin/ruff" check t11_mcp_auth | tee -a "$OUT/verification.txt"
"$OUT/.venv/bin/ruff" format --check t11_mcp_auth | tee -a "$OUT/verification.txt"
podman compose -p t11-mcp-auth --env-file "$ROOT/.env" \
  -f "$SOLUTION/t11_mcp_auth/docker-compose.yml" stop
```

Stop the two owned foreground MCP processes with Ctrl-C. Do not use `down -v`
or remove other exercises' containers. Output, virtual environments, caches, and
rendered credentials are ignored, not committed. Screenshots are not bundled.

## Results / Notes

Observed on 2026-10-27 using Python 3.14.3:

- Offline suite: **161 tests** in both fork and standalone delivery; scoped
  Ruff lint/format checks pass. Standalone imports resolve only to this solution.
- Real API-key probes: missing/wrong keys 401; discovery/list and all five CRUD
  tools succeed. The uniquely owned fixture is verified absent afterward.
- Real configured-DIAL API-key query: two model requests, `get_user_by_id`, and
  a final answer reporting the synthetic fixture email. Cleanup returned 204,
  followed by a verified 404. No unrelated record was modified.
- Live evidence is local in ignored `solution/output/`: probe events/summary,
  `http-exchanges.json` with actual authenticated request/status/response
  captures, DIAL messages/final answer, and `acceptance-summary.json` with
  runtime versions and the actual UMS image digest. Evidence is not linked as
  a durable committed artifact.
- The T11-only test backend was stopped after verification. Existing T10
  services/records/volumes were not stopped or deleted.
- **Blocked:** Keycloak passwords are not configured. Allowed/no-role browser
  login, real JWT-negative checks, post-expiry refresh, and OAuth DIAL acceptance
  have not run. No sample transcript replaces them. Keep the OpenSpec change open.

### Acceptance Mapping

| Requirement / Scenario | Evidence |
| --- | --- |
| Stateless discovery/list/call, exact schemas, header replacement | `test_clients.py`; real authenticated HTTP captures |
| API-key denial before dispatch and correct-key success | `test_auth.py`; real 401 negatives and CRUD probe |
| JWT signature/issuer/audience/expiry/role and cached/bounded JWKS | `test_auth.py` with generated RSA keys; live Keycloak checks blocked |
| PKCE URL, callback validation, invalid-then-valid, timeout/cancellation cleanup | `test_oauth.py`, including continuous slow-header cancellation |
| Atomic token state, fake-clock threshold, refresh rotation/concurrency | `test_oauth.py`; live post-expiry check blocked |
| Same-client refresh, no 401 replay/403 refresh, lifecycle/results | `test_clients.py`; actual OAuth transport run blocked |
| DIAL configuration, credential separation, malformed arguments, ten-round bound | `test_agent.py`; real API-key DIAL capture; OAuth DIAL blocked |
| CLI/capture safety, nonzero failures, owned cleanup | `test_agent.py`, `test_probe.py`; real cleanup evidence |
| Isolated infrastructure and credential-free rendered realm sources | `test_auth.py`; T11-only live UMS container |
| Independent delivery and no fork dependency | full standalone suite, scoped Ruff, source comparison and secret scan |
| Approved-plan gate | explicit user approval of proposal/design/spec/tasks before implementation |
| Truthful incomplete acceptance | unchecked browser/live-refresh/OAuth-DIAL tasks; no archive |

The course `UserUpdate` excludes `about_me`; the probe changes the supported
`name` field instead of silently assuming unsupported updates work. Final review
also added regressions for streamed function-name fragments and bounded cleanup
while a callback connection continuously trickles incomplete headers.