## 1. Server and User Tools

- [x] 1.1 Add failing tests for discovery, five tool schemas, metadata validation, and tool-error semantics; verify they fail for the missing implementations.
- [x] 1.2 Complete tool registration, discovery, listing, metadata validation, and user-tool TODOs; verify the focused server/tool tests pass and record the implemented behavior in the task card draft.
- [x] 1.3 Add failing HTTP boundary tests, complete header/media/origin validation and SSE routing, and fix executable imports; verify JSON-RPC codes, HTTP statuses, notification behavior, and GET/DELETE rejection using the focused HTTP tests.

## 2. Clients and DIAL Agent

- [x] 2.1 Add failing custom-client tests and implement request metadata/headers, discovery, JSON/SSE handling, response correlation, schema conversion, tool calls, and cleanup; verify client tests pass.
- [x] 2.2 Adapt the SDK wrapper only as required for compatible discovery, tool content, errors, and cleanup; verify both clients against the same local server contract and document client-mode selection.
- [x] 2.3 Add failing configuration/routing/agent tests and implement the agent entry point, model-agnostic DIAL configuration, bounded tool rounds, error recovery, and single-query/interactive modes; verify tests and document the provider boundary and round limit.

## 3. Real Experiments and Standalone Packaging

- [x] 3.1 Prepare isolated or verified compatible local services and a reproducible HTTP probe using Python or curl with tee; verify discovery, CRUD, protocol errors, and actual JSON/SSE responses are captured in solution/output with owned-fixture cleanup.
- [x] 3.2 Run the specified Arkadiy Dobkin query using both SDK and custom clients against real DIAL and MCP services; capture tool traces and final responses, document the observed existing-user or web-search/create branch, and record any blockers honestly.
- [x] 3.3 Copy final T10 code, needed shared modules, dependencies, compose configuration, tests, and course references into app_development/t10-mcp-advanced/solution; verify imports and offline tests without relying on the workspace clone.
- [x] 3.4 Run the full T10 offline suite and static checks in the fork and standalone solution; capture actual verification output and a machine-readable experiment summary, and scan copied artifacts and captures for credentials.
- [x] 3.5 Finish the T7-style exercise README and root progress row with exact setup, probe, client-mode, output, and cleanup commands; verify durable local links and ensure reported results match captured executions.

## 4. OpenSpec Completion

- [x] 4.1 Review the implementation and evidence against every acceptance scenario; run openspec validate t10-mcp-advanced --strict and mark only verified tasks complete.
- [ ] 4.2 Once delivery is complete, sync/archive the change, move its archive to workspace/openspec/archive as required, and validate the resulting living specification; leave all work uncommitted unless explicitly approved.