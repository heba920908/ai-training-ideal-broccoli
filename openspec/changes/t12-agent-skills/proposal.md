## Why

The course's T12 Agent Skills exercise has unfinished skill instructions, managed
Anthropic/OpenAI examples, local skill-reading and interpreter tools, and a custom
agent. It also needs a standalone delivery, like T5 and T10, with the original
supporting files rather than only the files containing TODOs. Implementing the
starter literally would retain unrestricted file paths, account-wide skill
deletion, model-specific request settings, and an unbounded recursive tool loop.

## What Changes

- Complete calculator, style-guide, and unit-converter skill instructions and
  supporting style examples/reference material.
- Complete both managed-provider examples: skill discovery/upload, conversations,
  container/history reuse, and cleanup restricted to resources created by this run.
- Complete local `read_skill`, the MCP `execute_code` wrapper, the custom agent,
  and its application with progressive disclosure and interpreter-session reuse.
- Use model-agnostic EPAM DIAL configuration for OpenAI-compatible calls; never
  redirect to public OpenAI when a managed API is unsupported. Configure Anthropic
  separately through environment variables only where required by that exercise.
- Add confined skill-file access, bounded calls, lifecycle/error tests, isolated
  interpreter infrastructure, and real redacted acceptance captures.
- Record a runnable task card and standalone solution with the exact source-copy
  inventory in [copy-manifest.md](copy-manifest.md).

## Capabilities

### New Capabilities

- `skill-enabled-agents`: reusable skill packages, provider-managed skill examples,
  a DIAL custom agent using local skill files and a session-based MCP interpreter,
  and independently runnable course artifacts with acceptance evidence.

### Modified Capabilities

None. Existing MCP and RAG specifications are references, not changed contracts.

## Impact

- Development: `t12_skills/` in the ephemeral course fork; only the required shared
  message/role modules are bundled. No T5, T10, or T11 implementation changes.
- Delivery: `app_development/t12-agent-skills/README.md`, `solution/`, exercise
  output ignores, root progress, and placeholder-only provider configuration notes.
- Infrastructure: isolated local MCP Python interpreter on loopback port 8050;
  no host repository, environment file, secrets, or Docker socket mounted into it.
- External dependencies: provider SDK/API compatibility and access must be checked;
  DIAL Chat Completions does not establish support for managed Skills/Responses.
  Managed calls can incur substantial token/container costs and require a reviewed
  bounded run budget. Unsupported live paths remain explicitly incomplete.
- Approval: this is a planning-only change. Implementation, dependency installation,
  container startup, and live provider experiments await explicit plan approval.
  Commits, pushes, account-wide deletion, and provider-boundary changes are not authorized.