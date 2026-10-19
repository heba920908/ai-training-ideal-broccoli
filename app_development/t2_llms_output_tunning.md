# LLM Output Tuning

Output tuning controls how a model selects tokens, how much it can generate, and what format it returns. These settings complement the prompt; they do not replace clear instructions, factual checks, or application-side validation.

## How to Read the Parameters

Most generation controls fall into five groups:

| Control | What it changes | Typical parameters | Main trade-off |
|---|---|---|---|
| Sampling | How the model chooses the next token from candidate tokens. | `temperature`, `top_p` / `topP`, `top_k` / `topK` | Lower randomness can improve consistency, but does not guarantee correctness or identical responses. |
| Output budget | The maximum number of tokens the model may generate. | `max_completion_tokens`, `max_output_tokens`, `max_tokens`, `maxOutputTokens` | A low cap can truncate an answer; a high cap permits more output and potentially more cost. |
| Repetition control | How strongly previously generated tokens are discouraged. | `frequency_penalty`, `presence_penalty` | Reducing repetition can also discourage necessary terms or shift the answer away from the task. |
| Format and boundaries | The output structure or the conditions that end generation. | Schema settings, MIME types, stop sequences | Schemas constrain structure, not factual accuracy; stop sequences can cut off otherwise valid output. |
| Reasoning | How much internal reasoning the model is allowed or encouraged to perform. | `reasoning_effort`, `reasoning`, `thinking`, `thinkingConfig` | More reasoning can improve difficult-task results, but can increase latency and token usage. |

**Compatibility matters:** the tables below describe API parameter names, not a guarantee that every model accepts them. Defaults, supported values, and interactions depend on the model, endpoint, and API version. Numeric tuning suggestions are starting points for experiments, not universal presets. A temperature of `1.0` does not imply equivalent behavior across providers.

**Course configuration:** exercises use the EPAM DIAL OpenAI-compatible interface by default. Keep `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` environment-driven. The native provider APIs below are references; their features are not automatically available through DIAL. Check the deployed model and proxy's supported endpoints and parameters before using them.

## OpenAI: Chat Completions

> Full reference: [OpenAI Chat Completions](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create).

The Chat Completions API (`POST /v1/chat/completions`) takes conversation history in `messages`. Generation controls are top-level request fields.

### Key Parameters

| Parameter | Range / values | Default / requirement | Description | When to use |
|---|---|---|---|---|
| `temperature` | `0.0` to `2.0`, where supported | Usually `1.0`; model-dependent | Adjusts the token probability distribution. Lower values favor more likely tokens; higher values increase randomness. | Try a low value for extraction or classification and a moderate value for conversation. Higher values can help brainstorming, but test for incoherent output. Even `0.0` is not a determinism guarantee. |
| `top_p` | `0.0` to `1.0` | Usually `1.0`; model-dependent | Nucleus sampling: restricts candidates to a set whose cumulative probability reaches the chosen threshold. | An alternative to temperature. Lower values narrow the candidate set; values near `1.0` retain more possibilities. Start by changing one sampling control, not both. |
| `max_completion_tokens` / legacy `max_tokens` | Positive integer within model limits | Model-dependent | Caps generated tokens. `max_completion_tokens` includes visible output and reasoning tokens where applicable. `max_tokens` is deprecated and incompatible with some reasoning models. | Set an explicit budget suited to the task. Short labels need less room than summaries or long documents. Leave room for reasoning when applicable, and inspect the finish reason for truncation. |
| `n` | Positive integer | `1` | Requests multiple completion choices in one call, where supported. | Generate alternative names, subject lines, or drafts. Token usage and cost grow with the total generated across choices. Not available in the Responses API. |
| `stop` | String or array of up to four strings | Not set | Ends generation when a matching sequence is produced; the stop sequence is not included in the returned text. Some models do not support it. | Use controlled template markers such as `"###"`. A newline stop can force a single line, but may truncate useful content or break JSON. |
| `response_format` | Object, such as `{"type": "text"}`, `{"type": "json_object"}`, or a `json_schema` configuration | Text output | Selects plain text, JSON mode, or schema-constrained output on supported models. JSON mode alone does not enforce a particular schema. | Use a supported strict JSON Schema configuration for typed extraction or API responses. Still handle refusals, truncation, and validation failures. |
| `frequency_penalty` | `-2.0` to `2.0`, where supported | `0.0` | Penalizes tokens in proportion to how often they have appeared. Positive values discourage repetition; negative values encourage it. | Experiment with modest positive values for repetitive long-form writing. Keep the default when technical terms must recur. Strong negative values can amplify repetition. |
| `presence_penalty` | `-2.0` to `2.0`, where supported | `0.0` | Applies a penalty based on whether a token has appeared at all, rather than its frequency. Positive values encourage different tokens. | Try modest positive values for brainstorming. It is not a direct topic-control setting; use the prompt to define scope and relevance. |
| `seed` | Integer, where supported | Not set | Requests best-effort reproducibility. Availability is limited, and the parameter is deprecated in the reference. | Helpful for controlled comparisons on supported models. Identical inputs and seeds can still produce different results; do not rely on exact output equality in regression tests. |
| `reasoning_effort` | Model-specific effort levels; examples include `"low"`, `"medium"`, and `"high"` | Model-dependent | Controls internal reasoning effort on supported reasoning models. Accepted levels and sampling compatibility vary. | Use lower effort for simple tasks and higher effort for difficult logic, math, or debugging. Check the selected model's restrictions rather than assuming a universal temperature rule. |

