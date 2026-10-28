## Context

Source: EPAM `ai-applications-development-from-api-to-agents`, Python exercise
`t12_skills`, inspected at revision `2c55dc448f2c80c35962f92a17d5f29d333222b6`.
Development stays in the ignored course fork. Final artifacts are recorded under
`app_development/t12-agent-skills/`, following T10 standalone delivery conventions
and T5's exercise-card/solution separation. The existing topic notes
`app_development/t12_skills.md` are learning material, not the implementation.

The controlling paths are `anthropic_app.py`, `openai_app.py`, and
`custom/custom_app.py` -> `T12Agent` -> `ReadSkillTool` / `PythonCodeInterpreterTool`
-> `T12MCPClient`. The custom MCP client initializes and pings a session; T10's
stateless server is not its transport contract. The diagrams are explanatory,
not replacements for the starter interfaces: the local tool is `read_skill`,
including references, and there is no separate starter `read_resource` tool.

## Goals / Non-Goals

**Goals:** finish every T12 TODO, retain the course's useful abstractions, demonstrate
progressive disclosure and skill/script execution, test failure boundaries, and
deliver a runnable standalone copy with reproducible offline and live checks.

**Non-goals:** a new agent framework, production arbitrary-code sandboxing, a custom
MCP server implementation, RAG changes, account-wide provider maintenance, direct
public OpenAI access, new diagrams, unrelated lesson rewrites, commits, or pushes.

## Decisions

### 1. Complete all three course paths, with capability gates

Selected approach: preserve both managed examples and the local custom agent,
sharing the two managed skill packages. Offline tests cover all three paths even
when a live provider is unavailable. Use injected fake SDK clients to test request
shapes, pagination, uploads, state reuse, failures, and owned-resource cleanup.

Alternatives: custom-only delivery fits DIAL but omits explicit course work;
blindly implementing the starter's API comments risks incompatible SDKs and unsafe
cleanup. Completing all paths with explicit compatibility gates preserves the
course scope without claiming unavailable functionality.

First implementation check: test the current MCP initialization/list/call/result
contract against a local test endpoint, then pin a compatible dependency set.
Inspect installed SDK interfaces and current provider documentation before coding
managed requests. Do not copy model/API assumptions from the topic notes blindly.
API incompatibility is reported, not concealed by a fallback implementation.

### 2. Skill content and progressive disclosure

Complete `_skills/calculator/SKILL.md` using the existing script's actual supported
syntax. Preserve `calculate.py` unless a failing course example demonstrates a
necessary defect. Document exponent syntax, roots, trigonometry, constants,
arithmetic, grouping, and error reporting; test all four calculator prompts.

Complete style-guide instructions, `REFERENCE.md`, and `EXAMPLES.md` with a
consistent plain-language training brand voice. Cover every content type and
minimum example count requested in the starter, including LinkedIn rules and
before/after support-email rewrites. The skill links to the two supporting files
instead of embedding all reference material in its routing metadata.

Complete the custom unit-converter skill against the existing `convert.py`,
`examples.md`, and execution-reference instructions. Make temperature, speed,
area, US-cup volume, and data-size conventions explicit. Numeric acceptance
oracles come from the supplied conversion factors, including its decimal/binary
unit distinctions; never mix TB/MB with TiB/MiB silently.

Startup loads validated names/descriptions and optional metadata into escaped XML,
not full skill bodies or scripts. The agent reads `SKILL.md` only when relevant,
reads references on demand through `read_skill`, and runs scripts through
`execute_code(script_path=..., code=..., session_id=...)`. Script prepending happens
in the application; the model need not read script source to execute it. Supported
metadata is descriptive, not an authorization system.

### 3. Provider configuration, API support, and cost

Use the nearest ancestor root `.env`, preserving exported values. All
OpenAI-compatible calls use exactly `OPENAI_BASE_URL`, `OPENAI_MODEL`, and
`OPENAI_API_KEY`; use DIAL `Api-Key` authentication, retain the configured deployment
and model, reject credential-bearing URLs and public OpenAI hosts, and do not add
model/host aliases or hard-coded reasoning/temperature settings. The existing
`OPENAI_TERRA_MODEL` import is removed from T12, not reproduced in bundled constants.

The custom path uses DIAL Chat Completions. The managed OpenAI path additionally
requires Skills and Responses hosted-shell APIs on the configured DIAL route.
Establish SDK interface availability offline and service support only during
approved verification. Unsupported endpoints produce a clear capability blocker;
never call `api.openai.com` or silently substitute local execution. A blocker leaves
the corresponding live acceptance tasks unchecked and prevents complete archival.

Anthropic uses environment-provided key/model, with an optional configured endpoint
when needed; document only placeholder settings in `.env.example`. No model literal
is a runtime default. Check whether equivalent settings already exist before adding
them. Keep credentials confined to their provider client, never prompts or MCP code.

Use at most ten model/tool rounds per custom query, 90-second model HTTP requests
with at most one retry, and 60-second MCP requests. Bound managed continuation
loops to ten requests per query, expose a finite output-token cap, and report usage.
Before approved managed live execution, agree a finite prompt/token or monetary
budget; run the fixed course samples, not open-ended unattended chats. These are
operational bounds, not a claim that arbitrary interpreter code is safely contained.

