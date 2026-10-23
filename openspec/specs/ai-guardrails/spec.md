# ai-guardrails Specification

## Purpose
Demonstrate and compare four AI guardrail layers—system prompt hardening, LLM-based input validation, LLM-based output validation (hard and soft modes), and real-time streaming PII redaction (regex and Microsoft Presidio)—through EPAM DIAL.

## Requirements

### Requirement: DIAL configuration
The solution SHALL load the root `.env` without overriding exported variables, use the three existing OPENAI variables, reject public OpenAI hosts, and keep keys out of errors and output.

#### Scenario: Deployment configuration
- **WHEN** a DIAL deployment URL and model are configured
- **THEN** chat and streaming requests use DIAL deployment routes with Api-Key authentication and no hard-coded model-specific generation settings.

### Requirement: Four progressive guardrail tasks
The solution SHALL implement system prompt hardening (`t1`), pre-LLM input validation (`t2`), post-LLM output validation with soft redaction and hard blocking (`t3`), and rolling-buffer streaming PII redaction with both regex and Microsoft Presidio (`t4`).

#### Scenario: Pre-LLM input blocking
- **WHEN** a user input contains a prompt injection or requests restricted PII
- **THEN** the input validator returns `valid=False` with a description and blocks the query before calling the assistant.

#### Scenario: Post-LLM output validation
- **WHEN** an assistant response leaks restricted PII
- **THEN** the output validator flags `valid=False` and either redacts sensitive values with labeled placeholders (`soft_response=True`) or replaces the response with a block message (`soft_response=False`).

#### Scenario: Streaming chunk-boundary PII redaction
- **WHEN** sensitive PII tokens are split across consecutive streaming chunks
- **THEN** the rolling buffer and safety margin hold partial tokens until complete and redact them before flushing output.

### Requirement: Reproducible deliverables
The solution SHALL include standalone run instructions, offline tests, and git-ignored output captures for all tasks and offline demonstrations.

#### Scenario: Secret-safe evidence
- **WHEN** scenarios are captured to `solution/output/`
- **THEN** logs exclude API credentials and record per-scenario results and token usage in `summary.json`.
