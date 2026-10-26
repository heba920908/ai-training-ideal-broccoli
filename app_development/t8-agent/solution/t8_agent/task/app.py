import argparse

from commons.constants import OPENAI_API_KEY, OPENAI_MODEL
from commons.models.conversation import Conversation
from commons.models.message import Message
from commons.models.role import Role
from commons.user_service.client import UserServiceClient
from t8_agent.task.agents.anthropic import AnthropicBasedAgent
from t8_agent.task.agents.openai import OpenAIBasedAgent
from t8_agent.task.prompts import SYSTEM_PROMPT
from t8_agent.task.tools.users.create_user_tool import CreateUserTool
from t8_agent.task.tools.users.delete_user_tool import DeleteUserTool
from t8_agent.task.tools.users.get_user_by_id_tool import GetUserByIdTool
from t8_agent.task.tools.users.search_users_tool import SearchUsersTool
from t8_agent.task.tools.users.update_user_tool import UpdateUserTool
from t8_agent.task.tools.web_search import WebSearchTool


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="T8 user-management agent over EPAM DIAL")
    parser.add_argument("--provider", choices=["openai", "anthropic"], default="openai",
                        help="openai: DIAL Chat Completions; anthropic: DIAL Anthropic Messages route")
    parser.add_argument("--model", default=OPENAI_MODEL,
                        help="Agent deployment (default: OPENAI_MODEL). Use a Claude deployment for --provider anthropic")
    parser.add_argument("--web-search-model", default=OPENAI_MODEL,
                        help="Responses-API deployment with web_search support (default: OPENAI_MODEL)")
    parser.add_argument("--quiet", action="store_true", help="Do not print request/response payloads")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    user_client = UserServiceClient()
    tools = [
        WebSearchTool(OPENAI_API_KEY, model=args.web_search_model),
        GetUserByIdTool(user_client),
        SearchUsersTool(user_client),
        CreateUserTool(user_client),
        UpdateUserTool(user_client),
        DeleteUserTool(user_client),
    ]
    agent_cls = AnthropicBasedAgent if args.provider == "anthropic" else OpenAIBasedAgent
    agent = agent_cls(model=args.model, api_key=OPENAI_API_KEY, tools=tools, system_prompt=SYSTEM_PROMPT)
    conversation = Conversation()

    print("Type your request, or 'exit' to quit.")
    while True:
        try:
            user_input = input("> ").strip()
        except EOFError:
            break
        if user_input.lower() in {"exit", "quit"}:
            break
        if not user_input:
            continue
        conversation.add_message(Message(role=Role.USER, content=user_input))
        ai_message = agent.get_response(conversation.get_messages(), print_request=not args.quiet)
        conversation.add_message(ai_message)
        print(f"\nAI: {ai_message.content}\n")


if __name__ == "__main__":
    main()
