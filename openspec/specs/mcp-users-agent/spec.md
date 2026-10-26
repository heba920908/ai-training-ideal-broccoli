# mcp-users-agent Specification

## Purpose
Provide a standalone training implementation of user-management MCP tools,
resources and prompts, consumed by a bounded EPAM DIAL agent over HTTP or STDIO,
with Podman-compatible services and reproducible verification evidence.

## Requirements

### Requirement: Expose user-management MCP capabilities
The server SHALL expose get_user_by_id, search_user, add_user, update_user and
delete_user tools using the shared user-service models. It SHALL expose a PNG
resource at users-management://flow-diagram and search_guidance and
creation_guidance prompts.

#### Scenario: Discover and retrieve capabilities
- **WHEN** a connected client lists server capabilities and retrieves the resource and prompts
- **THEN** it receives five tools, two prompts and valid PNG bytes with image/png MIME type

### Requirement: Support HTTP and STDIO lifecycles
Clients SHALL open and close SDK connections through async context managers.
STDIO SHALL support the current Python executable and Podman containers using
run --rm -i without a pseudo-TTY.

#### Scenario: Perform CRUD over either transport
- **WHEN** the smoke command runs against the local mock service using HTTP or STDIO
- **THEN** it can create, read, search, update and delete its own synthetic profile
- **AND** the deleted profile subsequently returns a 404 error

### Requirement: Adapt MCP results for a bounded DIAL agent
The agent SHALL use OPENAI_BASE_URL, OPENAI_MODEL and OPENAI_API_KEY without
hard-coded model names or model-specific request parameters. Clients SHALL
preserve paginated schemas and all tool-result content blocks. The agent SHALL
return tool errors to the model with matching tool-call IDs and stop after ten
tool rounds.

#### Scenario: Recover from invalid tool arguments
- **WHEN** the model emits malformed JSON, a non-object argument or an unknown tool
- **THEN** the conversation receives a corresponding tool error rather than crashing

### Requirement: Route tools to their owning server
The CLI SHALL support multiple HTTP MCP servers and optional local users STDIO
plus Podman web-search STDIO. It SHALL reject duplicate tool names.

#### Scenario: Combine users and web search
- **WHEN** two servers advertise distinct tools
- **THEN** each call is dispatched to the client that advertised its tool

### Requirement: Provide a reproducible standalone artifact
The exercise SHALL include the necessary shared Python modules, pinned runtime
dependencies, Podman Compose prerequisites, run instructions, offline tests and
sanitized verification outputs. Discovery SHALL work without LLM credentials.

#### Scenario: Run without the course clone
- **WHEN** the learner runs commands from the packaged solution directory
- **THEN** imports resolve without the ephemeral course clone
- **AND** no credential values or raw user records are required in tracked artifacts
