# T11 Source Task

Course: EPAM, AI Applications Development: From API to Agents.

Source revision: `2c55dc448f2c80c35962f92a17d5f29d333222b6`.

Original task:
<https://github.com/epam/ai-applications-development-from-api-to-agents/blob/2c55dc448f2c80c35962f92a17d5f29d333222b6/t11_mcp_auth/README.md>.

Complete the FastMCP API-key and Keycloak OAuth servers, authenticated SDK
clients, browser PKCE token lifecycle, and a user-directory agent. Preserve
`get_user_by_id`, `delete_user`, `search_user`, `add_user`, and `update_user`.
The original task's screenshots and insecure seeded credentials are not bundled.
Use only environment-provided credentials and the credential-free realm template.

This delivery uses stateless MCP `2026-07-28`, explicit JWT audience checking,
S256 PKCE, proactive serialized refresh, and configured EPAM DIAL. The parent
task card records actual verification and the remaining browser-login blockers.