### Practical Interpretation

- **Temperature changes randomness, not knowledge.** Lowering it may make an incorrect answer more consistent; it does not make that answer true.
- **A token cap is a ceiling, not a target length.** Ask for a concise answer in the prompt as well as setting a budget. Very small caps can prevent a complete response.
- **Structured output is a contract about shape.** Validate both the schema and business rules, such as whether an extracted date is plausible.

## OpenAI: Responses API

> Full reference: [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create).

The Responses API (`POST /v1/responses`) supports text generation, tools, and conversation state. Several Chat Completions fields have different names or structures here, so migration is not just an endpoint change.

### What Changes Compared to Chat Completions

| Chat Completions | Responses API | What changes | When to use / why it matters |
|---|---|---|---|
| `messages` | `input` | Accepts text or an array of input items, including messages and tool-related items. | Supply the user's task and relevant context. Do not assume every Chat Completions message object can be copied unchanged. |
| `system` / `developer` messages in `messages` | Top-level `instructions`, or supported instruction messages in `input` | `instructions` provides a dedicated place for system/developer guidance; message-based instructions are also supported. | Separate application rules from user content. When using `previous_response_id`, prior top-level instructions are not automatically carried forward; send them again if needed. |
| `max_completion_tokens` / legacy `max_tokens` | `max_output_tokens` | Uses a different field name; the cap includes visible output and reasoning tokens where applicable. | Revisit the budget during migration rather than assuming the entire allowance is available for the final answer. |
| `response_format` | `text.format` | Format configuration is nested, for example `text={"format": {...}}`. The schema configuration shape also differs. | Adapt structured-output requests to the target API instead of only renaming the outer field. |
| `stop` | No equivalent request field | Stop sequences are not available in this API. | Redesign the output contract using supported format controls, prompt instructions, and application-side checks. |
| Manually supplied history | `store` and `previous_response_id`, or a conversation | Stored responses can be linked so the application need not resend all prior items. Storage is subject to account and retention policies. | Useful for multi-turn applications. Smaller request payloads do not imply free context: earlier input tokens in the chain still count toward billing. |
| Context managed by the caller | `truncation` | `"disabled"` rejects over-limit input; `"auto"` drops earlier conversation items as needed. Default: `"disabled"`. | Use automatic truncation only if losing older context is acceptable. Keep essential rules and facts available to the model. |
| Request annotations such as `metadata` | `metadata` | Supports up to 16 key-value pairs, with keys up to 64 characters and string values up to 512 characters. It is not unique to Responses. | Tag requests for tracking or filtering. Do not put secrets or unnecessary personal data in metadata. |
| `reasoning_effort` | `reasoning.effort` | Uses an object, for example `reasoning={"effort": "high"}`. Supported effort levels remain model-dependent. | Tune reasoning separately from answer length and verify compatibility with sampling settings. |
| `temperature`, `top_p` | `temperature`, `top_p` | Names are retained, but model support still varies. | Re-test sampling behavior after changing either the endpoint or the model. |
| `n`, `frequency_penalty`, `presence_penalty`, `seed` | No corresponding request fields | These Chat Completions controls are not part of the Responses request interface. | Do not forward a shared configuration dictionary blindly. Request separate responses for alternatives and reassess repetition or reproducibility strategies. |

**Migration rule:** build a configuration for the target endpoint. Similar purpose does not imply identical field names, defaults, or supported behavior.

## Anthropic: Messages API

