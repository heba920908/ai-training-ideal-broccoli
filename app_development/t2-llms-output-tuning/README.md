# T2: LLMs Output Tuning

Experiment with LLM output-tuning parameters across OpenAI Chat Completions and OpenAI Responses APIs
to observe how sampling (`temperature`, `top_p`), token budgets (`max_tokens`, `max_output_tokens`),
repetition penalties (`frequency_penalty`, `presence_penalty`), stop sequences (`stop`), structured
JSON outputs (`response_format`, `text.format`), determinism (`seed`), multi-choice completions (`n`),
and extended reasoning (`reasoning_effort`, `reasoning`) affect model responses.

> **Scope note:** Focused on the OpenAI exercises (Chat Completions and Responses API) via the
> OpenAI-compatible EPAM DIAL proxy. Optional Anthropic and Gemini tasks are skipped.

## Source

Star ⭐️ and fork ⑃ the course repository for your language:

| Language | Repository | Task folder |
|----------|------------|-------------|
| Python (used here) | <https://github.com/epam/ai-applications-development-from-api-to-agents> | `t2_llms_output_tuning` |
| Java | <https://github.com/epam/java-ai-applications-development-from-api-to-agents> | `t2.llms.output.tuning` |
| JS | <https://github.com/epam/js-ai-applications-development-from-api-to-agents> | `t2_llms_output_tuning` |

## Provider: EPAM DIAL instead of OpenAI

All calls go through the **EPAM DIAL** proxy configured in the root `.env`
(template: [`.env.example`](../../.env.example)):

```bash
set -a; source .env; set +a   # exports OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_API_KEY
```

What was adapted:
- `commons/constants.py` reads `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` from the environment (model-agnostic).
- `_clients/openai_responses_client.py` passes `base_url=self._endpoint.removesuffix("/responses")` to the `OpenAI` SDK client so requests route to the configured DIAL endpoint instead of `api.openai.com`.
- `_clients/_base_client.py` masks the `Authorization` header as `Bearer <redacted>` when printing requests so no characters of `OPENAI_API_KEY` are ever echoed to the console.
- `openai_chat_completions_task.py` and `openai_responses_task.py` include a declarative `STEPS` catalog and CLI runner (`--step all`, `--step <N>`, `--only-content`, `--no-request`, `--interactive`) so every TODO can be executed step-by-step via `uv run` or `pytest`.

## Tasks

**1. OpenAI Chat Completions (`openai_chat_completions_task.py`, TODOs 1–10)**
- [x] TODO 1: `n` — generate multiple completion choices (`n=3`)
- [x] TODO 2: `temperature` — compare deterministic (`0.0`) vs creative (`1.2`) sampling
- [x] TODO 3: `top_p` — compare narrow (`0.1`) vs wide (`0.9`) nucleus sampling
- [x] TODO 4: `max_tokens` — compare tight (`50`) vs generous (`256`) output budgets
- [x] TODO 5: `stop` — halt generation at a custom stop sequence (`stop=["5"]`)
- [x] TODO 6: `response_format` — enforce strict JSON Schema output (`type="json_schema"`)
- [x] TODO 7: `frequency_penalty` — compare `0.0` vs `1.5` token frequency penalty
- [x] TODO 8: `presence_penalty` — compare `0.0` vs `1.5` token presence penalty
- [x] TODO 9: `seed` — run twice with `seed=42, temperature=0.0` to compare reproducibility
- [x] TODO 10: `reasoning_effort` — compare `"low"` vs `"high"` reasoning effort

**2. OpenAI Responses API (`openai_responses_task.py`, TODOs 1–8)**
- [x] TODO 1: `temperature` — `0.0` vs `1.2`
- [x] TODO 2: `top_p` — `0.1` vs `0.9`
- [x] TODO 3: `max_output_tokens` — `50` vs `256` (replaces `max_tokens`)
- [x] TODO 4: `text` — structured JSON output via `text={"format": {"type": "json_schema", ...}}`
- [x] TODO 5: `truncation` — automatic context window truncation (`truncation="auto"`)
- [x] TODO 6: `metadata` — attach request tracking key-value metadata
- [x] TODO 7: `reasoning` — `reasoning={"effort": "low"}` vs `reasoning={"effort": "high"}`
- [x] TODO 8: `instructions` & `store` — top-level instructions and stored response state

**3–4. Anthropic & Gemini (Optional)**
- [ ] Skipped (exercise focused on OpenAI / EPAM DIAL only)

## How to test locally and see step-by-step live output (`uv run`)

First, export your root `.env` variables in your shell (using `source` ensures `.env` overrides any pre-existing shell variables):

```bash
set -a; source .env; set +a
```

### Option A: Run directly from `app_development/t2-llms-output-tuning/solution` with `uv run`

Run all 10 OpenAI Chat Completions output-tuning steps live and print each request + assistant output:

