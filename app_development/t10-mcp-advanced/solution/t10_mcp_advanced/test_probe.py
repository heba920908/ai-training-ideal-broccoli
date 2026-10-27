import asyncio
import json

import httpx


def test_protocol_probe_records_real_responses_and_cleans_fixture(
    tmp_path, monkeypatch
):
    from t10_mcp_advanced.mcp_server import server
    from t10_mcp_advanced.probe import run_probes
    from t10_mcp_advanced.test_server import Directory

    directory = Directory()
    for tool in server.mcp_server.tools.values():
        monkeypatch.setattr(tool, "_user_client", directory)

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app)
        ) as client:
            return await run_probes(client, "http://testserver/mcp", tmp_path)

    results = asyncio.run(scenario())
    assert results["passed"] >= 20
    assert not directory.users
    capture = json.loads((tmp_path / "protocol.json").read_text())
    assert any(item["status"] == 405 for item in capture)
    assert any("text/event-stream" in item["content_type"] for item in capture)
    assert any(
        item.get("response", {}).get("error", {}).get("code") == -32022
        for item in capture
    )
