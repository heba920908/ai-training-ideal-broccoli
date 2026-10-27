## Why

The T11 MCP authentication exercise has incomplete API-key middleware, OAuth/JWT middleware,
PKCE token management, authenticated clients, and server/agent entry points. Completing the
TODOs literally would retain embedded credentials, a T9 import dependency, model-specific
generation settings, and an unbounded recursive tool loop. The exercise needs a reviewed plan
that meets the course goals while following this repository's T10 delivery conventions.

## What Changes

- Complete both authentication modes around the existing FastMCP user tools and SDK clients.
- Verify stateless discovery, tool execution, and mutable HTTP authentication headers against
  a pinned, compatible FastMCP/MCP dependency set before implementing the full auth flow.
- Load credentials from environment configuration; keep API keys, passwords, tokens, callback
  codes, and PKCE verifiers out of tracked files and captured output.
- Validate JWT signature, issuer, expiry, explicit MCP audience, and required realm role using
  cached JWKS. Configure an audience mapper in the local Keycloak realm rather than disabling
  audience verification as the starter suggests.
- Complete browser Authorization Code + S256 PKCE, state verification, bounded callback handling,
  proactive refresh, and HTTP-header replacement without reconnecting the MCP client.
- Adapt the agent to model-agnostic EPAM DIAL and a bounded tool loop, without a T9 dependency.
- Deliver isolated local infrastructure, offline tests, redacted real probes and agent captures,
  and a standalone T10-style task card and solution bundle.

## Capabilities

### New Capabilities

- `authenticated-mcp-users-agent`: API-key and Keycloak OAuth/PKCE protection for stateless MCP
  user tools, authenticated SDK clients, a DIAL agent, and reproducible acceptance evidence.

### Modified Capabilities

None. T11 references `stateless-mcp-users-agent` for transport and delivery conventions but
does not modify T10 or adopt its raw-server implementation or different tool names.

## Impact

- Implementation: `t11_mcp_auth/` in the ephemeral course fork, including auth middleware,
  SDK wrappers, PKCE helpers, agent, dependency pins, compose, and Keycloak configuration.
- Delivery: `app_development/t11-mcp-auth/README.md` and `solution/`, the root progress table,
  and placeholder-only additions to `.env.example`.
- Runtime: local UMS, Keycloak, API-key MCP, OAuth MCP, and browser callback on ports
  8041, 8089, 8007, 8008, and 9999 respectively; real agent runs contact configured EPAM DIAL.
- Security: local training scope, explicit audience checking, no committed credentials, and
  synthetic owned fixtures only. Full MCP OAuth authorization discovery is not claimed.
- Approval: planning artifacts are pending user review. No implementation or live experiments
  are authorized until the user explicitly approves this plan. No commit or push is authorized.