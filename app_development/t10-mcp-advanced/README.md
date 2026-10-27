# T10: MCP Advanced (Server and Client)

Implement the course's stateless MCP `2026-07-28` server, five user-management
tools, a custom JSON-RPC HTTP/SSE client, and a DIAL agent that can use either
the MCP SDK or the custom client. Real protocol and agent captures are generated
locally under `solution/output/`, following the T7 layout.

## Source

- Course: <https://github.com/epam/ai-applications-development-from-api-to-agents>,
  Python exercise `t10_mcp_advanced`, source revision
  `2c55dc448f2c80c35962f92a17d5f29d333222b6`.
- Original task and protocol reference, copied from the fork:
  [solution/t10_mcp_advanced/README.md](solution/t10_mcp_advanced/README.md).
- Final code: [solution/t10_mcp_advanced](solution/t10_mcp_advanced), with the
  required shared modules in [solution/commons](solution/commons).
  The ephemeral course clone is not needed to run this solution.
- This task implements the course's explicitly specified **stateless** protocol.
  There is no `initialize` handshake, session ID, GET event stream, or DELETE
  session shutdown. Older stateful lifecycle diagrams are not its contract.

## Tasks

- [x] Register get, search, create, update, and delete tools with JSON schemas.
- [x] Implement discovery, metadata validation, complete results, and cache hints.
- [x] Implement HTTP header/origin/media validation and JSON/SSE responses.
- [x] Complete the custom HTTP client, including discovery, schema conversion,
  response correlation, SSE parsing, and cleanup.
- [x] Connect both SDK and custom clients to UMS and web-search MCP servers.
- [x] Adapt the streaming agent to model-agnostic DIAL with bounded tool execution.
- [x] Capture actual HTTP probes, both course-query runs, a custom-client
  search/create experiment, cleanup, and verification output.
- [x] Verify the course fork and standalone solution with offline tests and Ruff.

## Provider and Data Boundaries

Only `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` from the repository
root `.env` are required for agent runs. Configuration finds the nearest ancestor
`.env`, preserves exported variables, uses DIAL `Api-Key` authentication, and
never prints credentials. See [../../.env.example](../../.env.example).
Use the configured HTTPS DIAL deployment URL and model unchanged. Public OpenAI
hosts and URLs with embedded credentials, query strings, or fragments are rejected.
No fixed model, temperature, or reasoning parameter is required.

The MCP server, HTTP probes, and offline tests need no DIAL credentials.
The agent stops after at most ten model/tool rounds. Tool errors return to the
model with the matching call ID. Duplicate tool names are rejected, and clients
close on exit or failed setup. Custom MCP HTTP requests have a 60-second timeout;
DIAL requests have a 90-second timeout and at most one retry.

This is a **local training service**, not a production system. CRUD probes use
owned synthetic profiles with `example.invalid` emails and clean them up in
`finally`. The requested public-person experiment may create a profile in the
mock service. Web pages and model-generated biographies are not authoritative
identity verification. Review sources and fields before using any resulting
record outside this exercise. Do not copy real customer data into the service.

The shared course service client is synchronous; T10 runs it in worker threads
instead of blocking the MCP event loop. Its original API and models are bundled
unchanged. Its service address is `http://localhost:8041`.

## How to Run

Requires Python 3.11+, `uv`, `curl`, and Docker Compose or Podman Compose.
Runtime and test dependencies are pinned in
[solution/t10_mcp_advanced/requirements.txt](solution/t10_mcp_advanced/requirements.txt).
Commands below run from the repository root. In each new terminal, set:

```bash
SOLUTION="$PWD/app_development/t10-mcp-advanced/solution"
REQS="$SOLUTION/t10_mcp_advanced/requirements.txt"
OUT="$SOLUTION/output"
mkdir -p "$OUT"
set -o pipefail
```

### 1. Start the Dependencies

```bash
podman compose -p t10-mcp \
  -f "$SOLUTION/t10_mcp_advanced/docker-compose.yml" up -d
curl --fail --silent --show-error http://localhost:8041/health
```

Replace `podman compose` with `docker compose` for Docker. Wait until the health
request succeeds before running probes. UMS binds to `127.0.0.1:8041`; DDG MCP
binds to `127.0.0.1:8010`. Data is stored in the compose file's adjacent
`data-t10/` directory, not in this repository's tracked files. The mock image
can seed synthetic users despite `GENERATE_USERS=false`; always inspect the
requested user's presence rather than assume the directory is empty.

Do not run a second copy on occupied ports. Stop an earlier T9/T10 deployment
only when it is yours to stop. `--ums-url` and `--web-url` configure agent MCP
addresses; moving the shared UMS backend off 8041 also requires adapting its
bundled service endpoint. Container tags are mutable upstream; captured runtime
metadata records the actual image digests used for these experiments.

