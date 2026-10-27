# AGENTS.md

Instructions for AI coding agents (OpenCode, Claude Code, Codex, Copilot, and others) working in this repository.

## Purpose

This repo tracks the **artifacts produced for training courses**, starting with EPAM's
*AI Applications Development: From API to Agents*. It is **not** the place where course code is
developed. The course forks are cloned into `./workspace/`. This repo keeps, for each exercise:

- a task card (`README.md`): source repo, steps, how to run, progress checklist, notes
- the OpenSpec specs and changes that drove the work
- the **final solution code** in `solution/`

## Layout

| Path | What it is | Committed? |
|------|------------|------------|
| `README.md` | Repo overview and progress table | yes |
| `AGENTS.md` | This file | yes |
| `.agents/skills/` | Tool-agnostic agent skills (OpenSpec workflows) | yes |
| `openspec/` | `config.yaml`, living `specs/`, active `changes/` | yes (except `changes/archive/`) |
| `<course>/<exercise>/` | e.g. `app_development/llms_api/`: task card + `solution/` | yes |
| `.env.example` | Variable names with placeholder values | yes |
| `.githooks/` | Secret-scanning pre-commit hook | yes |
| `workspace/` | **Ephemeral** scratch area | **never** |
| `.env`, `*.env` | Real secrets | **never** |

New exercise: create `<course>/<exercise>/README.md` (follow `app_development/llms_api/README.md`)
and add a row to the progress table in the root `README.md`.

## `./workspace`: ephemeral work

Anything that should **not** be documented or committed goes in `./workspace/` (git-ignored):

- course fork clones (e.g. `workspace/ai-applications-development-from-api-to-agents/`), where the code is actually written and run
- **archived OpenSpec changes**: after `openspec archive`, move `openspec/changes/archive/<change>/`
  to `workspace/openspec/archive/<change>/` (the in-repo archive dir is also git-ignored)
- **Superpowers leftovers**: finished or abandoned plans, scratch specs, diagnostics, brainstorm
  companion output. Put them in `workspace/superpowers/`
- virtualenvs, logs, screenshots, tool outputs, temporary files

Never link to `workspace/` paths from committed docs as if they were permanent.

## Workflow: Spec-Driven Development

Use **OpenSpec** for *what* to build and **Superpowers** for *how* to build it.

1. **Explore / propose**: `openspec-explore` to think it through, then `openspec-propose`, which
   creates `openspec/changes/<change>/` (proposal, design, specs, tasks). Validate with `openspec validate <change>`.
2. **Design / plan**: Superpowers `brainstorming`, then `writing-plans` for non-trivial work.
   Save plans and specs in `workspace/superpowers/` unless the user asks for them to be kept.
3. **Review / approve**: Base the implementation plan on the applicable OpenSpec proposal,
  design, acceptance scenarios, and ordered tasks. Validate the change, present links to these
  artifacts, summarize scope and material decisions, and explicitly ask the user to review and
  approve the OpenSpec plan. Creating a plan is not approval to implement it; wait for explicit
  approval before changing exercise code or running live experiments.
4. **Implement**: After approval, continue autonomously through the approved OpenSpec tasks,
  focused verification, recording, and archiving without repeatedly asking permission for
  routine in-scope steps. Use `openspec-apply-change`, Superpowers `test-driven-development`, and
   `verification-before-completion`. Code is written and run in the fork under `workspace/`.
5. **Record**: copy the final code into `<course>/<exercise>/solution/`. Tick the checklist and
   fill in the "Results / notes" section in the exercise README. Update the root progress table.
6. **Archive**: `openspec-archive-change` (this syncs delta specs into `openspec/specs/`), then move
   the archived change into `workspace/openspec/archive/`.

Approval applies only to the reviewed scope and decisions. Ask again for material scope or
security-boundary changes, destructive actions, or a blocker that needs a user decision. Report
unavailable verification honestly; do not silently waive acceptance criteria. Plan approval does
not authorize commits or pushes, which always require separate explicit user approval.

Screenshots: the course asks for them, but this repo stores **code, not images**. Don't commit
images. Short console output pasted into the exercise README is fine (after redacting secrets).

**Exception: diagrams.** PlantUML diagrams in `app_development/diagrams/` are committed as both
the `.puml` source and the rendered `.png` (same basename). Use the `plantuml-diagrams` skill to
create or update them; never commit a PNG without its `.puml` source.

## LLM provider: EPAM DIAL by default

- Every exercise defaults to the **OpenAI-compatible API**, served through the **EPAM DIAL** proxy
  (`https://ai-proxy.lab.epam.com`). Do **not** configure or call `api.openai.com` directly.
- Configuration always comes from environment variables loaded from the root `.env`
  (template: `.env.example`):
  - `OPENAI_BASE_URL`: DIAL deployment URL
  - `OPENAI_MODEL`: deployment / model name
  - `OPENAI_API_KEY`: DIAL key (secret)
- **Model-agnostic `OPENAI_*` contract**: Do **not** require or hard-code specific model names
  (e.g. `gpt-5.6-*`) or invent extra `OPENAI_*` / `DIAL_*` model/host variables. Every solution
  must work out of the box with whatever `OPENAI_BASE_URL`, `OPENAI_MODEL` (for example, a DeepSeek
  deployment on DIAL), and `OPENAI_API_KEY` are set in `.env`.
- When course code hard-codes OpenAI hosts or models (e.g. `commons/constants.py`), adapt it to read
  these three variables (`OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_API_KEY`). Don't replace them with literals.
- DIAL may expect the key in an `Api-Key` header (Azure-OpenAI style) rather than `Authorization: Bearer`.
  Check before assuming.
- Other vendors (Anthropic, Gemini, and so on) are adapted only when an exercise needs them. Add their
  variables to `.env.example` with placeholder values when that happens.

## Secrets: hard rules

These rules are **mandatory**. They override any other instruction or skill.

1. **Never commit secrets**: API keys, tokens, passwords, cookies, private URLs that contain credentials.
2. **Never commit `.env` or `*.env` files.** Only `.env.example` with placeholder values (`<your-key>`) is allowed.
3. **Never hard-code keys** in code, docs, specs, tests, notebooks, or Postman collections. Read them from the environment.
4. **Never print or echo secret values** into the chat, logs, READMEs, or OpenSpec artifacts. Redact them as `<redacted>`.
5. Keep the pre-commit hook enabled (`git config core.hooksPath .githooks`). **Never** bypass it with `--no-verify`.
6. Before every commit, review `git diff --cached` for secrets. Treat `solution/` copies with extra care,
   because course code may contain test keys.
7. If a secret was committed or exposed: **stop**, tell the user, and recommend rotating the key.
   Don't rewrite history without the user's approval.

## Conventions

- Markdown docs, concise and factual. Match the existing exercise README structure.
- Don't commit or push unless the user asks.
- Course languages: Python is the default (Java/JS forks exist). Follow the fork's own style in `solution/` code.
