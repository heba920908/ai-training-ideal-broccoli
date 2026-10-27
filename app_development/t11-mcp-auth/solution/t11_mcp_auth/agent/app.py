import argparse
import asyncio
import json
import sys
from pathlib import Path

from commons.models.message import Message
from commons.models.role import Role
from t11_mcp_auth.agent._agent import AgentMCPAuth
from t11_mcp_auth.agent.mcp_clients.api_key_mcp_client import ApiKeyMCPClient
from t11_mcp_auth.config import dial_base_url, load_environment, redact, required


def OauthHttpMCPClient(*args, **kwargs):
    from t11_mcp_auth.agent.mcp_clients.oauth_mcp_client import OauthHttpMCPClient

    return OauthHttpMCPClient(*args, **kwargs)


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Authenticated T11 user agent")
    parser.add_argument("--auth", choices=("api-key", "oauth"), default="api-key")
    parser.add_argument("--query")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        load_environment()
        provider_key = required("OPENAI_API_KEY")
        model = required("OPENAI_MODEL")
        base_url = dial_base_url()
        client = (
            ApiKeyMCPClient(
                mcp_server_url="http://127.0.0.1:8007/mcp",
                api_key=required("MCP_API_KEY"),
            )
            if args.auth == "api-key"
            else OauthHttpMCPClient(mcp_server_url="http://127.0.0.1:8008/mcp")
        )
        async with client as mcp_client:
            tools = await mcp_client.get_tools()
            agent = AgentMCPAuth(
                api_key=provider_key,
                model=model,
                tools=tools,
                mcp_client=mcp_client,
                base_url=base_url,
            )
            messages = [
                Message(Role.SYSTEM, "You are a helpful user-directory assistant.")
            ]
            try:
                while True:
                    if args.query is not None:
                        query = args.query
                    else:
                        try:
                            query = input("You: ")
                        except EOFError:
                            break
                        if query.strip().lower() in {"exit", "quit"}:
                            break
                        if not query.strip():
                            continue
                    messages.append(Message(Role.USER, query))
                    result = await agent.get_completion(messages)
                    messages.append(result)
                    manager = getattr(mcp_client, "token_manager", None)
                    credentials = (
                        provider_key,
                        getattr(mcp_client, "api_key", ""),
                        *(
                            getattr(manager, name, "")
                            for name in (
                                "access_token",
                                "refresh_token",
                                "code_verifier",
                                "code",
                                "state",
                                "_access_token",
                                "_refresh_token",
                                "_code_verifier",
                                "_code",
                                "_state",
                            )
                        ),
                    )
                    safe_result = redact(result.content, secrets=credentials)
                    print(safe_result)
                    if args.query is not None:
                        if args.output_dir is not None:
                            capture = redact(
                                {
                                    "auth": args.auth,
                                    "query": query,
                                    "model": model,
                                    "result": safe_result,
                                    "messages": [
                                        message.to_dict() for message in messages
                                    ],
                                },
                                secrets=credentials,
                            )
                            args.output_dir.mkdir(parents=True, exist_ok=True)
                            (args.output_dir / f"agent_{args.auth}.json").write_text(
                                json.dumps(capture, indent=2) + "\n", encoding="utf-8"
                            )
                        break
            finally:
                await agent.openai.close()
        return 0
    except Exception:  # noqa: BLE001
        print(
            "Agent failed; check configuration, authentication, and service availability.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130) from None
