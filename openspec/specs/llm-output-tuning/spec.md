# llm-output-tuning Specification

## Purpose
Experiment with and verify LLM output-tuning parameters on OpenAI Chat Completions and OpenAI Responses APIs against EPAM DIAL, with step-by-step non-interactive execution and interactive chat support.

## Requirements

### Requirement: Model-agnostic DIAL endpoint routing for output tuning
`OpenAIChatCompletionsClient` and `OpenAIResponsesClient` SHALL read `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` via `commons/constants.py` and route requests to `<OPENAI_BASE_URL>/chat/completions` and `<OPENAI_BASE_URL>/responses` respectively.

#### Scenario: OpenAIResponsesClient derives base_url from endpoint
- **WHEN** `OpenAIResponsesClient` is instantiated with `OPENAI_BASE_URL` set
- **THEN** the underlying `OpenAI` SDK client `base_url` matches `<OPENAI_BASE_URL>` without `/responses`

#### Scenario: Empty API key rejected
- **WHEN** `OpenAIChatCompletionsClient` or `OpenAIResponsesClient` is constructed with an empty `OPENAI_API_KEY`
- **THEN** a `ValueError` is raised before any network call

### Requirement: OpenAI Chat Completions output-tuning steps (TODOs 1–10)
`openai_chat_completions_task.py` SHALL define and execute step-by-step experiments covering all 10 Chat Completions output-tuning tasks:
1. `n` (multiple completions)
2. `temperature` (`0.0` vs `1.2` / `2.0`)
3. `top_p` (`0.1` vs `0.9`)
4. `max_tokens` / `max_completion_tokens` (`50` vs `512`)
5. `stop` (`stop=["5"]`)
6. `response_format` (`json_schema` structured output)
7. `frequency_penalty` (`0.0` vs `1.5`)
8. `presence_penalty` (`0.0` vs `1.5`)
9. `seed` (`seed=42` repeated twice)
10. `reasoning_effort` (`"low"` vs `"high"`)

#### Scenario: Step-by-step execution forwards tuning kwargs
- **WHEN** a Chat Completions step is executed via `run_step`
- **THEN** the client sends the step's prompt and tuning `kwargs` in the request payload and prints the redacted request and response

### Requirement: OpenAI Responses API output-tuning steps (TODOs 1–8)
`openai_responses_task.py` SHALL define and execute step-by-step experiments covering all 8 Responses API output-tuning tasks:
1. `temperature` (`0.0` vs `1.2`)
2. `top_p` (`0.1` vs `0.9`)
3. `max_output_tokens` (`50` vs `512`)
4. `text` (`text={"format": {"type": "json_schema", ...}}`)
5. `truncation` (`truncation="auto"`)
6. `metadata` (`metadata={"project": "demo", "user": "student-1"}`)
7. `reasoning` (`reasoning={"effort": "low"}` vs `reasoning={"effort": "high"}`)
8. `instructions` and `store` + `previous_response_id`

#### Scenario: Responses API step-by-step execution forwards tuning kwargs
- **WHEN** a Responses API step is executed via `run_step`
- **THEN** the client passes the step's input messages and tuning `kwargs` to `responses.create` and prints the redacted request and response