### 2. Start the MCP Server

In a separate terminal with the variables above:

```bash
uv run --with-requirements "$REQS" --directory "$SOLUTION" \
  python -m t10_mcp_advanced.mcp_server.server
```

The endpoint is `http://127.0.0.1:8006/mcp`. It binds only to localhost. A browser
GET returns **405**, which is expected: this endpoint accepts MCP POST requests.
For another MCP port, use:

```bash
uv run --with-requirements "$REQS" --directory "$SOLUTION" \
  python -m uvicorn t10_mcp_advanced.mcp_server.server:app \
  --host 127.0.0.1 --port 8007
```

### 3. Postman-Equivalent HTTP Tests

```bash
uv run --with-requirements "$REQS" --directory "$SOLUTION" \
  python -u -m t10_mcp_advanced.probe \
  --url http://127.0.0.1:8006/mcp --output-dir "$OUT" \
  2>&1 | tee "$OUT/protocol.txt"
```

This performs **26 actual HTTP exchanges**, captures request bodies and safe
headers, HTTP statuses, content types, raw JSON/SSE responses, and assertions in
`protocol.json` and `protocol_summary.json`. It covers discovery, five tool
schemas, create/get/search/update/delete, reading the deleted fixture, origin and
Accept rejection, missing metadata, unsupported version, header mismatches,
base64 tool headers, unknown tool/method, obsolete initialization, parse errors,
notifications, and GET/DELETE rejection. A failed assertion exits nonzero.

To reproduce a single exchange with curl or Postman:

```bash
curl --silent --show-error --include http://127.0.0.1:8006/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/list' \
  --data '{"jsonrpc":"2.0","id":"manual-list","method":"tools/list","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientInfo":{"name":"postman-equivalent","version":"1.0"},"io.modelcontextprotocol/clientCapabilities":{}}}}' \
  | tee "$OUT/manual_tools_list.txt"
```

Expected: HTTP **200**, `Content-Type: text/event-stream`, and a `data:` JSON-RPC
response with ID `manual-list`, five tools, `resultType: complete`, server
identity, and caching hints. No initialization request is needed. For Postman,
use the same URL, POST, headers, and raw JSON body. For `tools/call`, also set
`Mcp-Name` to the exact `params.name`; see the captured probe requests for all
negative cases and the course reference for the error-code table.

### 4. Run Both Agents With Real DIAL Output

```bash
env -u OPENAI_API_KEY -u OPENAI_BASE_URL -u OPENAI_MODEL \
  uv run --with-requirements "$REQS" --directory "$SOLUTION" \
  python -u -m t10_mcp_advanced.agent.app \
  --client sdk --course-query --output-dir "$OUT" \
  2>&1 | tee "$OUT/agent_sdk.txt"

env -u OPENAI_API_KEY -u OPENAI_BASE_URL -u OPENAI_MODEL \
  uv run --with-requirements "$REQS" --directory "$SOLUTION" \
  python -u -m t10_mcp_advanced.agent.app \
  --client custom --course-query --output-dir "$OUT" \
  2>&1 | tee "$OUT/agent_custom.txt"
```

`--course-query` sends exactly: `Check if Arkadiy Dobkin present as a user, if
not then search info about him in the web and add him`. Unsetting exported
variables makes the root `.env` authoritative; omit `env -u ...` when intentionally
using exported provider settings. Each run saves its real transcript plus
`agent_sdk.json` or `agent_custom.json`, containing messages, tool calls, model
name, and call count, without the provider key. Rerunning overwrites these files;
use a different output directory to retain earlier experiments.

To reproduce the custom client's search/create branch without deleting the
public-person profile, use a distinct clearly synthetic training identity:

```bash
mkdir -p "$OUT/custom-create"
env -u OPENAI_API_KEY -u OPENAI_BASE_URL -u OPENAI_MODEL \
  uv run --with-requirements "$REQS" --directory "$SOLUTION" \
  python -u -m t10_mcp_advanced.agent.app --client custom \
  --query 'Check whether the synthetic training user named T10Custom with surname ArkadiyDobkin exists. If absent, search the web for public information about Arkadiy Dobkin, then add a clearly labeled synthetic training profile with name T10Custom, surname ArkadiyDobkin, email t10-custom@example.invalid and an about_me that labels the profile synthetic and cites the source URL. Do not alter the actual Arkadiy Dobkin profile. Do not add any private fields.' \
  --output-dir "$OUT/custom-create" \
  2>&1 | tee "$OUT/custom-create/agent_custom.txt"
```

This exact identity was cleaned up after the recorded run. If it already exists
on a rerun, the correct behavior is to return it, not duplicate it. For another
fresh branch experiment, choose a new synthetic identity and `example.invalid`
email. Record its ID and explicitly delete only that owned fixture afterward,
using the `delete_users` tool or a query such as `Delete only synthetic training
user ID <created-id>, named T10Custom ArkadiyDobkin`. Never delete an existing
person to force a branch. Cleanup evidence is in `custom-create/cleanup.txt` and
`custom-create/after_cleanup.json`.

