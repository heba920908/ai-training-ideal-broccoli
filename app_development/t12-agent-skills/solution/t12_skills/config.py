import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

MAX_ROUNDS = 10
MCP_TIMEOUT = 60


def load_environment(start: Path | None = None) -> None:
    current = (start or Path.cwd()).resolve()
    for ancestor in (current, *current.parents):
        candidate = ancestor / ".env"
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            break


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required configuration: {name}")
    return value


def validate_url(value: str, *, dial: bool = False) -> str:
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        valid = (
            parsed.scheme == "https"
            and host
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.port in (None, 443)
        )
    except ValueError:
        valid = False
        host = ""
    if not valid or (dial and (host == "openai.com" or host.endswith(".openai.com"))):
        raise ValueError("Provider URL must be credential-free HTTPS; public OpenAI is not allowed")
    return value.rstrip("/")


@dataclass(frozen=True)
class ProviderSettings:
    model: str
    api_key: str = field(repr=False)
    base_url: str | None = None
    dial: bool = False

    def client_kwargs(self) -> dict:
        options = {"api_key": self.api_key, "timeout": 90, "max_retries": 1}
        if self.base_url:
            options["base_url"] = self.base_url
        if self.dial:
            options["default_headers"] = {"Api-Key": self.api_key}
        return options


def dial_settings() -> ProviderSettings:
    load_environment()
    return ProviderSettings(
        model=required("OPENAI_MODEL"),
        api_key=required("OPENAI_API_KEY"),
        base_url=validate_url(required("OPENAI_BASE_URL"), dial=True),
        dial=True,
    )


def anthropic_settings() -> ProviderSettings:
    load_environment()
    endpoint = os.getenv("ANTHROPIC_BASE_URL", "").strip()
    return ProviderSettings(
        model=required("ANTHROPIC_MODEL"),
        api_key=required("ANTHROPIC_API_KEY"),
        base_url=validate_url(endpoint) if endpoint else None,
    )


def token_limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 8192:
        raise ValueError("max_tokens must be an integer between 1 and 8192")
    return value