```bash
uv run --with requests --with openai --with pytest \
  --directory app_development/t2-llms-output-tuning/solution \
  python -m t2_llms_output_tuning.openai_chat_completions_task --step all --only-content
```

Run a single step (for example, Step 6 `response_format` JSON Schema, printing the full raw JSON response):

```bash
uv run --with requests --with openai \
  --directory app_development/t2-llms-output-tuning/solution \
  python -m t2_llms_output_tuning.openai_chat_completions_task --step 6
```

Run the OpenAI Responses API steps (1–8):

```bash
uv run --with requests --with openai \
  --directory app_development/t2-llms-output-tuning/solution \
  python -m t2_llms_output_tuning.openai_responses_task --step all --only-content
```

Run in interactive chat mode (`input("> ")` loop):

```bash
uv run --with requests --with openai \
  --directory app_development/t2-llms-output-tuning/solution \
  python -m t2_llms_output_tuning.openai_chat_completions_task --interactive
```

### Option B: Run from the course fork (`workspace/ai-applications-development-from-api-to-agents`)

```bash
cd workspace/ai-applications-development-from-api-to-agents
set -a; source ../../.env; set +a

# Run all 10 Chat Completions steps (content view)
uv run python -m t2_llms_output_tuning.openai_chat_completions_task --step all --only-content

# Run a single step with full JSON response body (e.g. step 1: n=3, step 4: max_tokens, step 6: json_schema)
uv run python -m t2_llms_output_tuning.openai_chat_completions_task --step 1

# Run all 8 Responses API steps
uv run python -m t2_llms_output_tuning.openai_responses_task --step all --only-content
```

### Option C: Run with `pytest` (`uv run ... pytest -s`)

Run the fast offline unit tests (verifies DIAL `base_url` derivation, header redaction, and kwargs forwarding across all 18 steps):

```bash
uv run --with requests --with openai --with pytest \
  --directory app_development/t2-llms-output-tuning/solution \
  python -m pytest t2_llms_output_tuning/test_t2_output_tuning.py -k "not live" -v
```

Run the **live** step-by-step suite with `-s` to stream every request and live DIAL response to the terminal:

```bash
set -a; source .env; set +a
uv run --with requests --with openai --with pytest \
  --directory app_development/t2-llms-output-tuning/solution \
  python -m pytest -s t2_llms_output_tuning/test_t2_output_tuning.py -k "live_chat_completions"
```

## Deliverables

- `solution/`: self-contained `t2_llms_output_tuning/` and `commons/` modules for the OpenAI exercises, plus `test_t2_output_tuning.py`. Contains no keys or `.env` files.

## Results / notes

Live step-by-step run against EPAM DIAL (`OPENAI_MODEL` from `.env`, key `<redacted>`):

- **Step 1 (`n=3`)**: Returns 3 distinct completions in a single call:
  ```text
  --- Sub-run: n=3 ---
  🔗 Endpoint: <OPENAI_BASE_URL>/chat/completions
  📋 Headers:
    Authorization: Bearer <redacted>
    Content-Type: application/json
  ================================================== RESPONSE ==================================================
  [choice 0] Ember & Bean
  [choice 1] Eclipse Brew
  [choice 2] "The Grindstone"
  ```
- **Step 4 (`max_tokens=50` vs `max_tokens=256`)**: `max_tokens=50` truncates mid-sentence (`...Because of two key quantum effects, qu`), whereas `max_tokens=256` completes the full explanation and analogy.
- **Step 5 (`stop=["5"]`)**: Generation stops right before emitting `"5"`:
  ```text
  ================================================== RESPONSE ==================================================
  1, 2, 3, 4, 
  ```
- **Step 6 (`response_format` with strict `json_schema`)**: Returns schema-valid JSON matching the `languages` array contract:
  ```json
  {
    "languages": [
      {
        "name": "Python",
        "year": 1991
      },
      {
        "name": "JavaScript",
        "year": 1995
      },
      {
        "name": "Go",
        "year": 2009
      }
    ]
  }
  ```
- **Step 9 (`seed=42, temperature=0.0`)**: Demonstrates that `seed` + `temperature=0.0` is best-effort rather than guaranteed deterministic (`Ember & Bean` on run 1 vs `Brew & Bean` on run 2 across load-balanced backend instances).
- **Step 10 (`reasoning_effort="low"` vs `"high"`)**: Both correctly count 3 `r`'s in `"strawberry"`.
- **Responses API (`openai_responses_task.py`)**: Deployment-dependent on EPAM DIAL; when `OPENAI_BASE_URL` points to an Azure-style `/openai/deployments/<model>` endpoint that only exposes `/chat/completions`, the step runner prints each formatted Responses API request payload (`input`, `max_output_tokens`, `text.format`, `truncation`, `metadata`, `reasoning`) and reports `Route is not found` cleanly without aborting.
