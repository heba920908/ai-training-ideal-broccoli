import argparse
import asyncio
import copy
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from t10_mcp_advanced.agent.clients.custom_mcp_client import CustomMCPClient


def rpc(method, **params):
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientInfo": {
                    "name": "t10-http-probe",
                    "version": "1.0",
                },
                "io.modelcontextprotocol/clientCapabilities": {},
            },
            **params,
        },
    }


async def run_probes(client, url, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []

    async def exchange(
        label,
        body=None,
        *,
        status=200,
        code=None,
        headers=None,
        verb="POST",
        predicate=None,
    ):
        body = copy.deepcopy(body)
        sent = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if isinstance(body, dict):
            sent["Mcp-Method"] = body["method"]
            sent["MCP-Protocol-Version"] = (
                body.get("params", {})
                .get("_meta", {})
                .get("io.modelcontextprotocol/protocolVersion", "2026-07-28")
            )
            if body["method"] == "tools/call" and "name" in body["params"]:
                sent["Mcp-Name"] = CustomMCPClient._encode_header_value(
                    body["params"]["name"]
                )
        sent.update(headers or {})
        response = await client.request(
            verb,
            url,
            headers=sent,
            **({"content": body} if isinstance(body, str) else {"json": body})
            if verb == "POST"
            else {},
        )
        payload = None
        if response.content:
            text = response.text
            if "text/event-stream" in response.headers.get("content-type", ""):
                text = "\n".join(
                    line[5:].strip()
                    for line in text.splitlines()
                    if line.startswith("data:")
                )
            payload = json.loads(text)
        passed = response.status_code == status
        if code is not None:
            passed = passed and payload.get("error", {}).get("code") == code
        if (
            isinstance(body, dict)
            and body.get("id") is not None
            and payload
            and "jsonrpc" in payload
        ):
            passed = passed and payload.get("id") == body["id"]
        if predicate:
            passed = passed and predicate(payload)
        record = {
            "label": label,
            "method": verb,
            "url": url,
            "headers": sent,
            "request": body,
            "status": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "raw_response": response.text,
            "response": payload,
            "passed": passed,
        }
        records.append(record)
        print(
            f"\n{label}: {'PASS' if passed else 'FAIL'} HTTP {response.status_code} {record['content_type']}"
        )
        print(json.dumps({"headers": sent, "request": body}, indent=2))
        print(response.text)
        return payload

    fixture_id = None
    fixture = {
        "name": "T10Probe",
        "surname": uuid.uuid4().hex[:12],
        "email": f"t10-{uuid.uuid4().hex[:12]}@example.invalid",
        "about_me": "Synthetic owned T10 HTTP fixture",
    }
    try:
        await exchange(
            "discover",
            rpc("server/discover"),
            predicate=lambda data: "2026-07-28" in data["result"]["supportedVersions"],
        )
        await exchange(
            "list_tools",
            rpc("tools/list"),
            predicate=lambda data: len(data["result"]["tools"]) == 5,
        )
        await exchange(
            "bad_origin",
            rpc("tools/list"),
            status=403,
            code=-32600,
            headers={"Origin": "http://attacker.invalid"},
        )
        await exchange(
            "bad_accept",
            rpc("tools/list"),
            status=406,
            code=-32600,
            headers={"Accept": "application/json"},
        )
        await exchange(
            "disabled_sse_accept",
            rpc("tools/list"),
            status=406,
            code=-32600,
            headers={"Accept": "application/json, text/event-stream;q=0"},
        )
        await exchange(
            "missing_meta", rpc("tools/list", _meta={}), status=400, code=-32602
        )
        old = rpc("tools/list")
        old["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"] = "2025-11-25"
        await exchange("unsupported_version", old, status=400, code=-32022)
        await exchange(
            "method_mismatch",
            rpc("tools/list"),
            status=400,
            code=-32020,
            headers={"Mcp-Method": "wrong"},
        )
        await exchange(
            "version_mismatch",
            rpc("tools/list"),
            status=400,
            code=-32020,
            headers={"MCP-Protocol-Version": "wrong"},
        )
        await exchange(
            "tool_name_mismatch",
            rpc("tools/call", name="get_user_by_id", arguments={"id": 0}),
            status=400,
            code=-32020,
            headers={"Mcp-Name": "wrong"},
        )
        await exchange(
            "bad_base64",
            rpc("tools/call", name="missing"),
            status=400,
            code=-32020,
            headers={"Mcp-Name": "=?base64?%%%%?="},
        )
        await exchange("unknown_tool", rpc("tools/call", name="missing"), code=-32602)
        await exchange(
            "encoded_unknown_tool", rpc("tools/call", name="caf\u00e9"), code=-32602
        )
        await exchange("unknown_method", rpc("missing"), status=404, code=-32601)
        await exchange(
            "legacy_initialize",
            rpc("initialize", protocolVersion="2025-11-25"),
            status=400,
            code=-32022,
        )
        await exchange("parse_error", "{", status=400, code=-32700)
        for verb in ("GET", "DELETE"):
            await exchange(f"removed_{verb.lower()}", verb=verb, status=405)
        notification = rpc("notifications/message")
        del notification["id"]
        await exchange("notification", notification, status=202)
        await exchange(
            "tool_validation_error",
            rpc("tools/call", name="add_user", arguments={}),
            predicate=lambda data: (
                data["result"]["isError"] is True and "error" not in data
            ),
        )
        created = await exchange(
            "create_fixture",
            rpc("tools/call", name="add_user", arguments=fixture),
            predicate=lambda data: data["result"]["isError"] is False,
        )
        text = created["result"]["content"][0]["text"]
        fixture_id = json.loads(text[text.index("{") :])["id"]
        await exchange(
            "get_fixture",
            rpc("tools/call", name="get_user_by_id", arguments={"id": fixture_id}),
            predicate=lambda data: (
                fixture["email"] in data["result"]["content"][0]["text"]
            ),
        )
        await exchange(
            "search_fixture",
            rpc(
                "tools/call", name="search_users", arguments={"email": fixture["email"]}
            ),
            predicate=lambda data: (
                fixture["email"] in data["result"]["content"][0]["text"]
            ),
        )
        await exchange(
            "update_fixture",
            rpc(
                "tools/call",
                name="update_user",
                arguments={"id": fixture_id, "new_info": {"company": "T10 verified"}},
            ),
            predicate=lambda data: (
                "T10 verified" in data["result"]["content"][0]["text"]
            ),
        )
    finally:
        try:
            if fixture_id is not None:
                await exchange(
                    "delete_fixture",
                    rpc(
                        "tools/call", name="delete_users", arguments={"id": fixture_id}
                    ),
                    predicate=lambda data: data["result"]["isError"] is False,
                )
                await exchange(
                    "get_deleted_fixture",
                    rpc(
                        "tools/call",
                        name="get_user_by_id",
                        arguments={"id": fixture_id},
                    ),
                    predicate=lambda data: data["result"]["isError"] is True,
                )
        finally:
            (output_dir / "protocol.json").write_text(
                json.dumps(records, indent=2) + "\n"
            )
            summary = {
                "timestamp": datetime.now(UTC).isoformat(),
                "total": len(records),
                "passed": sum(item["passed"] for item in records),
                "failed": [item["label"] for item in records if not item["passed"]],
            }
            (output_dir / "protocol_summary.json").write_text(
                json.dumps(summary, indent=2) + "\n"
            )
    if summary["failed"]:
        raise RuntimeError(f"Failed probes: {summary['failed']}")
    print(json.dumps(summary, indent=2))
    return summary


async def main():
    parser = argparse.ArgumentParser(description="Postman-equivalent real HTTP probes")
    parser.add_argument("--url", default="http://localhost:8006/mcp")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    args = parser.parse_args()
    async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
        await run_probes(client, args.url, args.output_dir)


if __name__ == "__main__":
    asyncio.run(main())
