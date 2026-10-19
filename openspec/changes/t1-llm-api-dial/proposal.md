# Proposal

## Why

Exercise T1 (`t1_llm_api`) in the *AI Applications Development: From API to Agents* course has every
client stubbed with TODOs, and it hard-codes the vendor hosts (`api.openai.com`, `api.anthropic.com`,
`generativelanguage.googleapis.com`) and vendor model names. This repo calls models through
**EPAM DIAL**, so the task can only be completed and tested after the endpoints, models, and keys are
adapted to DIAL. Configuration must come from environment variables, never literals.

## What Changes

- Implement the interactive chat loop (`base_app.start`): sync and streaming modes, conversation history, and `exit` to quit.
- Implement OpenAI-style auth in the base client: validate the key and format it as `Bearer <key>`.
- Implement **OpenAI Chat Completions** clients, both SDK and raw HTTP (`requests` for sync, `aiohttp` + SSE for streaming).
- Implement **OpenAI Responses API** clients, both SDK and raw HTTP (event-based streaming).
- Implement **Anthropic Messages** clients, both SDK and raw HTTP (SSE).
- Implement the **Gemini** clients (SDK and raw HTTP) to the course contract. Live testing depends on
  a Gemini route being available (see design).
- Adapt `commons/constants.py` so OpenAI endpoints, models, and keys are read strictly from `OPENAI_BASE_URL`,
  `OPENAI_MODEL`, and `OPENAI_API_KEY` without hard-coding specific model names or extra `OPENAI_*` / `DIAL_*` variables.
- Copy the final code into `app_development/t1-llm-api-dial/solution/` and record the results in the exercise README.

## Capabilities

### New Capabilities

- `llm-api-clients`: Interactive chat CLI and vendor clients (OpenAI Chat Completions, OpenAI Responses,
  Anthropic, Gemini). Each vendor has an SDK client and a raw-HTTP client with sync and streaming modes,
  all configured from the environment to run against EPAM DIAL.

### Modified Capabilities

None. This is the first spec in the repo.

## Impact

- Code (in the fork under `workspace/`, copied into `solution/`): `t1_llm_api/**`, `commons/constants.py`.
- Dependencies: already pinned in the fork's `requirements.txt` (`openai`, `anthropic`, `google-genai`, `requests`, `aiohttp`).
- External systems: EPAM DIAL proxy (`https://ai-proxy.lab.epam.com`). Calls use real tokens and cost a little.
- Security: keys are read only from the environment. Nothing secret goes into code, the README, or `solution/`.
