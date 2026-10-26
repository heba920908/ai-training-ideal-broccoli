# T8: AI Agent (Tool Use)

Build a tool-calling agent from scratch that manages users in a local mock service. It also uses web search to enrich new profiles. The agentic loop runs over the OpenAI-compatible **EPAM DIAL** Chat Completions API by default. An Anthropic Messages variant uses DIAL's Anthropic-compatible route.

## Source

- Course: <https://github.com/epam/ai-applications-development-from-api-to-agents>, Python task `t8_agent`.
- The complete standalone implementation is bundled in [solution/](solution). The workspace clone is not required.
- Background: [../t8_agent.md](../t8_agent.md).

## Tasks

- [x] Reuse the T6 Podman user service as the prerequisite.
- [x] Implement provider tool schemas in `BaseTool` (`openai_schema`, `anthropic_schema`).
- [x] Implement the user tools: `get_user_by_id`, `search_users`, `add_user`, `update_user`, `delete_users`.
- [x] Implement `web_search_tool` with the Responses API `web_search` tool.
- [x] Implement `BaseAgent`, `OpenAIBasedAgent`, and the system prompt.
- [x] Wire `app.py` and try the sample inputs.
- [x] Implement `AnthropicBasedAgent` and run it through DIAL.
- [x] Verify with offline tests, lint, and live DIAL runs with the DeepSeek deployment.

## Provider Adapters

Only `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` from the repository-root `.env` are required. The template is [../../.env.example](../../.env.example). [solution/commons/constants.py](solution/commons/constants.py) loads the nearest ancestor `.env` without overriding exported variables. It derives every endpoint from `OPENAI_BASE_URL`:

| Use | Endpoint | Model Source | Auth |
| --- | --- | --- | --- |
| Agent, `--provider openai` (default) | `<OPENAI_BASE_URL>/chat/completions` | `--model`, default `OPENAI_MODEL` | `Authorization: Bearer` |
| Web search tool | `<DIAL origin>/openai/v1/responses` (model in body) | `--web-search-model`, default `OPENAI_MODEL` | `Authorization: Bearer` |
| Agent, `--provider anthropic` | `<DIAL origin>/anthropic/v1/messages` | `--model` (a Claude deployment) | `x-api-key` + `anthropic-version` |

No deployment name is hard-coded, and no extra environment variables are introduced. The DIAL key is used for every route. The agent sends no model-specific parameters such as `reasoning_effort`, which the course template adds for GPT-5.6. Any DIAL chat deployment that supports function calling works unchanged.

Capabilities observed on DIAL on **2026-10-23**:

- `DeepSeek-V4-Flash-2026-04-23` supports Chat Completions function calling (`finish_reason: "tool_calls"`). This works even though its `/openai/models` entry does not advertise `tools`.
- The course's per-deployment `.../deployments/<name>/responses` route returns 404 on DIAL. The working route is `/openai/v1/responses` with `model` in the body.
- DeepSeek returns `503 OpenAI responses not supported for this deployment type`, so it **cannot run web search**. The tool returns that error to the agent. The agent then reports it and asks the user for the missing details. Pass `--web-search-model "<responses-capable-deployment>"` to enable search. A GPT deployment returned `web_search_call` items plus cited `output_text`.
- DeepSeek returns 503 on the Anthropic route. `--provider anthropic` needs a Claude deployment on DIAL.

## How to Run

Run all commands from the repository root. Requires Python 3.11+, `uv`, Podman, and `podman-compose`. Dependencies are in [solution/t8_agent/requirements.txt](solution/t8_agent/requirements.txt).

### Prerequisite: User Service (Shared With T6)

