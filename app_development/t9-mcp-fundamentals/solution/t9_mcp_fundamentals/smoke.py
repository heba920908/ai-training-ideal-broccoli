"""Exercise real MCP transports without requiring or exposing LLM credentials."""

import argparse
import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from t9_mcp_fundamentals.agent.mcp_clients.http import HttpMCPClient
from t9_mcp_fundamentals.agent.mcp_clients.stdio import StdioMCPClient


async def check_users(client, crud):
    tools = await client.get_tools()
    names = {tool["function"]["name"] for tool in tools}
    assert names == {
        "get_user_by_id",
        "search_user",
        "add_user",
        "update_user",
        "delete_user",
    }
    resources = await client.get_resources()
    assert str(resources[0].uri) == "users-management://flow-diagram"
    image = base64.b64decode(
        await client.get_resource("users-management://flow-diagram")
    )
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    prompts = await client.get_prompts()
    assert {prompt.name for prompt in prompts} == {
        "search_guidance",
        "creation_guidance",
    }
    assert "Search" in await client.get_prompt("search_guidance")
    assert "Required" in await client.get_prompt("creation_guidance")
    summary = {"tools": len(tools), "prompts": len(prompts), "png_resource": "PASS"}
    if crud:
        email = f"mcp-training-{uuid4().hex}@example.com"
        created = await client.call_tool(
            "add_user",
            {
                "user": {
                    "name": "Training",
                    "surname": "Example",
                    "email": email,
                    "about_me": "Synthetic MCP transport verification profile.",
                }
            },
        )
        user_id = json.loads(created.removeprefix("User successfully added: "))["id"]
        try:
            assert email in await client.call_tool(
                "get_user_by_id", {"user_id": user_id}
            )
            assert email in await client.call_tool(
                "search_user", {"request": {"email": email}}
            )
            await client.call_tool(
                "update_user", {"user_id": user_id, "user": {"company": "MCP Training"}}
            )
            assert "MCP Training" in await client.call_tool(
                "get_user_by_id", {"user_id": user_id}
            )
        finally:
            await client.call_tool("delete_user", {"user_id": user_id})
        try:
            await client.call_tool("get_user_by_id", {"user_id": user_id})
        except RuntimeError as error:
            assert "404" in str(error)
        else:
            raise AssertionError("Deleted profile still exists")
        summary["create_read_search_update_delete"] = "PASS"
    return summary


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--transport", choices=["http", "stdio", "container"], default="stdio"
    )
    parser.add_argument("--server-url", default="http://127.0.0.1:8005/mcp")
    parser.add_argument(
        "--crud", action="store_true", help="Create and remove one synthetic profile"
    )
    parser.add_argument(
        "--web-url", help="Also discover and call the HTTP web-search server"
    )
    parser.add_argument("--container-image", default="docker.io/mcp/duckduckgo:latest")
    options = parser.parse_args()
    if options.transport == "http":
        connection = HttpMCPClient(options.server_url)
    elif options.transport == "stdio":
        root = Path(__file__).resolve().parents[1]
        connection = StdioMCPClient(
            command=sys.executable,
            args=[str(root / "t9_mcp_fundamentals/mcp_server/stdio_server.py")],
            env={**os.environ, "PYTHONPATH": str(root)},
        )
    else:
        connection = StdioMCPClient(docker_image=options.container_image)
    async with connection as client:
        if options.transport == "container":
            tools = await client.get_tools()
            assert tools
            summary = {
                "transport": "container",
                "tools": [tool["function"]["name"] for tool in tools],
            }
        else:
            summary = {
                "transport": options.transport,
                **await check_users(client, options.crud),
            }
    if options.web_url:
        async with HttpMCPClient(options.web_url) as client:
            tools = await client.get_tools()
            names = {tool["function"]["name"] for tool in tools}
            assert "search" in names
            result = await client.call_tool(
                "search",
                {
                    "query": "Python programming language official website",
                    "max_results": 1,
                },
            )
            assert result
            summary["web_search"] = (
                "PASS (nonempty response; inspect for upstream limitations)"
            )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
