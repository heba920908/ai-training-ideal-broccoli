# Tasks

## 1. Setup

- [x] 1.1 Create `.venv` in the fork and `pip install -r requirements.txt`; verify that `python -c "import openai, anthropic, google.genai, aiohttp"` succeeds
- [x] 1.2 Adapt `commons/constants.py` to read `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` (design decision 1); verify that, with `.env` loaded, printing the endpoints and models shows the configured `OPENAI_*` values and that no key is in the source
- [x] 1.3 Verify `.env.example` contains only the standard `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` placeholders (plus optional commented vendor keys) and that the pre-commit hook passes on it

## 2. Core: chat loop and base auth (steps 2–4)

- [x] 2.1 Implement `base_app.start` (history, sync/stream, `exit`, skip empty); verify with a fake client in an offline check script
- [x] 2.2 Implement `openai/base.py` (validate key, `Bearer` format); verify that an empty key raises `ValueError` and that `_api_key == "Bearer k"`

## 3. OpenAI Chat Completions (steps 5–8)

- [x] 3.1 Implement the SDK client `openai/chat/completions/client.py`; verify that a live sync and stream run through `openai_chat_completions_app.py` returns a reply and remembers context
- [x] 3.2 Implement the raw client `custom_client.py` (`requests` + `aiohttp` SSE); verify a live sync and stream run with `openai_custom_client`

## 4. OpenAI Responses API (steps 9–12)

- [x] 4.1 Implement the SDK client `openai/responses/client.py`; verify with unit tests (and check against configured `OPENAI_*` endpoint)
- [x] 4.2 Implement the raw client `openai/responses/custom_client.py` (event SSE); verify with unit tests (including SSE event parsing)

## 5. Anthropic (steps 13–16)

- [x] 5.1 Implement the SDK client `anthropic/client.py` to the course contract; verify with unit tests
- [x] 5.2 Implement the raw client `anthropic/custom_client.py` (SSE `content_block_delta`); verify with unit tests

## 6. Gemini (steps 17–20)

- [x] 6.1 Implement the SDK client `gemini/client.py` and the raw client `gemini/custom_client.py` to the course contract; verify that they import and that the offline SSE-parse check passes

## 7. Record and verify

- [x] 7.1 Copy `t1_llm_api/` and `commons/constants.py` into `app_development/t1-llm-api-dial/solution/` (source only, no `.venv` or `__pycache__`); verify that `git add` plus `.githooks/pre-commit` exits 0
- [x] 7.2 Update `app_development/t1-llm-api-dial/README.md` (tick the checklist, add run instructions, paste short redacted console output in Results) and the root progress table; verify that the docs render and contain no secrets
