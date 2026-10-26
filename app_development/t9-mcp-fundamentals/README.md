# T9: MCP Fundamentals

Complete the course Users Management MCP server and its streaming agent, using
HTTP or STDIO. The agent calls the OpenAI-compatible EPAM DIAL API and can combine
the users server with a DuckDuckGo MCP server.

## Source

- Course: <https://github.com/epam/ai-applications-development-from-api-to-agents>, Python task `t9_mcp_fundamentals`.
- The standalone [solution/](solution/) includes the required shared modules; the course clone is not required.
- Background: [../t9_mcp_fundamentals.md](../t9_mcp_fundamentals.md).
- Acceptance criteria: [../../openspec/specs/mcp-users-agent/spec.md](../../openspec/specs/mcp-users-agent/spec.md).

## Tasks

- [x] Register the five CRUD tools with validated request models.
- [x] Expose the PNG resource and two server prompts.
- [x] Implement HTTP and STDIO clients, schemas, tool results and cleanup.
- [x] Complete the DIAL streaming agent, system prompt and interactive app.
- [x] Support multiple HTTP servers and users STDIO plus Podman web-search STDIO.
- [x] Replace Docker STDIO launches with Podman by default.
- [x] Bundle dependencies, Podman Compose prerequisites, tests and smoke commands.
- [x] Verify the standalone package and record final results below.

## Setup

Requires Python 3.11+, `uv`, rootless Podman and `podman-compose`. All commands
below start from the repository root. Create the local environment once:

```bash
T9="$PWD/app_development/t9-mcp-fundamentals"
uv venv "$T9/.venv"
uv pip install --python "$T9/.venv/bin/python" \
  -r "$T9/solution/t9_mcp_fundamentals/requirements.txt"
```

In **each terminal**, set these paths before running the examples:

```bash
T9="$PWD/app_development/t9-mcp-fundamentals"
PY="$T9/.venv/bin/python"
export PYTHONPATH="$T9/solution"
```

The agent loads the nearest ancestor `.env` without overriding exported variables.
Set `OPENAI_BASE_URL`, `OPENAI_MODEL` and `OPENAI_API_KEY` as described in
[../../.env.example](../../.env.example). Do not source or print the file. No
specific model name, provider-specific tuning or additional DIAL variable is
required; the chosen deployment must support Chat Completions function calling.
Discovery and smoke checks do not require DIAL credentials.

Runtime packages are pinned in
[solution/t9_mcp_fundamentals/requirements.txt](solution/t9_mcp_fundamentals/requirements.txt):
FastMCP, MCP SDK, OpenAI SDK, Pydantic, Requests, python-dotenv and Pillow. The
packages for unrelated course exercises are deliberately not installed.

## Podman Prerequisites

Start the mock User Service and the DuckDuckGo HTTP MCP server:

```bash
podman-compose -p t9-mcp \
  -f "$T9/solution/t9_mcp_fundamentals/docker-compose.yml" up -d userservice ddg-mcp-server
curl --fail http://127.0.0.1:8041/health
```

If the User Service from T6 or T8 already uses port 8041, reuse it: start only
`ddg-mcp-server` with the same Compose command. Do not stop unrelated containers.
Both services publish only on loopback. The mock service uses `USERS_NUMBER=24`,
not the ignored `USER_COUNT` from the template. No host data directory is mounted;
`stop` preserves the container dataset, while `down` removes it. The service can
change users periodically. Swagger: <http://127.0.0.1:8041/docs>.

## HTTP

Start the users MCP server in one terminal:

```bash
"$PY" -m t9_mcp_fundamentals.mcp_server.http_server
```

It listens at <http://127.0.0.1:8005/mcp>. In another configured terminal:

```bash
# Discover tools, resources and prompts without calling DIAL
"$PY" -m t9_mcp_fundamentals.agent.app --discover-only \
  --prompt search_guidance --resource users-management://flow-diagram

# Interactive users agent
"$PY" -m t9_mcp_fundamentals.agent.app

# Optional users + web-search agent (one client per server)
"$PY" -m t9_mcp_fundamentals.agent.app --with-web-search

# Try just the DuckDuckGo HTTP server instead
"$PY" -m t9_mcp_fundamentals.agent.app --server-url http://127.0.0.1:8010/mcp
```

Repeat `--server-url` to connect arbitrary HTTP servers. Duplicate tool names fail
explicitly rather than silently routing to the wrong server.

## STDIO

The client starts and closes the local users MCP process itself. The User Service
container is still required; the HTTP MCP server is not:

```bash
"$PY" -m t9_mcp_fundamentals.agent.app --transport stdio

# Local users MCP plus a Podman-launched web-search MCP
"$PY" -m t9_mcp_fundamentals.agent.app --transport stdio --with-web-search

# Just the published DuckDuckGo STDIO image
"$PY" -m t9_mcp_fundamentals.agent.app --transport container \
  --stdio-image docker.io/mcp/duckduckgo:latest
```

