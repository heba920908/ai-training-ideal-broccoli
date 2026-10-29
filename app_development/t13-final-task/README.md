# T13: Final Task (Users Management Agent)

FastAPI agent using the Tool Use pattern through EPAM DIAL. It connects to the UMS MCP server
over streamable HTTP and to the DuckDuckGo MCP server over STDIO (Podman). It also has a
progressively loaded skill, a Presidio PII guardrail on every tool result, Redis conversation
persistence, and a hardened browser chat UI.

## Source

- Course: <https://github.com/epam/ai-applications-development-from-api-to-agents>,
  exercise `t13_final_task`, revision `2c55dc448f2c80c35962f92a17d5f29d333222b6`
  (no `completed` branch exists for this task).
- Original assignment: [solution/t13_final_task/README.md](solution/t13_final_task/README.md).
  Its flow-diagram PNGs are not committed. View them
  [upstream](https://github.com/epam/ai-applications-development-from-api-to-agents/tree/main/t13_final_task/task/flow-diagrams).
- Final code: [solution/t13_final_task](solution/t13_final_task) (32 files, no fork imports).
  The uv project files are [solution/pyproject.toml](solution/pyproject.toml) and
  `solution/uv.lock`, generated from
  [requirements.txt](solution/t13_final_task/requirements.txt).
- Acceptance specification: [ums-management-agent](../../openspec/specs/ums-management-agent/spec.md).

## Tasks

- [x] 1. `ums-user-management` skill: tool tables match the real UMS and DDG tools; operating rules require confirmation before add-after-enrichment and before delete.
- [x] 2. `McpTool`: delegation, text extraction, errors returned as tool messages.
- [x] 3. `ReadSkillTool`: confined to `_skills/` (no traversal, absolute, or symlink escapes, directories, or non-UTF-8 files).
- [x] 4. `UMSAgent`: non-streaming and streaming loops, bounded to 10 tool rounds; streamed tool-call deltas reassembled by index.
- [x] 5. `ConversationManager`: Redis `conversation:<id>` and `conversations:list`; replayable history after disconnects.
- [x] 6. `app.py`: lifespan with ordered cleanup, the five REST endpoints, `/health`, and the UI at `/`.
- [x] 7. `index.html`: load, select, and delete conversations; streaming; live tool indicator; tool-history dropdown; sanitized Markdown.
- [x] 8. Compose stack and all five sample requests, verified live through DIAL.
- [x] 11. `guardrail.py` (additional task): card number, CVV, expiry, and salary redacted to `***`.

## Setup

Requires `uv` and Podman with `podman compose`. Every command below runs from `solution/`.
From the repository root:

```bash
cd app_development/t13-final-task/solution
uv sync          # creates ./.venv (Python 3.12) from uv.lock
mkdir -p output
```

This is a uv project (`package = false`), so `uv run` always uses `./.venv`. That matters on
this host: the RPM-packaged uv sets `python-preference = "system"` in `/etc/uv/uv.toml`, which
makes `uv run` ignore a `.venv` outside a project. `python -m` puts the current directory on
`sys.path`, so no `PYTHONPATH` is needed. To change the pins, edit
`t13_final_task/requirements.txt` and run `uv add -r t13_final_task/requirements.txt`.

`requirements.txt` pins the full resolved set, including `en_core_web_sm` 3.8.0 for Presidio.
Set `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` in the ignored root `.env` (see
[../../.env.example](../../.env.example)). The app loads the nearest ancestor `.env`, so no copy
is needed. Exported variables take precedence over the file. Authentication uses the `Api-Key` header. Public OpenAI hosts and
credential-bearing URLs are rejected, and no model-specific request parameters are sent.

## Start the Infrastructure

```bash
COMPOSE=t13_final_task/docker-compose.yml
podman compose -f "$COMPOSE" config >/dev/null
podman compose -f "$COMPOSE" up -d userservice ums-mcp-server redis-ums
podman compose -f "$COMPOSE" ps
# Optional Redis Insight on http://127.0.0.1:6380 (add database redis-ums:6379):
podman compose -f "$COMPOSE" --profile insight up -d redis-insight
```

The project is named `ai-training-t13`. Every port is published only on `127.0.0.1`: UMS on
8041, UMS MCP on 8005, Redis on 6379, and Redis Insight on 6380. Images are pinned by digest,
and data lives in named volumes. The UMS MCP server reaches the user service over the project
network. The app launches the DuckDuckGo MCP server itself (`podman run --rm -i`) and stops it
on shutdown.

## Run

```bash
uv run python -m t13_final_task.task.agent.app
```

Open <http://127.0.0.1:8011/>. The app binds to `127.0.0.1:8011` and allows CORS only for
`localhost:8011` and `127.0.0.1:8011`, without credentials.

## Offline Verification

```bash
uv run python -m pytest -q t13_final_task
uv run ruff check t13_final_task
uv run ruff format --check t13_final_task
```

The tests use no network or containers. They cover the following, using a fake provider, fake
MCP clients, an in-memory Redis double, and `TestClient`:

- Configuration rules and confined skill reads
- MCP client launch and close behavior
- The guardrail, with real Presidio and spaCy
- Agent loops, both streaming and non-streaming
- Conversation persistence, the API, CORS, startup and shutdown cleanup
- Static UI checks for SRI, sanitization, and pinning

## Live Acceptance

```bash
uv run python t13_final_task/probe.py --out output/live --app-log output/app.log
# subset: --only search web update delete add guardrail
```

This makes real DIAL calls. For mutations, it creates its own fixture users through the UMS
REST API, substitutes their IDs into the update and delete samples, and deletes every created
user at the end. It writes `acceptance-summary.json` (tool sequences, short answer excerpts,
and pass/fail) to the ignored output directory.

## Shutdown

Stop the app with `Ctrl+C`. This closes both MCP sessions and Redis, and the DuckDuckGo
container exits. Then stop only the T13 project:

```bash
podman compose -f "$COMPOSE" stop
```

## Deviations from the Course

- **Podman instead of Docker.** STDIO uses `podman run --rm -i` with
  `khshanovskyi/ddg-mcp-server` pinned by digest. This image was verified to work over STDIO.
- **Compose.** Added a project name, loopback-only ports, digest pins, and named volumes instead
  of repo bind mounts. `USERS_MANAGEMENT_SERVICE_URL` points to `http://userservice:8000`.
  Redis Insight is behind the `insight` profile. The user-service healthcheck uses Python
  because the image has no `curl`, which kept the upstream check permanently `unhealthy`.
- **DIAL configuration.** The new `task/agent/config.py` uses only `OPENAI_BASE_URL`,
  `OPENAI_MODEL`, and `OPENAI_API_KEY`.
- **API hardening.** The app binds to `127.0.0.1` with loopback-only CORS and serves the UI at
  `/`. Chat requests accept only the `user` role. Error messages sent to clients are generic.
  The default log level is `info`, because DEBUG would log raw tool arguments.
- **UI hardening.** `marked@18.1.2` and `DOMPurify@3.4.17` are pinned with SRI. Every
  `marked.parse` output goes through `DOMPurify.sanitize`. `API_URL` is
  `window.location.origin`.
- **Bounded loop.** Each turn allows at most 10 tool rounds. Tools run sequentially so UMS
  mutations cannot race. The provider timeout is 90 seconds.
- **Guardrail placement.** Redaction runs once, on each tool result, before the result is added
  to history. The model input, SSE `result` events, and Redis therefore all see the same
  redacted text.
- **Confirmation enforcement.** Confirmation before add and delete is enforced by the skill
  instructions and verified live. It is not enforced by an application gate.

## Results / Notes

- **Fork:** 74 offline tests passed; Ruff check and format passed.
- **Fork live, all checks passed (probe run `4133b853`, about 93 s):**

  | Sample | Tool sequence |
  | --- | --- |
  | Surname "Smith" | `read_skill` → `search_user` |
  | Add Elon Musk | Turn 1: `read_skill` → `search_user` → `search` / `fetch_content` ×3, then the proposed profile is shown and no `add_user` is called. Turn 2, after confirmation: `add_user`. |
  | Update email (fixture) | `read_skill` → `get_user_by_id` → `update_user`; the stored email changed |
  | Delete (fixture) | Turn 1: `read_skill` → `get_user_by_id`, then a warning and a wait. Turn 2, after confirmation: `delete_user`; the user is gone. |
  | OpenAI news | `search` → `fetch_content` ×4 → `search` → `fetch_content` ×2, then a summary |
  | Guardrail (fixture with salary and card) | `get_user_by_id`; the SSE `result`, Redis record, final answer, and app log contain no raw value, only `***` |
  | Fixture cleanup | All three created users were deleted |

- **Lifecycle:** `/health` was healthy. Tools registered from both MCP servers. The DDG
  container ran during the session and exited on app shutdown.
- **Browser (`http://127.0.0.1:8011/`):**
  - A live `Calling read_skill...` indicator appeared during streaming.
  - The answer streamed into an assistant bubble. Following the starter's TODO, interim text
    before each tool round gets its own bubble.
  - The dropdown showed `Tool calls (2)` with each call and result.
  - The sidebar showed the new title, truncated at 50 characters with `...`. Selecting a
    conversation and deleting one with confirmation both worked.
  - An injected `<img onerror>`, `<script>`, and `javascript:` link rendered inert: the
    handler was stripped, no script ran, and the `href` was removed.
- **Standalone:** 74 tests passed in a fresh Python 3.12 venv with `PYTHONPATH` unset. Ruff
  passed. A live smoke run of the search and guardrail checks passed.
- **uv workflow (from `solution/`):** `uv sync --locked`, then 74 tests and Ruff passed through
  `uv run` without `PYTHONPATH`, and the root `.env` was found. A live search and guardrail
  smoke run also passed through `uv run`.
- **Packaging:** All 32 files match the fork byte for byte. No PNG or `.env` file is included.
- **First live attempt:** It failed with a DIAL `ConnectTimeout`. The app emitted the generic
  SSE error, and the guardrail and cleanup still held. A rerun after connectivity returned
  passed everything.
- **Known noise:** Presidio logs warnings about non-English recognizers at startup.
