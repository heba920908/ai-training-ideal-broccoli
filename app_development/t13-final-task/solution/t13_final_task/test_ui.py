import re
from pathlib import Path

HTML = (Path(__file__).parent / "task" / "index.html").read_text(encoding="utf-8")


def script_tags():
    return re.findall(r"<script\s+src=[^>]+>", HTML)


def test_cdn_scripts_are_pinned_with_integrity():
    tags = script_tags()
    assert len(tags) == 2
    for name in ("marked@", "dompurify@"):
        tag = next(t for t in tags if name in t)
        assert re.search(r"@\d+\.\d+\.\d+/", tag)
        assert 'integrity="sha384-' in tag
        assert 'crossorigin="anonymous"' in tag


def test_markdown_is_always_sanitized():
    raw_calls = re.findall(r"marked\.parse\(", HTML)
    sanitized = re.findall(r"DOMPurify\.sanitize\(marked\.parse\(", HTML)
    assert raw_calls and len(raw_calls) == len(sanitized)


def test_conversation_title_is_escaped():
    assert "${conversation.title}" not in HTML
    assert "${escapeHtml(conversation.title)}" in HTML


def test_same_origin_api_and_no_todos():
    assert "const API_URL = window.location.origin;" in HTML
    assert "TODO" not in HTML


def test_required_api_calls_present():
    for snippet in (
        "`${API_URL}/conversations`",
        "`${API_URL}/conversations/${conversationId}`",
        "method: 'DELETE'",
        "`${API_URL}/conversations/${currentConversationId}/chat`",
        "stream: true",
        "parsed.tool_activity",
        "createToolHistoryDropdown(pendingToolActivity)",
    ):
        assert snippet in HTML
