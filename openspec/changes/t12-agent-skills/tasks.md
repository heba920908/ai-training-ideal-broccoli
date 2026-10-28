## Execution Rules

This is the implementation breakdown, not implementation authorization. Review
[proposal.md](proposal.md), [design.md](design.md), the
[acceptance specification](specs/skill-enabled-agents/spec.md), and
[copy-manifest.md](copy-manifest.md) together before approving.
Implement natively in-session after approval using the execution and TDD skills.
No commits/pushes, bulk cleanup, public OpenAI fallback, or live budget waiver.
Tasks below are checked only where evidence exists. Implementation/startup was
explicitly approved on 2026-10-28. The user subsequently deferred both managed
live paths completely, retaining the custom EPAM DIAL path as the current focus.
No managed calls/uploads were made. On 2026-10-28 the user subsequently approved
archiving all changes with these managed live checks explicitly waived. This is
administrative closure with known gaps, not evidence that the checks passed.

Each implementation task follows: add the named failing tests, run the focused
check and observe the expected behavioral failure, implement the smallest owning
slice, then rerun the same check. Test dependencies are installed only after
approval. Paths below are relative to the fork/standalone solution root.

## 1. Approval and Compatibility

- [x] 1.1 Obtain explicit approval of the reviewed OpenSpec scope, copy list, provider/cost boundaries, and native execution plan before editing exercise code or running live experiments.
- [x] 1.2 Record the course source revision and existing local modifications; inspect current SDK interfaces/provider docs for managed Skills/Responses/beta execution. Add `test_mcp.py` local-socket initialization/ping/list/call/result tests, prove the interpreter contract, and pin the compatible Python/runtime/test dependencies in `t12_skills/requirements.txt`. Do not inherit T10 pins or stateless behavior by assumption.
- [x] 1.3 Add `test_agent.py` configuration tests for ancestor dotenv loading, exported-value precedence, configured model/Api-Key, rejected public/credential-bearing hosts, missing credentials, and no fixed reasoning parameters. Implement `config.py`, remove T12 `commons.constants` imports, and document only required placeholder additions to `.env.example`. Run `python -m pytest t12_skills/test_agent.py -q`.

## 2. Complete Skill Packages

- [x] 2.1 In `test_skills.py`, validate all three skill frontmatters, name/folder correspondence, nonempty routing descriptions, linked-file presence, and metadata-only startup XML. Add malformed/nonmapping YAML and invalid-name fixtures that fail safely. Complete calculator and converter `SKILL.md`; fix only demonstrated loader defects in `custom/models.py`. Run `python -m pytest t12_skills/test_skills.py -q`.
- [x] 2.2 Complete style-guide `SKILL.md`, `REFERENCE.md`, and `EXAMPLES.md`, covering every starter content section, at least four subject-line rewrites, four heading rewrites, eight jargon replacements, and the required body/social/support examples. Add inventory/section/minimum-count checks to `test_skills.py`, then manually review consistency against the three course style prompts and rerun the same test file.
- [x] 2.3 Add subprocess/script numeric tests for all four calculator prompts (1024, 192, 2, 1036) and all five converter prompts. Derive converter expected values/tolerances from its documented factors, asserting 98.6 F -> 37 C / 310.15 K and explicit data/cup conventions. Preserve provided scripts unless a focused failing sample requires a fix. Run `python -m pytest t12_skills/test_skills.py -q`.

## 3. Local Skill and Interpreter Tools

- [x] 3.1 Add `test_tools.py` cases for valid relative/leading-slash skill paths, traversal, outside paths, symlink escape, missing files, directories, and non-UTF-8 files. Implement the confined resolver in `custom/file_utils.py` and all `ReadSkillTool` TODOs with the required string-path schema. Run `python -m pytest t12_skills/test_tools.py -q` before moving to execution behavior.
- [x] 3.2 Extend `test_tools.py` with missing tool discovery, independent schema copies, optional `script_path`, exact script-plus-code assembly, no script_path forwarded, no call on failed read, first/reused session IDs, and preserved response fields. Complete `PythonCodeInterpreterTool` TODOs using `_ExecutionResult`. Run `python -m pytest t12_skills/test_tools.py -q`.
- [x] 3.3 Add `test_mcp.py` cases for `isError`, empty/multiple/nontext content, invalid result JSON/schema, setup/ping/list failure, cancellation, and reverse-order closure. Make narrow fixes in `custom/mcp/mcp_client.py` and the interpreter factory; never replay ambiguous code automatically. Run `python -m pytest t12_skills/test_mcp.py t12_skills/test_tools.py -q`.

## 4. Custom Agent and Application

- [x] 4.1 Extend `test_agent.py` with fake-provider completion/tool turns, serialization/IDs/order, tools=None, duplicate names, unknown tools, invalid/nonobject JSON, tool exceptions, normal completion versus truncation/refusal, and ten-round exhaustion. Complete `T12Agent` with nonblocking provider I/O and a bounded loop, preserving the public course abstractions. Run `python -m pytest t12_skills/test_agent.py -q`.
- [x] 4.2 Test then complete `custom/custom_app.py`: metadata XML escaping, system/user/tool/assistant history, on-demand read-before-execute trace, single-query and interactive modes, exit/quit/EOF, configurable MCP address, and guaranteed client/tool closure on failure. Keep the exact `read_skill` and `execute_code` contracts, not a new read_resource abstraction. Run `python -m pytest t12_skills/test_agent.py t12_skills/test_mcp.py -q`.

