# Design

## Context

`workspace/ai-applications-development-from-api-to-agents/t2_llms_output_tuning` provides:
- `_clients/_base_client.py`: `AIClient` with request printing and header masking (`_safe_headers`).
- `_clients/openai_chat_completions_client.py`: raw HTTP (`requests.post`) client posting to `OPENAI_CHAT_COMPLETIONS_ENDPOINT` with `**kwargs` merged into the JSON body.
- `_clients/openai_responses_client.py`: OpenAI SDK client calling `self._client.responses.create(...)` with `**kwargs`.
- `openai_chat_completions_task.py` (TODOs 1–10) and `openai_responses_task.py` (TODOs 1–8): comment-only TODO blocks followed by `run(...)`.

## Goals / Non-Goals

**Goals:**
- Route both OpenAI Chat Completions and OpenAI Responses clients through the configured `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` environment variables.
- Make every OpenAI output-tuning TODO (Chat Completions 1–10, Responses API 1–8) runnable step-by-step from the command line (`uv run`) and via `pytest -s` so the user can inspect request bodies and live responses for each parameter without manually editing kwargs between runs.
- Preserve default interactive `run(...)` behavior when invoked with `--interactive`.

**Non-Goals:**
- Anthropic (`anthropic_task.py`) and Gemini (`gemini_task.py`) exercises (explicitly skipped).
- Hard-coding model names or extra environment variables beyond `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY`.

## Decisions

1. **SDK `base_url` in `OpenAIResponsesClient`**: Initialize `OpenAI(api_key=api_key, base_url=self._endpoint.removesuffix("/responses"))` so `OpenAIResponsesClient` uses the exact endpoint configured in `commons/constants.py`.
2. **Declarative TODO step catalog + `run_step` / `run_steps` helper**:
   - Define `STEPS` in `openai_chat_completions_task.py` (steps 1–10) and `openai_responses_task.py` (steps 1–8), where each step records its step number, title, prompt(s), and list of parameter-tuning runs (`label` + `kwargs`).
   - Support CLI flags `--step all`, `--step <1..N>`, `--only-content`, `--no-request`, and `--interactive`.
   - In step-by-step mode, catch and display HTTP/API errors per call so model-specific unsupported parameters (or deployments that do not expose `/responses`) report the exact proxy response without aborting the remaining steps.
3. **Multi-turn `store` + `previous_response_id` step in Responses API (TODO 8)**:
   - Include a step demonstrating `instructions` and `store=True` + `previous_response_id` chaining (converting the first response's `id` or falling back gracefully if the endpoint does not support stateful storage).
4. **Testing with `uv run`**:
   - Provide `test_t2_output_tuning.py` with fast offline unit tests (verifying `OpenAIChatCompletionsClient`, `OpenAIResponsesClient`, and every TODO step's request payload) plus opt-in/live tests (`-k live`) to see live EPAM DIAL output step-by-step.
