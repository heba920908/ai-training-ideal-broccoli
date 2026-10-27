import json

import pytest
from fastapi.testclient import TestClient
from t10_mcp_advanced.test_server import request


def post(body=None, **headers):
    from t10_mcp_advanced.mcp_server.server import app

    body = body or request().model_dump()
    defaults = {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2026-07-28",
        "Mcp-Method": body.get("method", "tools/list"),
    }
    defaults.update(headers)
    return TestClient(app).post("/mcp", json=body, headers=defaults)


def test_http_sse_result_and_no_session():
    response = post()
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    data = json.loads(response.text.split("data: ", 1)[1])
    assert data["id"] == 7
    assert len(data["result"]["tools"]) == 5
    assert "mcp-session-id" not in response.headers


@pytest.mark.parametrize(
    "body,headers,status,code",
    [
        (request().model_dump(), {"Origin": "http://attacker.invalid"}, 403, -32600),
        (request().model_dump(), {"Accept": "application/json"}, 406, -32600),
        (request(_meta={}).model_dump(), {}, 400, -32602),
        (request().model_dump(), {"Mcp-Method": "wrong"}, 400, -32020),
        (request().model_dump(), {"MCP-Protocol-Version": "old"}, 400, -32020),
        (
            request("tools/call", name="missing").model_dump(),
            {"Mcp-Name": "missing"},
            200,
            -32602,
        ),
        (
            request("tools/call", name="missing").model_dump(),
            {"Mcp-Name": "=?base64?%%%%?="},
            400,
            -32020,
        ),
        (request("unknown").model_dump(), {}, 404, -32601),
        (request("initialize").model_dump(), {}, 400, -32022),
    ],
)
def test_http_boundary_errors(body, headers, status, code):
    response = post(body, **headers)
    assert response.status_code == status
    text = response.text.split("data: ", 1)[-1]
    data = json.loads(text)
    assert data["id"] == 7
    assert data["error"]["code"] == code


def test_http_notification_and_removed_verbs():
    from t10_mcp_advanced.mcp_server.server import app

    body = request("notifications/message").model_dump()
    body.pop("id")
    response = post(body)
    assert response.status_code == 202
    assert response.content == b""
    client = TestClient(app)
    assert client.get("/mcp").status_code == 405
    assert client.delete("/mcp").status_code == 405


@pytest.mark.parametrize(
    "body,code",
    [
        ("{", -32700),
        ({"method": 5, "id": 7}, -32600),
        ({"jsonrpc": "1.0", "method": "tools/list", "id": 7}, -32600),
    ],
)
def test_malformed_http_payloads_are_jsonrpc_not_framework_errors(body, code):
    from t10_mcp_advanced.mcp_server.server import app

    response = TestClient(app).post(
        "/mcp",
        content=body if isinstance(body, str) else json.dumps(body),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == code
