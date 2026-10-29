## Execution Rules

This is the implementation plan (Superpowers `writing-plans` output) and is not
implementation authorization. Review [proposal.md](proposal.md),
[design.md](design.md), and the
[acceptance specification](specs/ums-management-agent/spec.md) together before
approving. After approval, execute natively in-session with
`test-driven-development` and `verification-before-completion`: for each task,
add the named failing tests, run them and see the expected failure, implement
the smallest slice, rerun. Paths are relative to the fork's `t13_final_task/`
unless stated. No commits, pushes, public OpenAI fallback, or containers
outside project `ai-training-t13`.

## 1. Approval and Compatibility

- [x] 1.1 Obtain explicit approval of this OpenSpec change (scope, Podman switch, UI hardening, guardrail, live fixture policy).
- [x] 1.2 Create `workspace/.venv-t13` (Python 3.12); install course pins plus `uvicorn`, `pytest`, `pytest-asyncio`, `ruff`, and the matching `en_core_web_sm`. Inspect the installed `mcp` streamable HTTP client signature, tool schema field name, and OpenAI create awaitability; write `requirements.txt` and `ruff.toml`.
- [x] 1.3 Probe `podman run --rm -i khshanovskyi/ddg-mcp-server` for STDIO initialize/list; if unsupported, verify `docker.io/mcp/duckduckgo` instead. Record the chosen image digest and real tool names/schemas.
- [x] 1.4 Rewrite `docker-compose.yml` per design §7 (project name, loopback ports, digests, internal service URL, named volumes, optional Redis Insight profile). Run `podman compose config`; start only `userservice`, `ums-mcp-server`, `redis-ums`; verify health, list UMS MCP tools, and capture one synthetic-shaped `get_user_by_id` output format (no real values) for guardrail fixtures.

## 2. Configuration and Skill

- [x] 2.1 `test_config.py`: ancestor `.env` loading, exported precedence, Api-Key header, missing variables, credential URL and public-host rejection, no model-specific params. Implement `task/agent/config.py`. Run `pytest test_config.py -q`.
- [x] 2.2 `test_skill.py`: frontmatter validity via `load_skills`, name = directory, description covers CRUD/search/web enrichment, every documented tool name is in the discovered set from 1.3/1.4, operating rules include confirmation for add and delete. Complete `_skills/ums-user-management/SKILL.md` (DDG row documents STDIO via Podman, not the starter's HTTP URL). Run the test.

## 3. Tools and MCP Clients

- [x] 3.1 `test_tools.py`: `ReadSkillTool` valid relative/leading-slash path, traversal, absolute outside path, symlink escape, directory, missing file, non-UTF-8; `McpTool` delegation, string/non-text result handling, exception -> tool error with call ID. Implement both TODOs with a confined resolver. Run the test.
- [x] 3.2 Extend `test_tools.py` for `StdioMcpClient` launch arguments (`podman run --rm -i <image>`, no `-t`) and `call_tool`/close behavior, plus `HttpMcpClient` close. Add the missing STDIO `call_tool` if absent and `close()` on both clients releasing contexts in reverse order. Run the test.

## 4. Guardrail

- [x] 4.1 `test_guardrail.py`: YAML/JSON/Python-dict card num, CVV, expiry, salary redacted to `***`; standalone 16-digit card; plain-text `Annual salary: $85,000`; `salary: None` untouched; name/email untouched; Luhn-invalid numbers still redacted. Implement `_build_analyzer` and `redact`. Run the test.

## 5. Agent Loop

- [x] 5.1 `test_agent.py` non-streaming: final answer without tools; tool round then answer with ordered history; unknown tool; invalid/non-object JSON; tool exception; tool result redacted before it reaches the next provider request; round limit stops without another call; configured model and no extra params in the request. Implement `__init__`, `response`, `_call_tools`. Run the test.
- [x] 5.2 Extend `test_agent.py` streaming: content deltas forwarded; fragmented tool-call id/name/arguments reassembled by index; `call` and redacted `result` events emitted in order; recursive continuation; final stop chunk and `[DONE]`; provider error -> safe `error` event. Implement `stream_response` and `_collect_tool_calls`. Run the test.

## 6. Conversations and API

- [x] 6.1 `test_conversation_manager.py` with an in-memory async Redis double: create/list newest-first/get/delete, unknown IDs, system prompt injected only on first turn, non-streaming save, streaming save after completion, disconnect trims to a consistent history. Implement all TODOs. Run the test.
- [x] 6.2 `test_app.py` with `TestClient` and injected fakes: skills XML (escaping, optional fields, metadata children, allowed-tools), system prompt instructions, all five endpoints + 404s, non-user role rejected, streaming content type, `GET /` serves the UI, loopback-only CORS, startup failure closes opened resources, shutdown closes MCP clients and Redis. Implement `app.py` TODOs with host `127.0.0.1`. Run the test.

## 7. UI

- [x] 7.1 `test_ui.py` static checks: exact-version `marked` and `DOMPurify` with `integrity`/`crossorigin`, every `marked.parse` wrapped by `DOMPurify.sanitize`, `API_URL` from `window.location.origin`. Implement the four `index.html` TODO blocks (load, select, delete, stream with tool indicators/dropdown). Run the test.

## 8. Live Acceptance

- [x] 8.1 Full offline suite and `ruff check` / `ruff format --check` on `t13_final_task`; record results.
- [x] 8.2 Start the app on 127.0.0.1:8011; confirm `/health`, tool registration from both servers, and the DDG STDIO container lifecycle. Write `probe.py` (REST, streaming + non-streaming, ignored output).
- [x] 8.3 Run the five samples through DIAL: surname "Smith" search; add Elon Musk (profile shown before `add_user`, then confirm); update email and delete-with-confirmation on owned fixture IDs; web news summary. Assert tool sequences and that `read_skill` loaded the skill. Delete all fixture/created users afterwards.
- [x] 8.4 Guardrail live: fetch a fixture user with salary and card data; verify `***` in the SSE `result`, the provider-visible history, and the Redis record; verify no raw values in app logs.
- [x] 8.5 Browser check at `http://127.0.0.1:8011/`: live tool indicator, streamed bubble, tool-history dropdown, sidebar list/select/delete, and an injected-HTML message rendered inert.

## 9. Delivery and Archive

- [x] 9.1 Copy per design §10 to `app_development/t13-final-task/solution/`; add `.gitignore` for `output/`, venv, caches; verify byte parity and that no PNG/`.env` is included.
- [x] 9.2 Write `app_development/t13-final-task/README.md` (source + revision, tasks checklist, setup/compose/run/test/shutdown commands, deviations from the course, results/notes with redacted evidence) and update the root progress row.
- [x] 9.3 From the standalone root: offline suite, Ruff, one live smoke chat, link check, and a secret scan that reports matches without printing values.
- [x] 9.4 Stop (not remove) project `ai-training-t13` containers; reconcile every spec scenario with evidence; `openspec validate t13-final-task --strict`; archive, replace the generated Purpose text in the living spec, and move the archive to `workspace/openspec/archive/`. No commit or push.
