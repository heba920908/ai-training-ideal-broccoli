import pytest
from t13_final_task.task.agent import config


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("OPENAI_BASE_URL", "OPENAI_MODEL", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "load_environment", lambda start=None: None)


def set_valid(monkeypatch, url="https://ai-proxy.lab.epam.com/openai/deployments/any-model"):
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    monkeypatch.setenv("OPENAI_MODEL", "deepseek-any")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def test_settings_use_configured_values_and_api_key_header(monkeypatch):
    set_valid(monkeypatch)
    settings = config.dial_settings()

    assert settings.model == "deepseek-any"
    kwargs = settings.client_kwargs()
    assert kwargs["base_url"] == "https://ai-proxy.lab.epam.com/openai/deployments/any-model"
    assert kwargs["default_headers"] == {"Api-Key": "test-key"}
    assert kwargs["api_key"] == "test-key"
    assert "test-key" not in repr(settings)


@pytest.mark.parametrize("missing", ["OPENAI_BASE_URL", "OPENAI_MODEL", "OPENAI_API_KEY"])
def test_missing_variable_is_named(monkeypatch, missing):
    set_valid(monkeypatch)
    monkeypatch.delenv(missing)
    with pytest.raises(ValueError, match=missing):
        config.dial_settings()


@pytest.mark.parametrize(
    "url",
    [
        "https://user:pass@ai-proxy.lab.epam.com/openai",
        "https://api.openai.com/v1",
        "http://ai-proxy.lab.epam.com/openai",
        "https://ai-proxy.lab.epam.com/openai?key=1",
    ],
)
def test_unsafe_urls_rejected_without_echoing_value(monkeypatch, url):
    set_valid(monkeypatch, url)
    with pytest.raises(ValueError) as error:
        config.dial_settings()
    assert url not in str(error.value)


def test_ancestor_env_loaded_without_overriding_exports(tmp_path, monkeypatch):
    monkeypatch.undo()
    for name in ("OPENAI_BASE_URL", "OPENAI_MODEL", "OPENAI_API_KEY"):
        # set then delete so monkeypatch restores whatever dotenv writes
        monkeypatch.setenv(name, "placeholder")
        monkeypatch.delenv(name)
    (tmp_path / ".env").write_text("OPENAI_MODEL=from-file\nOPENAI_API_KEY=file-key\n")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.setenv("OPENAI_MODEL", "exported")

    config.load_environment(nested)

    import os

    assert os.environ["OPENAI_MODEL"] == "exported"
    assert os.environ["OPENAI_API_KEY"] == "file-key"


def test_local_endpoints_are_loopback_and_runtime_is_podman():
    assert config.UMS_MCP_URL == "http://localhost:8005/mcp"
    assert config.REDIS_URL.startswith("redis://localhost:6379")
    assert config.CONTAINER_COMMAND == "podman"
    assert "@sha256:" in config.DDG_MCP_IMAGE
    assert config.APP_HOST == "127.0.0.1"
    assert config.APP_PORT == 8011
    assert config.MAX_TOOL_ROUNDS == 10