Container mode uses `podman run --rm -i`, never `-t`: a pseudo-TTY corrupts the
protocol stream. Pull the image first with `podman pull docker.io/mcp/duckduckgo:latest`
to separate download problems from connection problems. The tested image uses
legacy MCP and logs a discovery warning before the SDK successfully falls back.
`--container-runtime docker` is available only for environments that need Docker.
Local STDIO uses the same Python executable and an inherited environment plus
the solution's `PYTHONPATH`. Server progress messages go to stderr.

Examples: `Find all female users`, `Add a user named Training Example` (supply
the requested email and biography), or `Delete user with id 3` (confirm the ID).
For the combined agent, try a public-profile search and provide missing required
fields before creation. Enter `exit`, `quit` or EOF to stop. `--model` optionally
overrides the deployment name without changing the environment contract.

## Verification

Install test-only dependencies into the same local environment:

```bash
uv pip install --python "$PY" pytest pytest-asyncio ruff
(cd "$T9/solution" && "$PY" -m pytest -q -p no:cacheprovider)
"$PY" -m ruff check "$T9/solution/t9_mcp_fundamentals"

# Requires the User Service; creates and deletes only its own synthetic profile
"$PY" -m t9_mcp_fundamentals.smoke --transport stdio --crud

# Requires both HTTP MCP servers as well
"$PY" -m t9_mcp_fundamentals.smoke --transport http --crud \
  --web-url http://127.0.0.1:8010/mcp

# Verify Podman STDIO discovery, without a DIAL call
"$PY" -m t9_mcp_fundamentals.smoke --transport container
```

The offline suite covers schemas, pagination, multi-block results and errors,
resources and prompts, transport cleanup, Podman launch parameters, CRUD
delegation, streaming fragments, model-agnostic requests, routing collisions and
the tool-round limit. Smoke checks verify real connections and PNG bytes.
Sanitized console evidence is saved in [output/](output/); raw user records and
credentials must never be added there.

## Stop and Reset

Press Ctrl+C in the HTTP server terminal. STDIO processes exit with their client.
Stop only the prerequisite services started for T9:

```bash
podman-compose -p t9-mcp \
  -f "$T9/solution/t9_mcp_fundamentals/docker-compose.yml" stop
```

Use `down` instead of `stop` only to remove those T9 containers and reset their
data. A shared T6/T8 service belongs to its original Compose project.

## Results / Notes

Verified **2026-10-26**, using Python 3.14.3, FastMCP 4.1.4, MCP SDK 2.3.0,
rootless Podman and the unchanged DIAL environment configuration:

| Check | Result |
| --- | --- |
| Standalone offline suite | **15 passed**; no DIAL calls or containers required |
| Ruff | All checks passed |
| HTTP smoke | Five CRUD tools, both prompts, valid PNG, and create/read/search/update/delete passed |
| Local STDIO smoke | Same checks passed; deleted profile returned the expected 404 |
| DuckDuckGo HTTP | `search` and `fetch_content` discovered; search returned a response |
| Podman STDIO image | Both web tools discovered through the SDK's legacy fallback |
| Combined STDIO discovery | Local users tools plus Podman web tools discovered in one CLI session |
| Live DIAL + STDIO | Called `search_user` for a reserved synthetic email; replied `No matching users` |
| Live DIAL + two HTTP servers | Called web `search`; replied `https://www.python.org/` |

Evidence is in [output/](output/). The HTTP MCP server runs from this standalone
copy; prerequisite containers belong to the `t9-mcp` Compose project. An initial
lookup of user ID 1 succeeded, but a later run returned not found because the
mock service changes its data; the saved DIAL check therefore uses an email search.

Intentional adaptations and limits:

- The course refers to a missing server-local `flow.png`. This solution renders
  an endpoint-map PNG in memory with Pillow at the same resource URI. It is not
  a Swagger screenshot; no image is committed.
- HTTP runs in stateless mode; the SDK negotiates modern MCP or legacy fallback.
- The agent has a ten-round tool limit. Tool errors retain the matching call ID.
- Deletion confirmation and privacy are prompt-driven, not enforced access controls.
  Full synthetic service records can reach DIAL. Use only the mock dataset, not
  real personal or payment data. Replies and saved outputs omit payment fields.
- The mock service ignores some filters, especially `gender`; verify actual
  returned matches. The upstream UserUpdate credit-card typing is retained.
- Web-search availability and relevance depend on the upstream service. A
  nonempty smoke response alone is not proof of useful results.
- Container images use upstream `latest` tags and may change independently of
  the pinned Python dependencies.