## 5. Managed Provider Examples

- [x] 5.1 Add Anthropic fake-client cases in `test_managed.py` for paginated matching/custom discovery, allowlisted upload, selected skill/beta/code-execution payload, complete assistant blocks, container reuse, bounded continuation, and missing configuration/API support. Complete `anthropic_app.py` TODOs with injectable client configuration and source-free skill selection. Run `python -m pytest t12_skills/test_managed.py -q -k anthropic`.
- [x] 5.2 Add OpenAI-compatible fake-client cases for deterministic top-level ZIP entries, excluded/escaping files, paginated lookup, upload, hosted-shell/skill environment, previous-response chaining, finite continuation, and unsupported Skills/Responses diagnostics without public fallback. Complete `openai_app.py` TODOs using the verified SDK interface. Run `python -m pytest t12_skills/test_managed.py -q -k openai`.
- [x] 5.3 Add both-provider ownership/failure regressions: preserve reused/unrelated skills, delete only created versions/skills, cleanup on query failure/cancellation, report cleanup errors without masking primary errors. Replace account-wide `delete_skills` behavior with explicit owned IDs. Add fake CLI single-query/exit/EOF and token-bound tests. Run `python -m pytest t12_skills/test_managed.py -q`.

## 6. Infrastructure and Live Acceptance

- [x] 6.1 Verify the upstream interpreter image/source contract and pin a working immutable digest in `docker-compose.yml`. Isolate the T12 project, loopback binding, resource limits, no host/secret mounts, and owned shutdown command. Check occupied ports without stopping unrelated services. Validate compose configuration before starting the approved local interpreter; record safe runtime metadata.
- [x] 6.2 Test then add `probe.py` fixed-query captures and numeric assertions using existing owning test files. Run real interpreter discovery and two executions reusing returned session state; run the custom DIAL agent on all five converter samples. Capture actual read/execute traces, numeric outputs, safe model/session metadata, and exit statuses in ignored output. Verify the initial prompt did not preload full skill bodies/scripts.
- Waived 6.3: all Anthropic managed live samples, container reuse, usage, and cleanup evidence remain unrun. The user explicitly waived them for archival on 2026-10-28. No managed paid calls/uploads were made; future runs still need a finite approved budget.
- Waived 6.4: all DIAL managed Skills/Responses live samples, response chaining, usage, and cleanup evidence remain unrun. The user explicitly waived them for archival on 2026-10-28. Configured-route support is unverified; no public fallback is authorized.

## 7. Standalone Recording and Verification

- [x] 7.1 Run the complete fork suite (`python -m pytest t12_skills -q`) and scoped checks (`ruff check t12_skills`, `ruff format --check t12_skills`) using the pinned environment. Record actual output; review error paths, file confinement, ownership, budgets, and missing live evidence before copying.
- [x] 7.2 Copy the final allowlisted T12 and shared message/role files exactly as specified in `copy-manifest.md` into `app_development/t12-agent-skills/solution/`. Include source README/flow HTML, scripts/references, dependencies, tests, and package markers; exclude constants, secrets, caches, screenshots, and unrelated repository files. Verify per-file byte parity and source-reference link portability.
- [x] 7.3 Create the outer exercise README and ignores, with durable source links, source revision, exact pinned setup/compose/run/test/shutdown commands, fixed samples, budget/capability/security caveats, generated-output list, checklist, and factual results. Update the root progress row and missing placeholder-only environment settings; never link to the ephemeral fork as a runtime dependency.
- [x] 7.4 Run the entire test/lint/format suite from the standalone root without fork imports; perform its real interpreter/custom-agent smoke run and available approved managed checks. Verify copied-file parity, task-card links, ignored output, and a secret scan without printing secret matches. Record fork/standalone evidence separately and retain blocked tasks as unchecked.
- [ ] 7.5 Reconcile every acceptance scenario with actual evidence, run `openspec validate t12-agent-skills --strict`, and report any blockers. Only when all required acceptance evidence passes, archive/sync the change and move its archive to the ignored `workspace/openspec/archive/` location. No commit or push without separate explicit approval.

## Verification Evidence

- Fork and standalone: **119 tests passed** in Python 3.12.13 with pinned
	dependencies; Ruff check passed and all 34 Python files passed format check.
	One upstream MCP/Pydantic lifespan forward-reference warning remains visible.
- Real interpreter: initialization, ping, discovery, execution/result parsing,
	and two calls accessing the same explicit Python session passed.
- Real custom DIAL agent: all five converter samples passed independently in
	both fork and standalone, with metadata-only startup and read-before-execute
	traces. Actual usage/model/session data and exit status 0 are in ignored output.
- Packaging: 40 allowlisted files match byte for byte; 37 local links resolve;
	output and virtualenv ignores are verified; secret scan passed without values.
- Durable results and exact commands: [exercise task card](../../../app_development/t12-agent-skills/README.md).
- Acceptance scenarios for skills, confinement, MCP, custom dispatch, provider
	boundaries, and standalone delivery have offline and custom-live evidence.
	Managed lifecycle scenarios have fake-client evidence only; real managed
	execution/access/cost scenarios remain deferred under 6.3 and 6.4.
- Strict OpenSpec validation passed. On 2026-10-28 the user approved archival
	with the remaining live checks explicitly waived, not reported as passing.
	See `openspec/closure-2026-10-28.md` for the durable decision record. This
	closure operation does not authorize another commit, push, or unrelated cleanup.