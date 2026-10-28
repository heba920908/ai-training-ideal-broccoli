# skill-enabled-agents Specification

## Purpose
Provide reusable skill packages and a bounded, model-agnostic DIAL agent with
progressive local skill loading, confined file access, and persistent MCP Python
execution, alongside scoped managed-provider SDK examples.

## Acceptance Status

The custom DIAL path has real execution evidence. Managed-provider live checks
were not run and were explicitly waived for closure; SDK/fake-client coverage
does not establish live API compatibility. See the
[2026-10-28 closure record](../../closure-2026-10-28.md).

## Requirements

### Requirement: Complete reusable skill packages
The solution SHALL provide valid calculator, style-guide, and unit-converter
skill metadata and complete every content TODO in the starter. Referenced scripts,
examples, and reference files SHALL be included in the delivered solution.

#### Scenario: Calculator samples use the supplied executable
- **WHEN** the four course calculator expressions are evaluated through the skill
- **THEN** the results are 1024, 192, 2, and 1036 respectively, within floating-point tolerance
- **AND** the skill documents the syntax accepted by the supplied calculator script

#### Scenario: Style guide covers all assigned content
- **WHEN** the skill and its two supporting documents are checked
- **THEN** the content covers every starter section and minimum example count
- **AND** the three course style prompts can be answered from consistent documented rules

#### Scenario: Converter covers the five course samples
- **WHEN** temperature, data size, speed, area, and cup-volume requests are executed
- **THEN** outputs match the supplied script's factors within documented tolerance
- **AND** results identify units and distinguish decimal/binary data sizes and US cups

### Requirement: Progressive disclosure and confined skill reads
The custom application SHALL load only validated skill metadata into its startup
prompt and SHALL expose `read_skill` for on-demand file reads within the configured
skill root. Both read and execution tools SHALL reject paths escaping that root.

#### Scenario: Skill activation does not preload script source
- **WHEN** the custom agent starts and receives a matching conversion request
- **THEN** startup XML contains metadata rather than full skill/reference/script content
- **AND** the agent reads the relevant SKILL.md before using its instructions
- **AND** script execution can occur by script_path without a model read of script source

#### Scenario: Invalid metadata is not advertised
- **WHEN** a skill has malformed YAML, an invalid name, a directory-name mismatch, or an empty description
- **THEN** it is skipped with a safe diagnostic rather than advertised or causing an unhandled startup failure

#### Scenario: Filesystem escape is refused
- **WHEN** a read or script_path uses traversal, an outside filesystem path, or a symlink outside the skill root
- **THEN** no outside content is returned or submitted to the interpreter
- **AND** the caller receives a correlated tool error

### Requirement: MCP execution preserves schemas, sessions, and failures
The interpreter tool SHALL discover `execute_code`, extend a copy of its schema
with optional script_path, prepend only valid confined script content, and parse
the full execution response. MCP resources SHALL close on all exit paths.

#### Scenario: Execution reuses the returned interpreter session
- **WHEN** a first execution returns session_info.session_id and a second execution uses that ID
- **THEN** the second call accesses state from the first session
- **AND** script_path is not forwarded as an MCP server argument
- **AND** the original discovered schema remains unchanged

#### Scenario: Bad execution results are not successful calculations
- **WHEN** a tool is absent, a script cannot be read, MCP reports isError, content is unusable, or result JSON is invalid
- **THEN** the operation produces a bounded actionable tool error
- **AND** unreadable script content is never submitted as code
- **AND** code is not automatically replayed after ambiguous execution failure

#### Scenario: Partial setup failure closes resources
- **WHEN** initialization, ping, discovery, tool construction, or a later query fails or is cancelled
- **THEN** all entered MCP and provider contexts are closed in reverse ownership order

### Requirement: Bounded model-agnostic custom agent
The custom agent SHALL use the configured DIAL deployment through the three
existing OPENAI_* variables, without fixed model-specific generation settings.
It SHALL preserve tool-call IDs, bound model/tool rounds, and handle tool failures.