Full reference: [Anthropic Messages API](https://platform.claude.com/docs/en/api/messages/create).

Anthropic's Messages API (`POST /v1/messages`) has its own request contract. Sampling settings are top-level fields, while structured output and reasoning use configuration objects.

### Key Parameters

| Parameter | Range / values | Default / requirement | Description | When to use |
|---|---|---|---|---|
| `temperature` | `0.0` to `1.0`, on models that support it | Typically `1.0`; model-dependent | Controls sampling randomness. Some models restrict or do not accept sampling overrides. | Where supported, try lower values for consistency and higher values for variety. A value of `0.0` is not fully deterministic, and values cannot be compared directly with OpenAI's scale. |
| `top_p` | Probability threshold, where supported | Model-dependent | Nucleus sampling; narrows candidates by cumulative probability. | An alternative to temperature. Check model restrictions before combining the two or using them with thinking. |
| `top_k` | Positive integer, where supported | Not set | Restricts sampling to the top K candidate tokens. | A small K narrows choices. `top_k=1` selects the highest-ranked candidate at the sampling step, but is not an end-to-end reproducibility guarantee. |
| `max_tokens` | Positive integer within model limits | Required | Sets the maximum generated-token budget. Thinking can consume part of the allowance. | Always provide it. Choose a budget for the answer and any reasoning, and handle the `max_tokens` stop reason as potentially incomplete output. |
| `stop_sequences` | Array of strings | Not set | Ends generation when a custom sequence is encountered. | Use markers for controlled templates. Check the returned stop reason and matched sequence; avoid markers that can appear inside legitimate content. |
| `output_config.format` | JSON Schema format object on supported models | Not set | Configures schema-constrained JSON output, for example `{"type": "json_schema", "schema": {...}}` inside `output_config.format`. | Use for extraction or typed downstream data. Check schema limitations and handle refusals or incomplete responses before parsing. |
| `thinking` | Model-specific object, such as `{"type": "adaptive"}` or supported manual mode `{"type": "enabled", "budget_tokens": N}` | Model-dependent | Configures internal reasoning. Manual budgets are supported only on applicable models; newer models may require adaptive thinking. | Use for difficult reasoning or debugging. For ordinary manual-budget requests, the thinking budget must fit below `max_tokens`; check the documented constraints and exceptions. Adaptive thinking uses model-specific controls, including `output_config.effort` where supported. |

See [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) and [thinking configuration](https://platform.claude.com/docs/en/build-with-claude/extended-thinking) for the supported request shapes.

**Important distinction:** reasoning controls allocate internal computation. They do not guarantee access to a complete chain of thought; returned thinking content may be summarized or otherwise limited.

## Google: Gemini API

> Full reference: [Google Gemini GenerateContent API](https://ai.google.dev/api/generate-content).

This section covers `POST /v1beta/models/{model}:generateContent`, where generation settings belong inside `generationConfig`. The field names below use REST JSON casing; SDK naming and other Google API interfaces can differ.

### Key Parameters Inside `generationConfig`

| Parameter | Range / values | Default / requirement | Description | When to use |
|---|---|---|---|---|
| `temperature` | Commonly `0.0` to `2.0`; check the model | Model-dependent | Controls randomness in token selection. | Start from the model's recommended default. Test lower values for consistency only where appropriate; some reasoning models work best with their default temperature. |
| `topP` | Probability threshold from `0.0` to `1.0`, where supported | Model-dependent | Nucleus sampling using cumulative token probability. | Lower values narrow the candidate set. Treat it as an alternative sampling control to tune experimentally, not a guarantee of better factual accuracy. |
| `topK` | Positive integer, where supported | Model-dependent; not universally `40` | Limits candidates to the top K tokens. Some models do not allow this field to be set. | Use only when supported. A value of `1` narrows selection to the highest-ranked candidate, while larger values permit more alternatives. |
| `maxOutputTokens` | Positive integer within model limits | Model-dependent; not universally `1024` | Caps generated output. On thinking models, reasoning can consume the generation budget. | Set a task-appropriate limit, leaving room for reasoning if needed. Inspect the candidate finish reason for token-limit termination. |
| `responseMimeType` | Supported types include `"text/plain"`, `"application/json"`, and `"text/x.enum"` | `"text/plain"` | Selects the response format on supported models. MIME type alone does not define all required fields. | Use JSON for machine-readable data. Enum output requires an accompanying schema that defines the allowed labels. |
| `responseSchema` | Supported schema object / JSON Schema subset | Not set | Describes the expected output structure. For JSON output, pair it with `responseMimeType: "application/json"`. Enum classification uses a compatible string-enum schema. | Use for typed extraction and constrained classification. Check the supported schema subset; do not assume arbitrary JSON Schema features are accepted. |
| `stopSequences` | Array of strings within the API's documented limit | Not set | Stops generation when a supplied sequence is encountered. | Useful for tightly controlled templates. Ensure markers cannot accidentally cut off valid content, especially structured output. |
| `thinkingConfig` | Model-specific object using fields such as `thinkingBudget` or `thinkingLevel` | Model-dependent; thinking may be enabled by default | Configures internal reasoning. The original `thinkMode` / `thinkBudget` names are not the GenerateContent request fields. | Use the control supported by the selected model. Do not assume thinking is disabled, can always be disabled, or accepts the same budget across models. |

**Do not copy configuration objects across providers.** For example, `max_tokens`, `max_output_tokens`, and `maxOutputTokens` play similar roles but belong to different request contracts.

## Summary and Recommendations

### General Advice

1. **Start with a clear prompt and a baseline.** Define a measurable goal, such as valid extraction, accurate classification, or acceptable latency, before changing parameters.
2. **Tune one sampling control at a time.** Start with temperature or nucleus sampling, leaving the other at its documented default. This makes comparisons easier and follows common provider guidance.
3. **Set an explicit output budget.** Choose it for the task and model, including reasoning where applicable. A cap limits generation but is not a complete cost estimate or a desired response length.
4. **Use schemas for machine-readable output.** A prompt asking for JSON is weaker than supported schema-constrained output. Validate the result and handle refusals and truncation explicitly.
5. **Measure quality, latency, and token usage together.** More reasoning or a longer response is not automatically better.
6. **Keep configurations endpoint- and model-specific.** Verify both provider and proxy support. Unsupported parameters may be rejected, and intermediaries may handle them differently.

### The Migration Problem

Parameter sets are not stable across model generations, vendors, or API interfaces. Treat a major model or endpoint change as a potential breaking change:

- In OpenAI Chat Completions, prefer the supported `max_completion_tokens` field over legacy `max_tokens`; this is not simply a rename tied to one model generation.
- In OpenAI Responses, use `max_output_tokens`, `text.format`, and `reasoning.effort` instead of copying their Chat Completions counterparts.
- Do not carry `stop`, `n`, penalties, or `seed` into Responses requests.
- Anthropic uses `stop_sequences` and may support `top_k`; OpenAI Chat Completions uses `stop` and has no equivalent `top_k` field.
- Gemini GenerateContent nests its controls under `generationConfig` and uses REST names such as `topP` and `maxOutputTokens`.
- Reasoning modes and their compatibility with sampling settings can change even when other parameter names stay the same.

Before deploying, check the target model's documentation, send a small compatibility request through the actual deployment, and run a representative evaluation set.

### Real-World Pitfalls

These are possible failure modes, not guaranteed outcomes at a particular numeric setting.

| Situation | What can happen | Lesson |
|---|---|---|
| Very high temperature, such as `1.5` or above on a model that accepts it | More varied output can become incoherent, inconsistent, or unsuitable for the task. | There is no universal safe threshold. Start from the model's recommendation and increase only when evaluations justify it. |
| A strong negative `frequency_penalty`, such as `-2.0` | Repeated tokens are rewarded, which can produce repetitive loops until a stop condition or token cap is reached. | Avoid aggressive negative penalties unless repetition is intentional; always set a generation limit. |
| Combining reasoning settings with unsupported sampling overrides | The endpoint can reject the request, or a proxy may handle the unsupported fields differently. | Check the exact model and endpoint. Do not apply a blanket "reasoning requires temperature 1.0" rule across providers. |
| Reusing legacy `max_tokens` after changing OpenAI models | Some models reject it or require `max_completion_tokens`. | Revalidate parameter names and accepted values after upgrades. |
| Setting a very small output budget on a reasoning model | Reasoning can consume the allowance before a complete visible answer is produced. | Budget for both reasoning and the answer; inspect completion status before treating the output as usable. |
| Expecting a seed or temperature `0.0` to make tests exact | Repeated calls can still differ because model execution or backend behavior changes. | Test required properties and quality criteria rather than exact wording. |
| Treating schema-constrained output as proof of correctness | Well-formed fields can still contain incorrect facts or violate business rules. | Validate semantics as well as syntax, and handle refusals and incomplete responses. |

### A Simple Tuning Workflow

1. Choose representative inputs and define what a good response must satisfy.
2. Record the model, endpoint, prompt, and baseline configuration without recording secrets.
3. Change one setting and compare repeated runs against the baseline.
4. Inspect validity, task quality, finish reasons, token usage, and latency.
5. Keep the configuration only if it improves the intended outcome; repeat the evaluation after upgrades.
