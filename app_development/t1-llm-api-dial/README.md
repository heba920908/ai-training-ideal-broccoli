# T1: Work with LLM APIs

Make calls to different LLM vendors' APIs and parse their responses, including streaming
(SSE). Do it twice for each vendor: once with the official SDK and once with a raw HTTP client.

## Source

Star ⭐️ and fork ⑃ the course repository for your language:

| Language | Repository | Task folder |
|----------|------------|-------------|
| Python (used here) | <https://github.com/epam/ai-applications-development-from-api-to-agents> | `t1_llm_api` |
| Java | <https://github.com/epam/java-ai-applications-development-from-api-to-agents> | `t1.llm.api` |
| JS | <https://github.com/epam/js-ai-applications-development-from-api-to-agents> | `t1_llm_api` |

Clone the fork into `workspace/` (git-ignored) and set it up by following its root README.
You only need to do this once for the whole course:

```bash
git clone https://github.com/<your-user>/ai-applications-development-from-api-to-agents.git \
  workspace/ai-applications-development-from-api-to-agents
cd workspace/ai-applications-development-from-api-to-agents
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Branches

| Branch | Purpose |
|--------|---------|
| `main` | The main task 🔥 |
| `main-detailed` | Easier version with detailed descriptions and code snippets |
| `completed` | Reference solution. Look here only if you're stuck |

## Provider: EPAM DIAL instead of OpenAI

The task targets `https://api.openai.com` directly (see `commons/constants.py`). We use the
EPAM DIAL proxy instead, configured through the root `.env` (template: [`.env.example`](../../.env.example)):

```bash
set -a; source ../../.env; set +a   # exports OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_API_KEY
```

What to adapt in the working fork:

- Build the endpoints from `OPENAI_BASE_URL`, not `OPENAI_HOST` (for example `f"{OPENAI_BASE_URL}/chat/completions"`).
- Use `OPENAI_MODEL` in place of the hard-coded `gpt-5.6-*` model names.
- If DIAL rejects `Authorization: Bearer`, send the key in an `Api-Key` header instead. DIAL uses the Azure-OpenAI style header.
- Anthropic and Gemini steps (13–20) need their own keys or DIAL deployments. Adapt them when we reach them, or mark them skipped.

Never hard-code the key. Read it from the environment only.

## Tasks

Do the TODO blocks in `t1_llm_api` in this order:

- [x] 1. Import the Postman collection `dial-ai-course.postman_collection.json` and configure its environment variables
- [x] 2. Implement `base_app.py`
- [x] 3. Review `base_client.py`, the abstract base for all clients

**OpenAI Chat Completions**
- [x] 4. `openai/base.py`: validate `api_key` and pass a Bearer-formatted key to `super()`
- [x] 5. `openai/chat/completions/client.py`: SDK client
- [x] 6. Run `openai_chat_completions_app.py` with `openai_client`
- [x] 7. `openai/chat/completions/custom_client.py`: raw HTTP client
- [x] 8. Run `openai_chat_completions_app.py` with `openai_custom_client`

**OpenAI Responses API**
- [x] 9. `openai/responses/client.py`: SDK client
- [x] 10. Run `openai_responses_app.py` with `openai_client` (verified via unit test; deployment-dependent on DIAL)
- [x] 11. `openai/responses/custom_client.py`: raw HTTP client
- [x] 12. Run `openai_responses_app.py` with `openai_custom_client` (verified via unit test; deployment-dependent on DIAL)

**Anthropic** (optional, needs adaptation)
- [x] 13–16. `anthropic/client.py` and `anthropic/custom_client.py`, then test both in `anthropic_app.py` (implemented & unit-tested)

**Gemini** (optional, needs adaptation)
- [x] 17–20. `gemini/client.py` and `gemini/custom_client.py`, then test both in `gemini_app.py` (implemented & unit-tested)

## How to run

From the fork in `workspace/ai-applications-development-from-api-to-agents`:

```bash
set -a; source ../../.env; set +a
PYTHONPATH=. .venv/bin/python -m t1_llm_api.openai.chat.completions.openai_chat_completions_app
```

## Deliverables

- `solution/`: the final `t1_llm_api` code (plus any changed `commons/` files) copied from the fork.
  It must contain no keys or `.env` files.
- Test evidence: the course asks for screenshots. In this repo we keep the code (and paste
  short console output below if useful) rather than images. Screenshots are git-ignored.

## Results / notes

- **Model-agnostic `OPENAI_*` configuration**: `commons/constants.py` reads `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` directly from the environment, without hard-coding specific model names or requiring extra environment variables.
- **SDK `base_url` derivation**: `OpenAIClient` and `OpenAIResponsesClient` derive `base_url` from the configured `endpoint` (`endpoint.removesuffix("/chat/completions")` / `endpoint.removesuffix("/responses")`), so both SDK and raw HTTP clients use the exact same endpoint source of truth.
- **Live run output against EPAM DIAL (`OPENAI_MODEL` from `.env`, key `<redacted>`)**:

```text
Type your question or 'exit' to quit.
> My name is Ana. Reply in 3 words.
AI:
Nice to meet you.

> What is my name? Reply in 3 words.
AI:
Your name is Ana.

> exit
```

Questions? Ask in the course [Discord](https://discord.gg/ukzj9U9tEe).
