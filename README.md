# AI Training: Course Artifacts

This repo tracks the work I produce for AI training courses, such as the EPAM
*AI Applications Development: From API to Agents* course. Each exercise gets its own folder.
The folder holds the task description, the specs that drove the work, and the finished
solution code.

Work follows **Spec-Driven Development (SDD)**. [OpenSpec](https://github.com/Fission-AI/OpenSpec)
records specs and change proposals. [Superpowers](https://github.com/obra/superpowers) skills
handle brainstorming, planning, TDD, and verification.

## Repository layout

```text
.
├── AGENTS.md               # Rules for AI agents working in this repo (read first)
├── .agents/skills/         # Tool-agnostic agent skills (OpenSpec workflows)
├── openspec/               # OpenSpec config, living specs, active changes
├── app_development/        # Course: AI Applications Development, From API to Agents
│   └── t1-llm-api-dial/    # Exercise T1: work with LLM APIs
│       ├── README.md       # Task card: source, steps, how to run, progress
│       └── solution/       # Final solution code copied from the working fork
├── .githooks/pre-commit    # Blocks commits containing secrets or .env files
├── .env.example            # Template for local environment variables (no real values)
└── workspace/              # Ephemeral, git-ignored (fork clones, archives, scratch)
```

## Getting started

```bash
# 1. Enable the secret-scanning pre-commit hook (once per clone)
git config core.hooksPath .githooks

# 2. Create your local env file and fill in real values (never commit it)
cp .env.example .env

# 3. Clone the course fork into the ephemeral workspace
git clone https://github.com/<your-user>/ai-applications-development-from-api-to-agents.git \
  workspace/ai-applications-development-from-api-to-agents
```

## LLM provider: EPAM DIAL

The courses assume the OpenAI API. Here we call models through the **EPAM DIAL** proxy instead.
DIAL exposes an OpenAI-compatible API, so the course code still uses the `OPENAI_*` variables:

| Variable          | Meaning                                         |
|-------------------|-------------------------------------------------|
| `OPENAI_BASE_URL` | DIAL deployment URL (`https://ai-proxy.lab.epam.com/openai/deployments/<model>`) |
| `OPENAI_MODEL`    | DIAL deployment / model name                    |
| `OPENAI_API_KEY`  | Your DIAL API key (secret)                      |

If an exercise needs another vendor (Anthropic, Gemini, and so on), we adapt it when we get
there. See each exercise README for details.

## Workflow (SDD)

1. **Explore / propose:** `openspec-explore` or `openspec-propose` creates a change under `openspec/changes/<change>/`.
2. **Design / plan:** Superpowers `brainstorming` and then `writing-plans`.
3. **Implement:** `openspec-apply-change` with Superpowers TDD and verification, inside the fork in `workspace/`.
4. **Record:** copy the final code into `<course>/<exercise>/solution/` and update the exercise README.
5. **Archive:** `openspec-archive-change`, then move the archived change into `workspace/` (see `AGENTS.md`).

## Progress

### AI Applications Development: From API to Agents

| #   | Exercise                | Folder                                 | Status      |
|-----|-------------------------|----------------------------------------|-------------|
| T1  | LLM API                 | `app_development/t1-llm-api-dial`      | Completed   |
| T2  | LLM output tuning       | `app_development/t2-llms-output-tuning` | Completed   |
| T3  | Content generation      | `app_development/t3-content-generation` | Completed   |
| T4  | RAG fundamentals        | [app_development/t4-rag-fundamentals](app_development/t4-rag-fundamentals/README.md) | Completed   |
| T5  | RAG advanced            | [app_development/t5-rag-advanced](app_development/t5-rag-advanced/README.md) | Completed   |
| T6  | Grounding               | [app_development/t6-grounding](app_development/t6-grounding/README.md) | Completed   |
| T7  | Guardrails              | [app_development/t7-guardrails](app_development/t7-guardrails/README.md) | Completed   |
| T8  | Agent                   | [app_development/t8-agent](app_development/t8-agent/README.md) | Completed   |
| T9  | MCP fundamentals        | [app_development/t9-mcp-fundamentals](app_development/t9-mcp-fundamentals/README.md) | Completed   |
| T10 | MCP advanced            | [app_development/t10-mcp-advanced](app_development/t10-mcp-advanced/README.md) | Completed   |
| T11 | MCP auth                | [app_development/t11-mcp-auth](app_development/t11-mcp-auth/README.md) | Implemented; OAuth acceptance pending |
| T12 | Skills                  | [app_development/t12-agent-skills](app_development/t12-agent-skills/README.md) | Custom DIAL verified; managed runs deferred |
| T13 | Final task              | n/a                          | Not started |

## Security

Never commit API keys, tokens, or `.env` files. The pre-commit hook enforces this. The
full rules are in [AGENTS.md](AGENTS.md#secrets--hard-rules).