#### Scenario: Tool argument and routing failures remain correlated
- **WHEN** a model supplies invalid JSON, a non-object argument, an unknown tool, or a failing execution
- **THEN** each result is attached to the original tool_call_id in order
- **AND** duplicate tool registrations are rejected and tools=None is accepted

#### Scenario: Repeated tool requests terminate
- **WHEN** a model continues requesting tools for ten rounds
- **THEN** the agent stops with a clear limit diagnostic rather than recursing indefinitely
- **AND** each model request has a 90-second timeout and at most one retry

#### Scenario: Provider configuration cannot silently change boundaries
- **WHEN** the configured provider host is public OpenAI or a URL embeds credentials
- **THEN** configuration is rejected before a network call
- **AND** valid DIAL settings retain the configured model and use Api-Key authentication

### Requirement: Managed skill lifecycle is scoped to owned resources
Both managed applications SHALL implement skill discovery/upload, skill selection,
conversation-state reuse, bounded execution, and cleanup. Cleanup SHALL delete only
resources created by the current invocation, never reused or unrelated skills.

#### Scenario: Discovery and upload preserve provider contracts
- **WHEN** matching skills occur on later listing pages or a new skill must be uploaded
- **THEN** discovery handles pagination and reuses a matching skill
- **AND** new uploads include only the selected skill's allowlisted files with correct relative paths

#### Scenario: Managed conversations retain execution context
- **WHEN** two managed-provider turns run with a selected skill
- **THEN** Anthropic preserves assistant blocks and reuses its container ID
- **AND** OpenAI-compatible Responses chains the previous response ID and selected hosted-shell skill
- **AND** documented continuation responses are handled within a ten-request bound

#### Scenario: Cleanup preserves pre-existing skills
- **WHEN** an invocation reuses one skill, creates another, and then exits or fails
- **THEN** cleanup attempts only deletion of the created skill and its owned versions
- **AND** the reused skill and unrelated account resources are not deleted
- **AND** cleanup errors do not hide the primary failure or expose credentials

### Requirement: Managed-provider access has explicit capability and cost gates
OpenAI-compatible managed examples SHALL retain the existing DIAL provider boundary.
Anthropic credentials/model SHALL come from environment configuration. Unsupported
managed APIs SHALL be reported without substituted execution or fabricated evidence.

#### Scenario: DIAL does not expose a required managed API
- **WHEN** the configured route cannot serve Skills or hosted-shell Responses
- **THEN** the managed path reports the unsupported capability without contacting public OpenAI
- **AND** its live acceptance task remains incomplete and the change is not archived as fully verified

#### Scenario: Live managed execution is bounded and credential-safe
- **WHEN** approved managed live verification runs
- **THEN** it uses a reviewed finite run budget, output-token bounds, and the fixed course samples
- **AND** safe usage/runtime metadata is captured without keys, tokens, or environment contents

### Requirement: Standalone delivery contains all required source dependencies
The artifact repository SHALL include a T12 task card and standalone solution
matching the reviewed copy manifest, including supporting skill files, original
task reference, required shared message/role modules, pinned dependencies, and tests.

#### Scenario: Solution runs without the ephemeral fork
- **WHEN** offline tests and scoped Ruff checks run from the standalone solution without the course fork on PYTHONPATH
- **THEN** imports, tests, lint, and format checks pass using only delivered files
- **AND** allowlisted final source copies match the verified fork files
- **AND** task-card links resolve to durable repository files

#### Scenario: Interpreter infrastructure stays isolated
- **WHEN** the documented T12 compose project is started
- **THEN** the verified pinned image binds only to a loopback port and uses documented resource limits
- **AND** it has no host repository, environment-secret, Docker-socket, privileged, or host-network access
- **AND** shutdown targets only the owned T12 project

#### Scenario: Acceptance reporting distinguishes verified and blocked work
- **WHEN** exercise results and progress are recorded
- **THEN** offline checks run in both copies and real captures cover each available live course path
- **AND** unavailable provider/service checks remain explicitly incomplete
- **AND** output/secrets are ignored, no screenshots are committed, and no fabricated captures are presented
