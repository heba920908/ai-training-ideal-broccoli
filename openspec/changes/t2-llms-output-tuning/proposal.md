# Proposal

## Why

Exercise T2 (`t2_llms_output_tuning`) in *AI Applications Development: From API to Agents* explores how generation parameters (`n`, `temperature`, `top_p`, `max_tokens` / `max_completion_tokens` / `max_output_tokens`, `stop`, structured JSON schemas, `frequency_penalty`, `presence_penalty`, `seed`, `reasoning_effort` / `reasoning`, `instructions`, `store` + `previous_response_id`, `truncation`, `metadata`) affect OpenAI Chat Completions and OpenAI Responses API calls. In the course template, TODOs are only comments above an interactive `input()` loop, and `OpenAIResponsesClient` does not configure `base_url` from `OPENAI_RESPONSES_ENDPOINT`, so it fails to route to EPAM DIAL cleanly. We also need a deterministic step-by-step runner (`uv run`) and pytest suite to observe each tuning parameter's live request/response behavior against EPAM DIAL using the model-agnostic `OPENAI_*` environment contract.

## What Changes

- Update `t2_llms_output_tuning/_clients/openai_responses_client.py` to derive `base_url` from `self._endpoint.removesuffix("/responses")` so the OpenAI SDK routes through `OPENAI_BASE_URL` on EPAM DIAL.
- Implement structured step-by-step experiment definitions and CLI runners in `openai_chat_completions_task.py` (TODOs 1–10) and `openai_responses_task.py` (TODOs 1–8), supporting `--step <N>`, `--step all`, and interactive mode via `uv run`.
- Add unit and live step-by-step tests (`test_t2_output_tuning.py`) runnable via `uv run pytest -s`.
- Skip optional Anthropic and Gemini tasks per user scope.
- Copy the final OpenAI solution artifacts into `app_development/t2-llms-output-tuning/solution/`, write `app_development/t2-llms-output-tuning/README.md` with step-by-step `uv run` instructions and redacted live output, and update the root `README.md` progress table.

## Capabilities

### New Capabilities

- `llm-output-tuning`: Step-by-step and interactive execution of OpenAI Chat Completions (TODOs 1–10) and OpenAI Responses API (TODOs 1–8) output-tuning experiments against EPAM DIAL using `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY`.

### Modified Capabilities

None.

## Impact

- Code (in the fork under `workspace/`, copied into `app_development/t2-llms-output-tuning/solution/`): `t2_llms_output_tuning/**`, `commons/constants.py`.
- External systems: EPAM DIAL proxy (`OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_API_KEY` from `.env`).
- Security: no secrets in code, tests, docs, or `solution/`; headers and console outputs redact API keys.
