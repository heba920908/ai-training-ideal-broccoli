# T12: Agent Skills

Custom skill-enabled agent using EPAM DIAL, local progressive skill loading,
and a sandboxed MCP Python interpreter. Managed Anthropic/OpenAI-compatible
examples are implemented and covered by offline tests; **all managed live runs
are explicitly deferred by the user**. No managed uploads or paid calls were made.

## Source

- Course: <https://github.com/epam/ai-applications-development-from-api-to-agents>,
  exercise `t12_skills`, revision `2c55dc448f2c80c35962f92a17d5f29d333222b6`.
- Original assignment: [solution/t12_skills/README.md](solution/t12_skills/README.md).
- Final code: [solution/t12_skills](solution/t12_skills), with only the required
  shared models in [solution/commons/models](solution/commons/models).
- Copy inventory: [copy-manifest.md](../../openspec/changes/t12-agent-skills/copy-manifest.md).
- Interpreter source: <https://github.com/khshanovskyi/mcp-python-code-interpreter>.
  The inspected image contains FastMCP 4.0.5 and uses stateless HTTP transport;
  kernel state is retained through the explicit `session_id` tool argument.
  The T12 client still initializes, pings, and discovers tools, as tested against
  this image. No assumption from T10's different client contract is required.

## Tasks

- [x] Complete calculator, style guide, and converter skill packages.
- [x] Advertise metadata only; load full skill instructions on demand.
- [x] Confine skill reads and script resolution; preserve execution/session results.
- [x] Implement bounded asynchronous DIAL tool dispatch and interactive/query modes.
- [x] Implement and offline-test both managed examples and owned cleanup.
- [x] Start the pinned local interpreter and verify persistent Python state.
- [x] Run all five converter prompts through the real custom DIAL agent.
- [x] Verify standalone imports, 119 tests, Ruff, source parity, links, and secrets.
- [ ] Run managed Anthropic samples and container-reuse acceptance: deferred.
- [ ] Run managed Skills/Responses samples through DIAL: deferred.
- [ ] Archive the change: withheld while managed live evidence is missing.

## Setup

Requires Python 3.12, `uv`, and Podman Compose or Docker Compose. From the
repository root:

```bash
SOLUTION="$PWD/app_development/t12-agent-skills/solution"
PY="$SOLUTION/.venv/bin/python"
OUT="$SOLUTION/output"
uv venv --python 3.12 "$SOLUTION/.venv"
uv pip install --python "$PY" -r "$SOLUTION/t12_skills/requirements.txt"
mkdir -p "$OUT"
```

Set `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` in the ignored root
`.env`, using [../../.env.example](../../.env.example) as the placeholder reference.
The nearest ancestor `.env` is loaded without overriding exported variables.
The configured HTTPS DIAL host/model are used unchanged with `Api-Key`
authentication. Public OpenAI hosts, credential-bearing URLs, query strings,
and fragments are rejected. No particular model or reasoning setting is required.

The standalone solution requires no imports or runtime files from the course fork.

## Start the Interpreter

```bash
podman compose -p ai-training-t12 \
  -f "$SOLUTION/t12_skills/docker-compose.yml" config
podman compose -p ai-training-t12 \
  -f "$SOLUTION/t12_skills/docker-compose.yml" up -d
podman compose -p ai-training-t12 \
  -f "$SOLUTION/t12_skills/docker-compose.yml" ps
```

Use `docker compose` instead when running Docker. The endpoint is
`http://127.0.0.1:8050/mcp`, an MCP API, not a browser UI.
Do not start a second project on an occupied port or stop unrelated containers.
For an alternate port, export `T12_MCP_PORT=8051` before compose and pass
`--mcp-url http://127.0.0.1:8051/mcp` to the app/probe.

The image is pinned to
`sha256:838e2a0ace5e3167d70389e32c68d850df34e4c1a55fc2102eeb0eedf94e8a42`.
It runs as UID/GID 1000, with read-only root storage, dropped capabilities,
no new privileges, no host mounts or credentials, an internal network,
2 GiB memory, one CPU, and 256 processes. Writable storage is temporary:
256 MiB `/tmp` and 512 MiB `/sandbox`. Stopping/removing it discards sessions.
These are local training safeguards, not a production multi-tenant sandbox.
Never send secrets or real customer data to generated Python code.

## Run the Custom Agent

