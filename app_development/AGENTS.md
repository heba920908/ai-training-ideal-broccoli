# Application Development Agent Instructions

Inherit all instructions in the repository root `AGENTS.md`, including the secret-handling,
EPAM DIAL, ephemeral workspace, standalone solution, and no-commit/no-push rules.

## OpenSpec Planning and Approval

1. Read the exercise task and the nearest completed exercise as a reference. Use the relevant
   living OpenSpec specifications and open changes to identify existing contracts and dependencies.
2. Create or update the exercise's OpenSpec proposal, design, delta specifications, and ordered
   tasks before implementation. Base the implementation plan on those artifacts, with explicit
   acceptance scenarios, focused tests, live verification, packaging, and documentation steps.
3. Validate the OpenSpec change. Present artifact links, summarize scope and material decisions,
   and explicitly ask the user to review and approve the OpenSpec plan. Wait for explicit approval;
   a request to create a plan does not authorize implementation or live experiments.
4. After approval, continue autonomously through the approved tasks, verification, final solution
   copy, task-card/progress updates, and OpenSpec archiving. Do not repeatedly request permission
   for routine in-scope steps. Mark tasks complete only when their checks support completion.
5. Ask again only for material scope or security-boundary changes, destructive actions, or blockers
   requiring a user decision. Do not silently waive failed or unavailable verification. Approval of
   the plan never authorizes commits or pushes; obtain separate explicit approval for those.

## Exercise Delivery

- Develop and run course code in the fork under `workspace/`, not in the tracked solution copy.
- Follow `t10-mcp-advanced/README.md` for current task-card, standalone packaging, offline tests,
  scoped lint/format checks, and redacted local evidence conventions where applicable.
- Preserve each exercise's own protocol and tool contracts rather than copying a reference blindly.
- Keep scratch plans in `workspace/superpowers/` and generated evidence ignored. Never link to
  ephemeral workspace material as a permanent dependency in committed documentation.
- Archive only after acceptance evidence is complete, then move the archive into
  `workspace/openspec/archive/` as specified by the root instructions.