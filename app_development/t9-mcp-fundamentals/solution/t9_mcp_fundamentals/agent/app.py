import argparse
import asyncio
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from commons.models.message import Message
from commons.models.role import Role
from dotenv import find_dotenv, load_dotenv
from t9_mcp_fundamentals.agent.agent import AgentMCPFundamentals
from t9_mcp_fundamentals.agent.mcp_clients.http import HttpMCPClient
from t9_mcp_fundamentals.agent.mcp_clients.stdio import StdioMCPClient
from t9_mcp_fundamentals.agent.prompts import SYSTEM_PROMPT

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STDIO_SERVER_PATH = PROJECT_ROOT / "t9_mcp_fundamentals/mcp_server/stdio_server.py"


async def main(argv=None):
    load_dotenv(find_dotenv(usecwd=True))
    parser = argparse.ArgumentParser(
        description="Users Management Agent with MCP tools"
    )
    parser.add_argument(
        "--transport", choices=["http", "stdio", "container"], default="http"
    )
    parser.add_argument(
        "--server-url",
        action="append",
        help="HTTP MCP URL; repeat for multiple servers",
    )
    parser.add_argument("--with-web-search", action="store_true")
    parser.add_argument("--stdio-image", default="docker.io/mcp/duckduckgo:latest")
    parser.add_argument("--container-runtime", default="podman")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", ""))
    parser.add_argument("--discover-only", action="store_true")
    parser.add_argument(
        "--prompt",
        help="Fetch a named server prompt (display only, not a system override)",
    )
    parser.add_argument(
        "--resource", help="Fetch a resource URI and display its encoded size"
    )
    options = parser.parse_args(argv)
    if options.server_url and options.transport != "http":
        parser.error("--server-url requires --transport http")
    if not options.discover_only and not all(
        os.getenv(name) for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL")
    ):
        parser.error("Set OPENAI_BASE_URL and OPENAI_API_KEY in the root .env")
    if not options.discover_only and not options.model:
        parser.error("Set OPENAI_MODEL or pass --model")

    if options.transport == "http":
        urls = options.server_url or ["http://127.0.0.1:8005/mcp"]
        if options.with_web_search:
            urls = list(dict.fromkeys([*urls, "http://127.0.0.1:8010/mcp"]))
        connections = [HttpMCPClient(mcp_server_url=url) for url in urls]
    elif options.transport == "stdio":
        connections = [
            StdioMCPClient(
                command=sys.executable,
                args=[str(STDIO_SERVER_PATH)],
                env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
            )
        ]
    else:
        connections = [
            StdioMCPClient(
                docker_image=options.stdio_image,
                container_runtime=options.container_runtime,
            )
        ]
    if options.with_web_search and options.transport == "stdio":
        connections.append(
            StdioMCPClient(
                docker_image=options.stdio_image,
                container_runtime=options.container_runtime,
            )
        )

    async with AsyncExitStack() as stack:
        tools = []
        tool_clients = {}
        for connection in connections:
            client = await stack.enter_async_context(connection)
            resources = await client.get_resources()
            prompts = await client.get_prompts()
            server_tools = await client.get_tools()
            print("Available resources:", [str(resource.uri) for resource in resources])
            print("Available prompts:", [prompt.name for prompt in prompts])
            print(
                "Available tools:", [tool["function"]["name"] for tool in server_tools]
            )
            if options.prompt and any(
                prompt.name == options.prompt for prompt in prompts
            ):
                print(await client.get_prompt(options.prompt))
            if options.resource and any(
                str(resource.uri) == options.resource for resource in resources
            ):
                print(
                    "Resource encoded size:",
                    len(await client.get_resource(options.resource)),
                )
            for tool in server_tools:
                name = tool["function"]["name"]
                if name in tool_clients:
                    raise ValueError(f"Duplicate tool name across MCP servers: {name}")
                tools.append(tool)
                tool_clients[name] = client
        if options.discover_only:
            return
        agent = AgentMCPFundamentals(
            os.environ["OPENAI_API_KEY"],
            options.model,
            tools,
            connections[0],
            base_url=os.environ["OPENAI_BASE_URL"],
            tool_clients=tool_clients,
        )
        stack.push_async_callback(agent.openai.close)
        messages = [Message(role=Role.SYSTEM, content=SYSTEM_PROMPT)]
        while True:
            try:
                user_input = (await asyncio.to_thread(input, "\n> ")).strip()
            except EOFError:
                break
            if user_input.lower() in {"exit", "quit"}:
                break
            if not user_input:
                continue
            messages.append(Message(role=Role.USER, content=user_input))
            response = await agent.get_response(messages)
            messages.append(response)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
