# Tasks

## 1. Client & Test Setup (TDD)

- [x] 1.1 Write failing unit tests in `t2_llms_output_tuning/test_t2_output_tuning.py` covering `OpenAIResponsesClient` `base_url` derivation, `OpenAIChatCompletionsClient` kwargs forwarding, and step-by-step runner execution for Chat Completions (TODOs 1–10) and Responses API (TODOs 1–8)
- [x] 1.2 Fix `OpenAIResponsesClient` in `t2_llms_output_tuning/_clients/openai_responses_client.py` to pass `base_url=self._endpoint.removesuffix("/responses")`

## 2. Step-by-Step Output Tuning Runners

- [x] 2.1 Implement `STEPS` (TODOs 1–10) and CLI step runner (`--step`, `--interactive`, `--only-content`, `--no-request`) in `t2_llms_output_tuning/openai_chat_completions_task.py`
- [x] 2.2 Implement `STEPS` (TODOs 1–8) and CLI step runner (`--step`, `--interactive`, `--only-content`, `--no-request`) in `t2_llms_output_tuning/openai_responses_task.py`
- [x] 2.3 Run unit tests and live step-by-step verification via `uv run` against EPAM DIAL (`.env`)

## 3. Solution Artifacts & Documentation

- [x] 3.1 Copy `commons/constants.py` and OpenAI `t2_llms_output_tuning/` files into `app_development/t2-llms-output-tuning/solution/`
- [x] 3.2 Write `app_development/t2-llms-output-tuning/README.md` with step-by-step `uv run` and `pytest` instructions and redacted live output notes
- [x] 3.3 Update root `README.md` progress table for T2 and verify `.githooks/pre-commit` secret scan passes
