from typing import Any

import requests
from commons.constants import OPENAI_RESPONSES_ENDPOINT, OPENAI_TERRA_MODEL
from t8_agent.task.tools.base import BaseTool


class WebSearchTool(BaseTool):

    def __init__(self, open_ai_api_key: str, model: str = OPENAI_TERRA_MODEL):
        self.__api_key = f"Bearer {open_ai_api_key}"
        self.__endpoint = OPENAI_RESPONSES_ENDPOINT
        self.__model = model

    @property
    def name(self) -> str:
        return "web_search_tool"

    @property
    def description(self) -> str:
        return "Searches the web for current, public information and returns a short summary with sources."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "The search query or question to search for on the web",
                },
            },
            "required": ["request"],
        }

    def execute(self, arguments: dict[str, Any]) -> str:
        headers = {"Authorization": self.__api_key, "Content-Type": "application/json"}
        request_data = {
            "model": self.__model,
            "input": arguments["request"],
            "tools": [{"type": "web_search"}],
        }
        try:
            response = requests.post(self.__endpoint, headers=headers, json=request_data, timeout=180)
        except requests.RequestException as e:
            return f"Error: {type(e).__name__}"
        if response.status_code != 200:
            return f"Error: {response.status_code} {response.text}"
        # Raw REST has no SDK `output_text` shortcut: join the message output_text blocks
        texts = [
            block.get("text", "")
            for item in response.json().get("output", [])
            if item.get("type") == "message"
            for block in item.get("content", [])
            if block.get("type") == "output_text"
        ]
        return "\n".join(texts) or "Error: web search returned no text"