T8 uses the same mock user service as T6. Start it with the **T6** Compose file. See [T6: Start the User Service](../t6-grounding/README.md#start-the-user-service) for details on the image, the `USERS_NUMBER` variable, and data reset.

```bash
podman-compose -p t6-grounding \
  -f app_development/t6-grounding/solution/t6_grounding/docker-compose.yml up -d

curl --fail http://127.0.0.1:8041/health
curl --fail --silent http://127.0.0.1:8041/v1/users | jq length
```

If T6 is already running, skip this step. The course's own `t8_agent/docker-compose.yml` is not bundled. It sets `USER_COUNT`, which the image ignores, so it creates 1,000 users and puts more tokens into each search. Swagger: <http://127.0.0.1:8041/docs>.

### Interactive Agent

```bash
uv run \
  --with-requirements "$PWD/app_development/t8-agent/solution/t8_agent/requirements.txt" \
  --directory app_development/t8-agent/solution \
  python -u -m t8_agent.task.app
```

Sample inputs: `Find all female users`, `Add Andrej Karpathy as a new user`, `Delete user with id 3`. Enter `exit`, `quit`, or EOF to stop. The conversation is kept in memory for the session.

| Option | Effect |
| --- | --- |
| `--provider openai\|anthropic` | Selects the Chat Completions agent (default) or the Anthropic Messages agent. |
| `--model "<deployment>"` | Overrides the agent deployment. Default: `OPENAI_MODEL`. |
| `--web-search-model "<deployment>"` | Responses-API deployment for `web_search_tool`. Default: `OPENAI_MODEL`. |
| `--quiet` | Hides request/response payloads. Tool calls and results are still printed. |

The default mode prints every request and response payload, as the course asks. API keys are never printed, because headers are not logged.

Examples:

```bash
# DeepSeek agent + a Responses-capable deployment for web search
uv run --with-requirements "$PWD/app_development/t8-agent/solution/t8_agent/requirements.txt" \
  --directory app_development/t8-agent/solution \
  python -u -m t8_agent.task.app --quiet --web-search-model "<responses-capable-deployment>"

# Anthropic agent over DIAL
uv run --with-requirements "$PWD/app_development/t8-agent/solution/t8_agent/requirements.txt" \
  --directory app_development/t8-agent/solution \
  python -u -m t8_agent.task.app --quiet --provider anthropic --model "<claude-deployment>"
```

Input can be piped for scripted runs, for example `printf '%s\n' "Find all female users" exit | ...`.

### Tests and Static Checks

The suite makes no DIAL calls and needs no running service:

```bash
uv run \
  --with-requirements "$PWD/app_development/t8-agent/solution/t8_agent/requirements.txt" \
  --with pytest --directory app_development/t8-agent/solution \
  python -m pytest -q -p no:cacheprovider

uv run --with ruff ruff check app_development/t8-agent/solution/t8_agent \
  app_development/t8-agent/solution/commons/constants.py
```

The other `commons/` files are verbatim course code and are not linted. Tests cover:

- endpoint derivation from `OPENAI_BASE_URL`
- the six tool names and both provider schemas, including resolvable `$ref`s
- ID casting, Pydantic validation, and service errors returned as strings
- the web search request shape and its error path
- the OpenAI loop: system prompt not stored, no `reasoning_effort`, unknown tools, invalid JSON arguments, HTTP errors
- the Anthropic loop: `x-api-key`, top-level `system`, grouped `tool_result` blocks, replayed `tool_use` blocks
- the app input loop

### Stop the Service

```bash
podman-compose -p t6-grounding \
  -f app_development/t6-grounding/solution/t6_grounding/docker-compose.yml stop
```

## Deliverables and Local Output

- [solution/t8_agent/task/tools/](solution/t8_agent/task/tools): `BaseTool` schemas, five user tools, and the web search tool.
- [solution/t8_agent/task/agents/](solution/t8_agent/task/agents): `BaseAgent`, `OpenAIBasedAgent`, and `AnthropicBasedAgent`.
- [solution/t8_agent/task/prompts.py](solution/t8_agent/task/prompts.py): the system prompt (domain scope, delete confirmation, web search fallback, privacy, untrusted tool output).
- [solution/t8_agent/task/app.py](solution/t8_agent/task/app.py): the CLI and the input loop.
- [solution/t8_agent/test_t8_agent.py](solution/t8_agent/test_t8_agent.py): offline tests.
- [solution/commons/](solution/commons): course shared code. Only `constants.py` is adapted, to add `.env` loading and the DIAL Responses and Anthropic routes.

Live transcripts are saved in the local `solution/output/` folder, which [.gitignore](.gitignore) excludes. They include synthetic payment fields from tool output, so do not force-add them.

## Results / Notes

Verified **2026-10-23**: **25 tests passed** in both the fork and the standalone solution, and Ruff reported no issues. Live runs used a fresh dataset of 24 synthetic users and the unchanged `DeepSeek-V4-Flash-2026-04-23` agent deployment:

| Run | Input | Outcome |
| --- | --- | --- |
| A: DeepSeek | `Find all female users` | Called `search_users`, which returned all 23 users. The service **ignores the `gender` query parameter**: a direct `curl ...search?gender=female` also returns every gender. The model filtered the records itself and listed the 2 female users. |
| A: DeepSeek | `Delete user with id 5` → `Yes, delete it` | Called `get_user_by_id`, showed the user, and asked for confirmation. It called `delete_users` only after the second message. The service then returned 404 for that ID. |
| DeepSeek, default search | `Add Andrej Karpathy as a new user` | `web_search_tool` got 503 (no Responses API). The agent said so and asked for the email; it did not invent one. |
| B: DeepSeek + GPT web search | Same, then supplied an `example.com` email | The web search returned a cited bio. `add_user` created ID 25 with a factual `about_me`. |
| C: Anthropic route, Claude deployment | `Set the company of the user with surname Karpathy to Eureka Labs` | `search_users`, then `update_user`. The service shows `company: Eureka Labs`; other fields were unchanged. |

Implementation notes:

- `update_user`'s schema hoists Pydantic `$defs` to the root. Otherwise the nested `#/$defs/...` references would not resolve.
- `UserServiceClient.update_user` sends `null` for omitted fields. The mock service treats them as "unchanged".
- Course `UserUpdate.credit_card` is typed as `UserCreate`, which is an upstream oddity. It is left as is.
- Tool errors and an unsupported web search deployment are returned to the model as strings. HTTP errors from the agent's own LLM call raise `RuntimeError`.

**Limits:** the agent loop recurses with no cap on tool rounds, as in the course design. Tool output still contains the service's full synthetic records, including card fields, which reach the LLM. Privacy relies on the system prompt (see T7 guardrails for enforcement). Delete confirmation is prompt-driven, not enforced in code. The service changes users periodically, so IDs and counts vary between runs.
