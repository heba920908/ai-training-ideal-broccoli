import json


def tool_text(result):
    parts = [
        item.get("text", json.dumps(item, ensure_ascii=True))
        for item in result.get("content", [])
    ]
    text = "\n".join(parts)
    if result.get("isError", False):
        return f"Tool error: {text}"
    return text or json.dumps(result.get("structuredContent", {}))
