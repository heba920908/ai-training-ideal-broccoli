import base64
import json
import uuid
from typing import Any

import aiohttp
from t10_mcp_advanced.agent.clients.results import tool_text

PROTOCOL_VERSION = "2026-07-28"
CLIENT_INFO = {"name": "my-custom-mcp-client", "version": "1.0.0"}


class CustomMCPClient:
    """Pure Python MCP client without external MCP libraries (stateless MCP, protocol version 2026-07-28)"""

    def __init__(self, mcp_server_url: str) -> None:
        self.server_url = mcp_server_url
        self.http_session: aiohttp.ClientSession | None = None

    @classmethod
    async def create(cls, mcp_server_url: str) -> "CustomMCPClient":
        """Async factory method to create and connect CustomMCPClient"""
        instance = cls(mcp_server_url)
        await instance.connect()
        return instance

    @staticmethod
    def _encode_header_value(value: str) -> str:
        """Header values must be plain visible ASCII, otherwise they are sent as `=?base64?{value}?=`"""
        is_plain_ascii = (
            value.isascii() and value.isprintable() and value == value.strip()
        )
        looks_like_base64_sentinel = value.startswith("=?base64?") and value.endswith(
            "?="
        )
        if is_plain_ascii and not looks_like_base64_sentinel:
            return value
        return f"=?base64?{base64.b64encode(value.encode('utf-8')).decode('ascii')}?="

    async def _send_request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if self.http_session is None:
            raise RuntimeError("MCP client not connected. Call connect() first.")
        params = dict(params or {})
        params["_meta"] = {
            "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
            "io.modelcontextprotocol/clientInfo": CLIENT_INFO,
            "io.modelcontextprotocol/clientCapabilities": {},
        }
        request_id = str(uuid.uuid4())
        body = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
            "Mcp-Method": method,
        }
        if method == "tools/call":
            headers["Mcp-Name"] = self._encode_header_value(params["name"])
        async with self.http_session.post(
            self.server_url, json=body, headers=headers
        ) as response:
            content_type = response.headers.get("content-type", "").lower()
            if "text/event-stream" in content_type:
                data = await self._parse_sse_response_streaming(response)
            elif "application/json" in content_type:
                data = await response.json()
            else:
                raise RuntimeError(f"Unexpected MCP response (HTTP {response.status})")
            if (
                not isinstance(data, dict)
                or data.get("jsonrpc") != "2.0"
                or data.get("id") != request_id
            ):
                raise RuntimeError("MCP response ID or JSON-RPC version mismatch")
            if "error" in data:
                error = data["error"]
                if (
                    not isinstance(error, dict)
                    or not isinstance(error.get("code"), int)
                    or not isinstance(error.get("message"), str)
                ):
                    raise RuntimeError("Invalid MCP error envelope")
                raise RuntimeError(f"MCP Error {error['code']}: {error['message']}")
            response.raise_for_status()
            if not isinstance(data.get("result"), dict):
                raise RuntimeError("Invalid MCP result envelope")
            result_type = data["result"].get("resultType")
            if result_type != "complete":
                raise RuntimeError(f"Unsupported resultType: {result_type}")
            return data

    async def _parse_sse_response_streaming(
        self, response: aiohttp.ClientResponse
    ) -> dict[str, Any]:
        lines = []
        async for line in response.content:
            text = line.decode("utf-8").rstrip("\r\n")
            if text.startswith("data:"):
                lines.append(text[5:].lstrip(" "))
            elif not text and lines:
                try:
                    message = json.loads("\n".join(lines))
                except json.JSONDecodeError:
                    lines.clear()
                    continue
                lines.clear()
                if isinstance(message, dict) and "id" in message:
                    return message
        raise RuntimeError("No JSON-RPC response found in SSE stream")

    async def connect(self) -> None:
        if self.http_session is not None:
            raise RuntimeError("Client already connected")
        self.http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60, connect=10),
            connector=aiohttp.TCPConnector(limit=100, limit_per_host=10),
        )
        try:
            discovery = (await self._send_request("server/discover"))["result"]
            if PROTOCOL_VERSION not in discovery.get("supportedVersions", []):
                raise RuntimeError(f"Server does not support {PROTOCOL_VERSION}")
            print(
                f"Custom client connected to {self.server_url}: {json.dumps(discovery)}"
            )
        except BaseException:
            await self.close()
            raise

    async def close(self) -> None:
        """Close HTTP session"""
        if self.http_session:
            await self.http_session.close()
            self.http_session = None

    async def get_tools(self) -> list[dict[str, Any]]:
        tools = []
        cursor = None
        while True:
            result = (
                await self._send_request(
                    "tools/list", {"cursor": cursor} if cursor else {}
                )
            )["result"]
            tools.extend(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool["inputSchema"],
                    },
                }
                for tool in result["tools"]
            )
            next_cursor = result.get("nextCursor")
            if not next_cursor:
                return tools
            if next_cursor == cursor:
                raise RuntimeError("Repeated tools/list cursor")
            cursor = next_cursor

    async def call_tool(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        print(f"Calling {tool_name} on {self.server_url}: {json.dumps(tool_args)}")
        result = (
            await self._send_request(
                "tools/call", {"name": tool_name, "arguments": tool_args}
            )
        )["result"]
        text = tool_text(result)
        print(text)
        return text