For interactive chat, omit `--course-query` and `--query`; enter `exit`, `quit`,
or EOF to finish. Both modes discover seven tools: five from UMS and `search`
and `fetch_content` from DDG. Client selection applies to both MCP servers.

### 5. Offline Tests and Static Checks

```bash
uv run --with-requirements "$REQS" --directory "$SOLUTION" \
  python -m pytest -q | tee "$OUT/verification_standalone.txt"
uv run --with-requirements "$REQS" \
  ruff check "$SOLUTION/t10_mcp_advanced" \
  | tee -a "$OUT/verification_standalone.txt"
uv run --with-requirements "$REQS" \
  ruff format --check "$SOLUTION/t10_mcp_advanced" \
  | tee -a "$OUT/verification_standalone.txt"
```

The **44 offline tests** include real local-socket SDK/custom round trips,
HTTP error semantics, split-write SSE, notifications, response correlation,
malformed envelopes, fixture cleanup, environment precedence, unsafe-provider
rejection, DIAL request shape, duplicate routing, and the tool-round limit.
No DIAL or external service is contacted. Static checks cover T10; bundled
shared course modules are preserved rather than restyled.

### Shutdown

Stop the host MCP server with Ctrl+C, then:

```bash
podman compose -p t10-mcp \
  -f "$SOLUTION/t10_mcp_advanced/docker-compose.yml" down
```

Compose shutdown retains `data-t10/`. Removing it destroys that local service's
profiles, so do not remove it merely to rerun an experiment.

## Deliverables and Local Output

| Artifact | Purpose |
| --- | --- |
| [solution/t10_mcp_advanced/mcp_server](solution/t10_mcp_advanced/mcp_server) | Raw HTTP/SSE server, request/result models, dispatch, and five tools |
| [solution/t10_mcp_advanced/agent](solution/t10_mcp_advanced/agent) | SDK/custom clients, streaming DIAL agent, and CLI |
| [solution/t10_mcp_advanced/config.py](solution/t10_mcp_advanced/config.py) | Ancestor environment loading and safe provider configuration |
| [solution/t10_mcp_advanced/probe.py](solution/t10_mcp_advanced/probe.py) | Reproducible Postman-equivalent HTTP probes and capture writer |
| [solution/t10_mcp_advanced/docker-compose.yml](solution/t10_mcp_advanced/docker-compose.yml) | Local UMS/DDG prerequisites with isolated data and loopback ports |
| [solution/t10_mcp_advanced/test_clients.py](solution/t10_mcp_advanced/test_clients.py) | Both-client socket tests, SSE framing, and malformed-response regressions |

Generated evidence is local and ignored by [.gitignore](.gitignore):
`protocol.txt`, `protocol.json`, `protocol_summary.json`, `agent_sdk.txt`,
`agent_sdk.json`, `agent_custom.txt`, `agent_custom.json`, `custom-create/`,
`verification_fork.txt`, `verification_standalone.txt`, `runtime.json`, and
`summary.json`. The files are real captures, not authored sample transcripts.
The probe and agent CLIs regenerate their own captures; runtime and consolidated
summary files describe this recorded run, not automatic future success claims.

## Results / Notes

Verified **2026-10-27**: **44 offline tests passed in both copies**. T10 Ruff and
format checks passed. The final standalone server passed **26/26 real HTTP
probes**. Both real agent modes discovered all seven tools with the configured
DIAL deployment `DeepSeek-V4-Flash-2026-04-23`; that observed model is not a
code dependency.

| Experiment | Actual Observed Outcome | DIAL Calls |
| --- | --- | --- |
| SDK, exact course query | User initially absent; called `search_users`, web `search`/`fetch_content`, then `add_user`; created mock profile ID 1001. | 8 |
| Custom, exact course query | Found ID 1001 created by the SDK run; returned it without another web search or duplicate creation. | 2 |
| Custom, separate synthetic identity | Called directory search, web search/content retrieval, then `add_user`; created clearly labeled synthetic ID 1002 with an `example.invalid` email. | 7 |
| Synthetic cleanup | `delete_users` succeeded; a subsequent directory search returned `[]`. | 0 |

Some fetched web pages were inaccessible; the agent received those tool errors
and continued using other sources. The SDK-created record includes biographical
and contact claims drawn from secondary web results. These claims were **not
independently verified** and the record must not be treated as authoritative.
The separate synthetic experiment avoids real contact details and retains source
URLs in its description. IDs and model responses vary across reruns.

Original T10 notes and diagrams were left untouched. No secrets, environments,
container data, commits, or pushes are included in the deliverable.