### 4. Managed skill lifecycle

Enumerate all pages when discovering custom skills and versions. Reuse an existing
matching title/name without acquiring ownership. Upload only an allowlisted skill
directory, using Anthropic's supported directory helper or an OpenAI ZIP whose
entries retain the top-level skill directory. Reject symlinks escaping that root
and exclude credentials, caches, captures, and unrelated files.

Track IDs and versions created by this invocation. `delete_skills` must be changed
to accept an explicit owned-resource selection, not enumerate-and-delete the
account. Cleanup deletes only owned versions/skills and runs in `finally`; reused
skills are preserved. Failed cleanup is reported without leaking raw provider
responses, and does not replace an earlier primary failure. No bulk-delete mode.

Anthropic requests include the verified beta/code-execution settings and selected
skill, preserve complete assistant content blocks, reuse the container ID, and
follow documented continuation semantics if execution pauses. OpenAI requests
reference the verified hosted-shell environment and chain `previous_response_id`.
Both applications select calculator/style-guide without editing source, support
interactive and single-query runs, and handle exit/quit/EOF and provider failures.

### 5. Confined file access and interpreter result contract

Preserve `ReadSkillTool` and `PythonCodeInterpreterTool` public responsibilities.
`read_skill` requires a string `path`. Accept skill-root-relative paths, including
the documented leading-slash form. Resolve the candidate under the configured root
and reject `..` escape, outside absolute filesystem paths, symlink escape, missing
files, directories, and non-UTF-8 content with a bounded tool error. A small shared
resolver belongs in existing `custom/file_utils.py`; do not duplicate checks.

`execute_code` copies the discovered input schema before adding optional
`script_path`; it must not mutate the MCP model or pass that local-only field to
the server. Resolve/read a script through the same confined helper, prepend it to
the submitted code, and pass the supplied session ID (empty on first execution).
If the script cannot be read, do not submit an error string as executable code.

Validate the structured JSON using `_ExecutionResult`, retaining success, output,
result, error, traceback, file references, and session information. Surface MCP
`isError`, empty/multiple/unsupported content, malformed JSON, and invalid result
schemas as tool errors rather than successful calculations. File references are
metadata only; do not fetch arbitrary URIs automatically. The returned session ID
is reused for later execution; session restart is explicit and bounded, never an
automatic replay of code that may have side effects.

### 6. Agent dispatch and resource lifecycle

Replace recursive completion with a bounded loop. Handle `tools=None`, reject
duplicate names, serialize tool calls, preserve IDs/order, and return correlated
tool messages for unknown tools, invalid JSON, non-object arguments, or execution
failure. Distinguish normal completion from truncation, refusal, and round exhaustion.
Do not block the async loop on synchronous provider I/O; use the SDK async interface
or a scoped worker-thread boundary compatible with the preserved agent API.

Close provider clients and MCP contexts on normal exit, cancellation, connection,
initialization, discovery, or construction failure. Keep the starter's stateful
initialize/ping/list/call behavior if the interpreter implements it; select a
compatible dependency version rather than adopting T10's protocol globally.

### 7. Infrastructure, packaging, and evidence

Use a separate T12 compose project. Bind the interpreter to
`127.0.0.1:8050`; if occupied, choose/document an alternate configurable port,
never stop an unrelated service. Pin the verified interpreter image by immutable
digest at implementation time and record its upstream source/revision where
available. Do not vendor the interpreter repository: it is an external service.
No privileged container, host network, host workspace/secret mounts, or Docker
socket; disable unnecessary outbound access where the verified image permits it.
Record resource limits and the command to stop only this owned compose project.

Use only synthetic calculator/conversion inputs and training copy. Keep transcripts,
model IDs, usage, safe tool traces, session-reuse checks, runtime metadata, and
verification logs in ignored `solution/output/`. Capture actual results, not
authored sample transcripts. Never capture credentials or entire environment maps.

The complete source/destination/exclusion inventory is in
[copy-manifest.md](copy-manifest.md). The final task card links only to durable
delivered files and includes source revision, exact prerequisites, startup/run/test
commands, cost/capability caveats, shutdown, checklist, and factual results.

## Verification and Approval

Follow the ordered checks in [tasks.md](tasks.md). Each code task uses focused
red-green tests before advancing. Offline tests have no provider/external MCP
dependency. Run the entire scoped suite and Ruff lint/format checks in both fork
and standalone copy, then verify import/copy parity without using the fork on
`PYTHONPATH`. Live acceptance covers all fixed course prompts (3 style, 4 calculator,
5 converter) and provider/session reuse; unavailable evidence remains a blocker.

This document, proposal, delta specification, copy manifest, and tasks are the
requested reviewable implementation plan. Native in-session execution is the
default after explicit approval. No implementation or live experiments occur in
this planning change. Material scope/provider/security changes require review.
No commit, push, or acceptance waiver is implied by approval.