# T12 Source and Delivery Manifest

## Provenance and Roots

- External course: <https://github.com/epam/ai-applications-development-from-api-to-agents>.
- Inspected revision: `2c55dc448f2c80c35962f92a17d5f29d333222b6`.
- Development source: course fork, `t12_skills/`; shared source: `commons/`.
- Durable destination: `app_development/t12-agent-skills/solution/`.
- Copy the **verified final fork files**, not untouched starter files over the
  implementation. Recheck source revision/dirty changes at execution time.
- Paths in the tables are relative to the course root and solution root respectively.
  These are inventory paths, not permanent links into the ignored workspace.

## Copy From the Course Fork

| Source -> same destination path | Action and reason |
| --- | --- |
| `t12_skills/README.md` | Preserve original assignment and all sample requests as the source reference |
| `t12_skills/custom_request_flow.html` | Preserve the assignment's linked request-flow resource; inspect embedded/external assets before claiming offline portability |
| `t12_skills/anthropic_app.py` | Complete managed Anthropic upload/chat/cleanup entry point |
| `t12_skills/openai_app.py` | Complete managed OpenAI-compatible upload/chat/cleanup entry point |
| `t12_skills/docker-compose.yml` | Adapt interpreter image pin, loopback binding, isolation, and resource bounds |
| `t12_skills/_skills/calculator/SKILL.md` | Complete calculator instructions and routing metadata |
| `t12_skills/_skills/calculator/scripts/calculate.py` | Required existing executable, even though it has no assignment TODO |
| `t12_skills/_skills/style-guide/SKILL.md` | Complete style skill instructions and routing metadata |
| `t12_skills/_skills/style-guide/REFERENCE.md` | Complete content-type rules referenced by the skill |
| `t12_skills/_skills/style-guide/EXAMPLES.md` | Complete before/after examples referenced by the skill |
| `t12_skills/custom/__init__.py` | Preserve package marker |
| `t12_skills/custom/agent.py` | Complete bounded tool-using agent |
| `t12_skills/custom/custom_app.py` | Complete metadata prompt, configuration, tools, and CLI |
| `t12_skills/custom/models.py` | Required skill metadata loader/validation, with focused robustness fixes only |
| `t12_skills/custom/file_utils.py` | Required file reader; shared confined path resolution |
| `t12_skills/custom/mcp/mcp_client.py` | Required session-based interpreter client and cleanup |
| `t12_skills/custom/mcp/mcp_tool_model.py` | Required discovered-tool schema model |
| `t12_skills/custom/tools/__init__.py` | Preserve package marker |
| `t12_skills/custom/tools/base.py` | Required shared tool/schema/result abstraction |
| `t12_skills/custom/tools/skills/__init__.py` | Preserve package marker |
| `t12_skills/custom/tools/skills/read_skill_tool.py` | Complete local skill-file reader |
| `t12_skills/custom/tools/py_interpreter/__init__.py` | Preserve package marker |
| `t12_skills/custom/tools/py_interpreter/python_code_interpreter_tool.py` | Complete script-prepending MCP execution wrapper |
| `t12_skills/custom/tools/py_interpreter/_response.py` | Required execution/session/file response models |
| `t12_skills/custom/_skills/unit-converter/SKILL.md` | Complete converter instructions and routing metadata |
| `t12_skills/custom/_skills/unit-converter/scripts/convert.py` | Required existing executable and numeric acceptance oracle |
| `t12_skills/custom/_skills/unit-converter/examples.md` | Required unit inventory/examples and unit conventions |
| `t12_skills/custom/_skills/unit-converter/references/how-code-execution-works.md` | Required interpreter/session usage instructions |
| `commons/models/message.py` | Required `Message` model imported by agent and base tool |
| `commons/models/role.py` | Required `Role` enum imported by the message model, agent, app, and tools |

Preserve any existing package markers needed by these shared imports. The starter
uses namespace packages in some directories; do not invent unrelated package files.
These are the transitive shared source dependencies observed in T12. Do **not** copy
`commons/constants.py`: replace its T12 imports with exercise-local environment
configuration, avoiding its model/key defaults and unrelated provider settings.

## Create During Approved Implementation, Then Copy

All paths below are under `t12_skills/` in both the development fork and solution.

| New file | Responsibility |
| --- | --- |
| `config.py` | Ancestor environment loading, DIAL/Anthropic settings, provider validation, finite limits |
| `managed.py` | Shared allowlisted upload files, paginated discovery, owned-resource cleanup, and bounded CLI settings |
| `requirements.txt` | Verified pinned runtime/test dependencies, not the entire course requirements |
| `ruff.toml` | Scoped style settings consistent with delivered exercise code |
| `probe.py` | Fixed sample runs, real safe capture, numeric assertions, usage and session/cleanup evidence |
| `test_skills.py` | Skill metadata/content, progressive disclosure, reference/script inventory, script numeric checks |
| `test_tools.py` | Confined reads, schema isolation, script assembly, execution-result errors/session fields |
| `test_agent.py` | Fake model/tool dispatch, IDs, errors, bounded loop, CLI and provider configuration |
| `test_mcp.py` | Local-socket MCP contract and resource lifecycle/partial-failure tests |
| `test_managed.py` | Fake provider skill upload/discovery/pagination, request shapes, continuation, owned cleanup |

Reuse these owning test files for additional cases; do not create a new test file
per regression. Add any necessary new runtime helper to this manifest when its
concrete need is demonstrated, before the final copy/parity check.

## Create in the Artifact Repository

| Path | Action |
| --- | --- |
| `app_development/t12-agent-skills/README.md` | Task card, source links, checklist, standalone commands, boundaries, and factual results |
| `app_development/t12-agent-skills/.gitignore` | Ignore generated solution output, caches, local data, and virtual environments |
| `app_development/t12-agent-skills/solution/output/` | Ignored real transcripts/probes/runtime/verification only; no fabricated evidence |
| `README.md` | Add T12 progress row with accurate pending/verified state |
| `.env.example` | Reuse existing model-agnostic DIAL variables; add only missing Anthropic placeholders required by T12 |

The original course README remains a source reference; the outer task card is the
authoritative set of adapted DIAL/run commands. Do not alter the topic notes just
to duplicate this task card.

## Explicit Exclusions

Do not copy the whole external repository, its `.git`, root requirements, root
README, unrelated `commons` clients, other exercises, `.env`/`*.env`, credentials,
provider uploads/ZIP caches, downloaded results, screenshots, logs, bytecode,
virtualenvs, or live interpreter state into tracked solution files. Never copy
host secrets into an interpreter container or managed skill upload.

The interpreter at <https://github.com/khshanovskyi/mcp-python-code-interpreter>
is consumed as a verified pinned container image, not vendored source. Record its
image digest and available source attribution in runtime evidence/task-card notes.
No new PNG/PlantUML artifacts are required for this exercise.

## Copy Verification

Run the same T12 tests/lint/format checks in fork and standalone roots. Compare
each allowlisted final source file byte-for-byte, check imports without the fork
on `PYTHONPATH`, verify every local task-card/source-reference link, and confirm
generated output is ignored. Scan staged/tracked candidate files and captures for
secrets without printing matched values. A copy discrepancy or missing support
file fails packaging acceptance; no commit is part of this check.