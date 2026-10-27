import base64
import binascii
import json
from urllib.parse import urlparse

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import ValidationError
from t10_mcp_advanced.mcp_server.models.request import MCPRequest
from t10_mcp_advanced.mcp_server.models.response import ErrorResponse, MCPResponse
from t10_mcp_advanced.mcp_server.ums_mcp_server import (
    PROTOCOL_VERSION_META_KEY,
    UmsMCPServer,
)

MCP_PROTOCOL_VERSION_HEADER = "MCP-Protocol-Version"
MCP_METHOD_HEADER = "Mcp-Method"
MCP_NAME_HEADER = "Mcp-Name"
HEADER_MISMATCH_ERROR_CODE = -32020
ALLOWED_ORIGIN_HOSTS = {"localhost", "127.0.0.1", "::1"}

app = FastAPI(title="MCP Tools Server", version="1.0.0")
mcp_server = UmsMCPServer()


def _validate_origin(origin):
    if origin is None:
        return True
    try:
        parsed = urlparse(origin)
        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname in ALLOWED_ORIGIN_HOSTS
        )
    except ValueError:
        return False


def _validate_accept_header(accept_header):
    accepted = set()
    for item in (accept_header or "").lower().split(","):
        parts = [part.strip() for part in item.split(";")]
        try:
            quality = next(
                (float(part[2:]) for part in parts[1:] if part.startswith("q=")), 1.0
            )
        except ValueError:
            return False
        if quality > 0:
            accepted.add(parts[0])
    return {"application/json", "text/event-stream"} <= accepted


def _decode_header_value(value):
    if value.startswith("=?base64?") and value.endswith("?="):
        return base64.b64decode(value[9:-2], validate=True).decode("utf-8")
    return value


def _validate_request_headers(request, protocol_version, mcp_method, mcp_name):
    version = request.params["_meta"][PROTOCOL_VERSION_META_KEY]
    if protocol_version != version:
        return f"{MCP_PROTOCOL_VERSION_HEADER} header does not match body value '{version}'"
    if mcp_method != request.method:
        return (
            f"{MCP_METHOD_HEADER} header does not match body value '{request.method}'"
        )
    if request.method == "tools/call":
        try:
            decoded = _decode_header_value(mcp_name) if mcp_name else None
        except (ValueError, binascii.Error, UnicodeError):
            return f"{MCP_NAME_HEADER} header is not valid base64 UTF-8"
        if decoded is None or decoded != request.params.get("name"):
            return f"{MCP_NAME_HEADER} header does not match tool name"
    return None


def _json_error_response(status_code, mcp_response):
    payload = mcp_response.model_dump(exclude_none=True)
    payload["id"] = mcp_response.id
    return Response(
        status_code=status_code,
        content=json.dumps(payload),
        media_type="application/json",
    )


async def _create_sse_stream(messages):
    for message in messages:
        yield f"event: message\ndata: {message.model_dump_json(exclude_none=True)}\n\n".encode()


@app.post("/mcp")
async def handle_mcp_request(http_request: Request):
    def error(status, code, message, request_id=None):
        return _json_error_response(
            status,
            MCPResponse(id=request_id, error=ErrorResponse(code=code, message=message)),
        )

    headers = http_request.headers
    try:
        body = await http_request.json()
    except (ValueError, UnicodeError):
        return error(400, -32700, "Parse error")
    request_id = body.get("id") if isinstance(body, dict) else None
    if isinstance(request_id, bool) or not isinstance(
        request_id, (str, int, type(None))
    ):
        request_id = None
    if not _validate_origin(headers.get("origin")):
        return error(403, -32600, "Origin is not allowed", request_id)
    if not _validate_accept_header(headers.get("accept")):
        return error(
            406,
            -32600,
            "Client must accept both application/json and text/event-stream",
            request_id,
        )
    try:
        request = MCPRequest.model_validate(body)
    except ValidationError:
        return error(400, -32600, "Invalid JSON-RPC request", request_id)
    if request.method == "initialize":
        return _json_error_response(400, mcp_server.handle_legacy_initialize(request))
    if invalid := mcp_server.validate_request_meta(request):
        return _json_error_response(400, invalid)
    if mismatch := _validate_request_headers(
        request,
        headers.get("mcp-protocol-version"),
        headers.get("mcp-method"),
        headers.get("mcp-name"),
    ):
        return error(400, HEADER_MISMATCH_ERROR_CODE, mismatch, request.id)
    if request.id is None:
        return Response(status_code=202)
    if request.method == "server/discover":
        response = mcp_server.handle_discover(request)
    elif request.method == "tools/list":
        response = mcp_server.handle_tools_list(request)
    elif request.method == "tools/call":
        response = await mcp_server.handle_tools_call(request)
    else:
        return error(404, -32601, f"Method '{request.method}' not found", request.id)
    return StreamingResponse(
        _create_sse_stream([response]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    uvicorn.run("t10_mcp_advanced.mcp_server.server:app", host="127.0.0.1", port=8006)