```bash
cd "$SOLUTION"
"$PY" -m t12_skills.custom.custom_app \
  --mcp-url http://127.0.0.1:8050/mcp \
  --query 'Convert 98.6 degrees Fahrenheit to Celsius and Kelvin'
```

Omit `--query` for interactive chat; `exit`, `quit`, or EOF exits. `--trace`
prints conversation/tool details, never credentials. The app advertises only
skill metadata, reads the matching skill first, and prepends its script locally
without sending the script through the model merely to execute it.
The agent permits ten model/tool rounds per query; provider timeout is 90 seconds
with at most one retry, and MCP requests have a 60-second timeout. Failed or
ambiguous execution is not automatically replayed. Clients close on all exit paths.

## Live Acceptance

```bash
cd "$SOLUTION"
"$PY" -m t12_skills.probe --mcp-url http://127.0.0.1:8050/mcp \
  --output "$OUT/standalone"
```

This makes real custom DIAL calls only. It discovers interpreter tools, executes
two calls using the same Python session, and captures each course conversion
with read/execute trace, model, usage, numeric assertions, and exit status.
Use `--sample 0` for a single-sample smoke check. Reruns overwrite the selected
capture directory; use another directory to retain earlier results.

| Prompt | Expected Script Result |
| --- | --- |
| 98.6 Fahrenheit to Celsius and Kelvin | 37 C; 310.15 K |
| 1.5 TB to MB | 1,572,864 MB using the supplied binary factors |
| 127 km/h to mph and knots | 78.9141414141 mph; 68.5745735416 knots |
| 577 acres to hectares and square meters | 233.503822 ha; 2,335,038.22 m2 |
| 3 US cups to ml | 709.764 ml |

Offline numeric tests use `1e-8` relative/absolute tolerance. Live checks inspect
actual interpreter output with `1e-5` relative/`1e-6` absolute tolerance, accounting
for the supplied six-significant-digit display formatter. Assertions are not based
only on the model's final prose. Sessions expire after 30 minutes of inactivity;
the probe explicitly clears its direct persistence-test session.

## Offline Verification

```bash
cd "$SOLUTION"
"$PY" -m pytest t12_skills -q -o asyncio_default_fixture_loop_scope=function
"$SOLUTION/.venv/bin/ruff" check t12_skills
"$SOLUTION/.venv/bin/ruff" format --check t12_skills
```

The tests cover malformed metadata, confined files, exact script assembly,
stateful local-socket MCP lifecycle/failures, correlated tool dispatch,
decorated async SDK calls, provider configuration, CLI modes, and managed
upload/continuation/ownership with fakes. The inherited scripts received only
mechanical Ruff formatting/import changes; their numeric behavior is unchanged.

## Results / Notes

- Fork: 119 tests passed; Ruff check and formatting passed.
- Fork live: interpreter persistence, metadata-only startup, and all five custom
  DIAL converter samples passed with real read/execute captures.
- Standalone: 119 tests passed in a fresh Python 3.12.13 environment, with
  `PYTHONPATH` unset; Ruff check and all 34 Python files' formatting passed.
- Standalone live: all five custom DIAL samples, read-before-execute traces,
  metadata-only startup, and real Python state reuse passed; exit status 0.
- Packaging: all 40 manifest files match the fork byte for byte, 37 local links
  resolve, output/virtualenv ignores apply, and the secret scan found no matches.
- One upstream MCP/Pydantic `lifespan` forward-reference warning occurs in the
  socket test. It is not suppressed or treated as a failed test.
- Local generated evidence is ignored under `solution/output/`: fork and
  standalone `summary.json`, `sample-0.json` through `sample-4.json`, test/static
  check output, runtime metadata, and packaging checks. No images are recorded.
- The source request-flow HTML is retained as a reference. It requests optional
  Google Fonts over the network; full offline font rendering is not claimed.
- Managed live calls/uploads are deferred, not passed. A future managed run
  needs an explicit finite budget, credentials, and supported APIs. There is
  no public OpenAI fallback or account-wide cleanup. Existing/reused resources
  are preserved. Missing live evidence prevents full acceptance and archival.

## Shutdown

```bash
podman compose -p ai-training-t12 \
  -f "$SOLUTION/t12_skills/docker-compose.yml" down
```

This stops only the named T12 project. The interpreter is intentionally left
running after this implementation so the custom agent can be tried immediately.