import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

MAX_TOOL_ROUNDS = 10
UMS_MCP_URL = "http://localhost:8005/mcp"
REDIS_URL = "redis://localhost:6379/0"
CONTAINER_COMMAND = "podman"
DDG_MCP_IMAGE = (
    "docker.io/khshanovskyi/ddg-mcp-server"
    "@sha256:83156e29160467e40a28d99001965e347c2bd8a0ba769c21ad8a1814a05ae2a9"
)
APP_HOST = "127.0.0.1"
APP_PORT = 8011
ALLOWED_ORIGINS = [f"http://localhost:{APP_PORT}", f"http://127.0.0.1:{APP_PORT}"]


def load_environment(start: Path | None = None) -> None:
    current = (start or Path.cwd()).resolve()
    for ancestor in (current, *current.parents):
        candidate = ancestor / ".env"
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            break


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required configuration: {name}")
    return value


def _validate_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        valid = (
            parsed.scheme == "https"
            and bool(host)
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.port in (None, 443)
        )
    except ValueError:
        valid, host = False, ""
    if not valid or host == "openai.com" or host.endswith(".openai.com"):
        raise ValueError(
            "OPENAI_BASE_URL must be credential-free HTTPS; public OpenAI is not allowed"
        )
    return value.rstrip("/")


@dataclass(frozen=True)
class ProviderSettings:
    model: str
    base_url: str
    api_key: str = field(repr=False)

    def client_kwargs(self) -> dict:
        return {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "default_headers": {"Api-Key": self.api_key},
            "timeout": 90,
            "max_retries": 1,
        }


def dial_settings() -> ProviderSettings:
    load_environment()
    return ProviderSettings(
        model=_required("OPENAI_MODEL"),
        base_url=_validate_url(_required("OPENAI_BASE_URL")),
        api_key=_required("OPENAI_API_KEY"),
    )
