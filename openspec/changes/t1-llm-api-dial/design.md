# Design

## Context

The course fork lives at `workspace/ai-applications-development-from-api-to-agents` (`main` branch).
`commons/constants.py` hard-codes vendor hosts and models, and every `t1_llm_api` client raises
`NotImplementedError`. I probed DIAL with the current `.env` (key redacted) and found:

| API | DIAL route | Result |
|-----|------------|--------|
| Chat Completions | `<OPENAI_BASE_URL>/chat/completions` (deployment URL) | 200 with `Authorization: Bearer` and with `Api-Key`; SSE streaming works |
| Responses | `https://ai-proxy.lab.epam.com/openai/v1/responses` | 200 for `gpt-5.6-terra-2026-07-09`; **503 for the DeepSeek deployment** in `.env` |
| Anthropic Messages | `https://ai-proxy.lab.epam.com/anthropic/v1/messages` | 200 for `claude-haiku-4-5@20251001` with the DIAL key |
| Gemini native (`generateContent`) | none found (`/v1beta`, `/google`, `/gemini` → 404) | Gemini only reachable through the OpenAI-compatible deployments route |

## Goals / Non-Goals

**Goals:** complete every TODO in `t1_llm_api` to the course contract. Run Chat Completions, Responses,
and Anthropic live against DIAL with a single DIAL key.

**Non-Goals:** changing the course's class or method structure; adding vendors beyond the four;
automated test suites beyond a small offline check of the pure logic (SSE parsing, key validation).

## Decisions

1. **Config in `commons/constants.py` via `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY`.** Keep the existing
   constant names so the `*_app.py` files work unchanged with any `OPENAI_*` configuration:
   - `OPENAI_HOST = os.getenv("OPENAI_BASE_URL", "https://ai-proxy.lab.epam.com").rstrip("/")`
   - `OPENAI_CHAT_COMPLETIONS_ENDPOINT = f"{OPENAI_HOST}/chat/completions"`
   - `OPENAI_RESPONSES_ENDPOINT = f"{OPENAI_HOST}/responses"`
   - `OPENAI_EMBEDDINGS_ENDPOINT = f"{OPENAI_HOST}/embeddings"`
   - `OPENAI_TERRA_MODEL = os.getenv("OPENAI_MODEL", "")` and `OPENAI_LUNA_MODEL = os.getenv("OPENAI_MODEL", "")`
   - `OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")`
   - Anthropic and Gemini keep their course constants (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`) and are implemented
     to the course contract.
2. **SDK base URLs are derived from the endpoints.** OpenAI SDK `base_url` is the endpoint minus
   `/chat/completions` or `/responses`. Anthropic SDK `base_url` is the endpoint minus `/v1/messages`. This keeps
   one source of truth.
3. **Auth.** OpenAI-style clients use `Authorization: Bearer` (the course spec; DIAL accepts it). Anthropic
   uses `x-api-key` plus `anthropic-version: 2023-06-01`.
4. **Gemini (steps 17–20) is implemented but marked "blocked: no DIAL route".** The code follows the
   course contract and can be run if a personal `GEMINI_API_KEY` is provided. I won't fake it through
   the OpenAI route.
5. **Request params:** set `max_tokens` (Anthropic requires it; default 1024). Don't set temperature,
   because reasoning models reject non-default values.

## Risks / Trade-offs

- [DIAL deployments or model names change] → everything is overridable through env vars; the defaults are documented in `.env.example`.
- [Reasoning models emit non-text stream events, e.g. `thinking` or `reasoning_content`] → parsers only take text deltas and ignore the rest.
- [Costs/tokens] → manual testing only, with short prompts.
- [Key leakage while copying to `solution/`] → only source files are copied. The pre-commit hook scans them.
