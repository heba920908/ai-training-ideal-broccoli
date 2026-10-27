import importlib
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from t11_mcp_auth.mcp_server.auth.api_key_auth import APIKeyMiddleware


def protected_app(middleware, **options):
    calls = []

    async def dispatch(request):
        calls.append(request.url.path)
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/{path:path}", dispatch, methods=["GET", "POST"])])
    app.add_middleware(middleware, **options)
    return app, calls


@pytest.mark.asyncio
async def test_api_key_denies_before_dispatch_and_permits_every_path(monkeypatch):
    key = secrets.token_urlsafe(32)
    monkeypatch.setenv("MCP_API_KEY", key)
    app, calls = protected_app(APIKeyMiddleware)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for supplied in (None, "", secrets.token_urlsafe(32)):
            headers = {} if supplied is None else {"X-API-Key": supplied}
            response = await client.post("/mcp", headers=headers)
            assert response.status_code == 401
            assert key not in response.text
        assert calls == []
        with patch(
            "hmac.compare_digest", wraps=__import__("hmac").compare_digest
        ) as compare:
            for path in ("/mcp", "/discover", "/tools"):
                assert (
                    await client.post(path, headers={"X-API-Key": key})
                ).status_code == 200
            assert compare.call_count == 3
        assert calls == ["/mcp", "/discover", "/tools"]


@pytest.mark.parametrize("value", [None, "", "   "])
def test_api_key_requires_nonempty_configuration(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("MCP_API_KEY", raising=False)
    else:
        monkeypatch.setenv("MCP_API_KEY", value)
    with pytest.raises((ValueError, RuntimeError), match="MCP_API_KEY"):
        APIKeyMiddleware(Starlette())


@pytest.fixture
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def public_jwk(key, kid="primary"):
    return {
        **json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())),
        "kid": kid,
    }


def access_token(key, *, kid="primary", algorithm="RS256", **changes):
    claims = {
        "iss": "http://127.0.0.1:8089/realms/mcp-realm",
        "aud": "mcp-users",
        "exp": int(time.time()) + 60,
        "realm_access": {"roles": ["mcp-user"]},
    }
    claims.update(changes)
    claims = {name: value for name, value in claims.items() if value is not None}
    headers = {} if kid is None else {"kid": kid}
    return jwt.encode(claims, key, algorithm=algorithm, headers=headers)


def jwt_app(signing_key, handler=None):
    from t11_mcp_auth.mcp_server.auth.oauth import JWKSCache, JWTAuthMiddleware

    requests = []

    def serve(request):
        requests.append(request)
        if handler:
            return handler(request)
        return httpx.Response(200, json={"keys": [public_jwk(signing_key)]})

    cache = JWKSCache(
        "http://127.0.0.1:8089/realms/mcp-realm/protocol/openid-connect/certs",
        transport=httpx.MockTransport(serve),
    )
    app, calls = protected_app(
        JWTAuthMiddleware,
        issuer="http://127.0.0.1:8089/realms/mcp-realm",
        audience="mcp-users",
        required_role="mcp-user",
        jwks_cache=cache,
    )
    return app, calls, requests


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "malformed",
        "expired",
        "no-exp",
        "issuer",
        "audience",
        "signature",
        "algorithm",
        "no-kid",
    ],
)
async def test_jwt_invalid_credentials_never_dispatch(signing_key, case):
    app, calls, requests = jwt_app(signing_key)
    changes = {
        "expired": {"exp": 1},
        "no-exp": {"exp": None},
        "issuer": {"iss": "https://invalid.example"},
        "audience": {"aud": "other"},
    }
    token = access_token(signing_key, **changes.get(case, {}))
    if case == "signature":
        token = access_token(
            rsa.generate_private_key(public_exponent=65537, key_size=2048)
        )
    if case == "algorithm":
        token = access_token(secrets.token_bytes(32), algorithm="HS256")
    if case == "no-kid":
        token = access_token(signing_key, kid=None)
    headers = {"Authorization": f"Bearer {token}"}
    if case == "missing":
        headers = {}
    if case == "malformed":
        headers = {"Authorization": "Bearer invalid"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/mcp", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert token not in response.text
    assert calls == []
    if case in ("missing", "malformed", "algorithm", "no-kid"):
        assert requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "realm_access",
    [
        None,
        {},
        [],
        {"roles": "mcp-user"},
        {"roles": ["mcp-user", 1]},
        {"roles": ["other"]},
        {"roles": []},
    ],
)
async def test_jwt_malformed_or_absent_roles_are_forbidden(signing_key, realm_access):
    app, calls, _ = jwt_app(signing_key)
    token = access_token(signing_key, realm_access=realm_access)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/mcp", headers={"Authorization": f"Bearer {token}"}
        )
    assert response.status_code == 403
    assert "roles" not in response.text
    assert calls == []


@pytest.mark.asyncio
async def test_jwt_reuses_cached_keys_and_refetches_once_for_rotation(signing_key):
    rotated = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    available = [public_jwk(signing_key)]
    app, calls, requests = jwt_app(
        signing_key, lambda _: httpx.Response(200, json={"keys": list(available)})
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for _ in range(2):
            assert (
                await client.post(
                    "/mcp",
                    headers={"Authorization": f"Bearer {access_token(signing_key)}"},
                )
            ).status_code == 200
        assert len(requests) == 1
        available.append(public_jwk(rotated, "rotated"))
        assert (
            await client.post(
                "/mcp",
                headers={
                    "Authorization": f"Bearer {access_token(rotated, kid='rotated')}"
                },
            )
        ).status_code == 200
        assert len(requests) == 2
        response = await client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {access_token(rotated, kid='unknown')}"},
        )
        assert response.status_code == 401
        assert len(requests) == 3
    assert len(calls) == 3
    assert all(
        0 < request.extensions["timeout"]["connect"] <= 5 for request in requests
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "status", "json", "shape"])
async def test_jwks_unavailable_is_sanitized_503(signing_key, failure):
    def unavailable(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("sensitive upstream detail", request=request)
        if failure == "json":
            return httpx.Response(200, text="sensitive upstream detail")
        if failure == "shape":
            return httpx.Response(200, json={"keys": "sensitive upstream detail"})
        return httpx.Response(503, text="sensitive upstream detail")

    app, calls, requests = jwt_app(signing_key, unavailable)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/mcp", headers={"Authorization": f"Bearer {access_token(signing_key)}"}
        )
    assert response.status_code == 503
    assert "sensitive" not in response.text
    assert calls == []
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_jwks_outage_keeps_cached_key_usable_but_unknown_key_fails_closed(
    signing_key,
):
    available = True

    def serve(_):
        return (
            httpx.Response(200, json={"keys": [public_jwk(signing_key)]})
            if available
            else httpx.Response(503)
        )

    app, calls, requests = jwt_app(signing_key, serve)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        headers = {"Authorization": f"Bearer {access_token(signing_key)}"}
        assert (await client.post("/mcp", headers=headers)).status_code == 200
        available = False
        assert (
            await client.post(
                "/mcp",
                headers={
                    "Authorization": f"Bearer {access_token(signing_key, kid='unknown')}"
                },
            )
        ).status_code == 503
        assert (await client.post("/mcp", headers=headers)).status_code == 200
    assert len(calls) == 2
    assert len(requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("module_name", ["api_key_mcp_server", "oauth_mcp_server"])
async def test_server_apps_reject_unauthenticated_discovery(monkeypatch, module_name):
    monkeypatch.setenv("MCP_API_KEY", secrets.token_urlsafe(32))
    config = ModuleType("t11_mcp_auth.config")
    config.load_environment = lambda start=None: None
    config.required = lambda name: os.environ[name]
    monkeypatch.setitem(sys.modules, "t11_mcp_auth.config", config)
    module = importlib.import_module(f"t11_mcp_auth.mcp_server.{module_name}")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=module.app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "server/discover"}
        )
    assert response.status_code == 401


ROOT = Path(__file__).parent


@pytest.mark.parametrize("module_name", ["api_key_mcp_server", "oauth_mcp_server"])
def test_server_loads_environment_before_tools_and_defaults_isolated_ums(
    monkeypatch, module_name
):
    import runpy

    from fastmcp import FastMCP

    monkeypatch.delenv("USER_SERVICE_URL", raising=False)
    monkeypatch.setenv("MCP_API_KEY", secrets.token_urlsafe(32))
    loaded = []
    config = ModuleType("t11_mcp_auth.config")
    config.load_environment = lambda start=None: loaded.append(True)
    config.required = lambda name: os.environ[name]
    server = ModuleType("t11_mcp_auth.mcp_server._server")
    mcp = FastMCP("auth-startup-test")

    def resolve(name):
        if name != "mcp":
            raise AttributeError(name)
        assert loaded, "Environment must load before tool imports"
        assert os.environ["USER_SERVICE_URL"] == "http://127.0.0.1:8042"
        return mcp

    server.__getattr__ = resolve
    monkeypatch.setitem(sys.modules, "t11_mcp_auth.config", config)
    monkeypatch.setitem(sys.modules, "t11_mcp_auth.mcp_server._server", server)
    runpy.run_path(str(ROOT / "mcp_server" / f"{module_name}.py"))


def render_realm(tmp_path, *, omit=None):
    names = (
        "KEYCLOAK_ADMIN_PASSWORD",
        "MCP_ALLOWED_USER_PASSWORD",
        "MCP_NO_ROLE_USER_PASSWORD",
    )
    values = {name: secrets.token_urlsafe(24) for name in names}
    environment = {**os.environ, **values, "PYTHON_DOTENV_DISABLED": "1"}
    if omit:
        environment.pop(omit, None)
    output = tmp_path / "runtime" / "mcp-realm.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "keycloak" / "render_realm.py"),
            "--output",
            str(output),
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result, output, values


def test_realm_renderer_builds_public_pkce_audience_and_private_output(tmp_path):
    result, output, values = render_realm(tmp_path)
    assert result.returncode == 0, "Renderer failed"
    realm = json.loads(output.read_text())
    assert realm["accessTokenLifespan"] == 60
    client = next(item for item in realm["clients"] if item["clientId"] == "mcp-client")
    assert client["publicClient"] is True
    assert client["standardFlowEnabled"] is True
    assert client["directAccessGrantsEnabled"] is False
    assert client["serviceAccountsEnabled"] is False
    assert client["attributes"]["pkce.code.challenge.method"] == "S256"
    assert client["redirectUris"] == ["http://127.0.0.1:9999/callback"]
    mapper = next(
        item
        for item in client["protocolMappers"]
        if item["protocolMapper"] == "oidc-audience-mapper"
    )
    assert mapper["config"]["included.custom.audience"] == "mcp-users"
    assert mapper["config"]["access.token.claim"] == "true"
    users = {user["username"]: user for user in realm["users"]}
    assert set(users) == {"allowed-user", "no-role-user"}
    assert users["allowed-user"]["realmRoles"] == ["mcp-user"]
    assert users["no-role-user"]["realmRoles"] == []
    assert (
        users["allowed-user"]["credentials"][0]["value"]
        == values["MCP_ALLOWED_USER_PASSWORD"]
    )
    assert (
        users["no-role-user"]["credentials"][0]["value"]
        == values["MCP_NO_ROLE_USER_PASSWORD"]
    )
    assert output.stat().st_mode & 0o777 == 0o600
    assert output.parent.stat().st_mode & 0o777 == 0o700
    assert all(value not in result.stdout + result.stderr for value in values.values())
    assert not (ROOT / "keycloak" / "mcp-realm-config.json").exists()
    template = json.loads((ROOT / "keycloak" / "realm-template.json").read_text())
    assert all(not user.get("credentials") for user in template["users"])
    ignored = subprocess.run(
        ["git", "check-ignore", str(ROOT / "keycloak" / "runtime" / "mcp-realm.json")],
        capture_output=True,
        check=False,
    )
    assert ignored.returncode == 0


def test_realm_cli_loads_ancestor_environment_without_overriding_exports(tmp_path):
    names = (
        "KEYCLOAK_ADMIN_PASSWORD",
        "MCP_ALLOWED_USER_PASSWORD",
        "MCP_NO_ROLE_USER_PASSWORD",
    )
    values = {name: secrets.token_urlsafe() for name in names}
    (tmp_path / ".env").write_text(
        "\n".join(f"{name}={value}" for name, value in values.items())
    )
    nested = tmp_path / "nested"
    nested.mkdir()
    output = nested / "runtime" / "realm.json"
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in names and name != "PYTHON_DOTENV_DISABLED"
    }
    exported = secrets.token_urlsafe()
    environment["MCP_ALLOWED_USER_PASSWORD"] = exported
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "keycloak" / "render_realm.py"),
            "--output",
            str(output),
        ],
        cwd=nested,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, "Ancestor environment was not loaded"
    users = {item["username"]: item for item in json.loads(output.read_text())["users"]}
    assert users["allowed-user"]["credentials"][0]["value"] == exported
    assert (
        users["no-role-user"]["credentials"][0]["value"]
        == values["MCP_NO_ROLE_USER_PASSWORD"]
    )
    assert all(
        value not in result.stdout + result.stderr
        for value in (*values.values(), exported)
    )


@pytest.mark.parametrize(
    "omit",
    [
        "KEYCLOAK_ADMIN_PASSWORD",
        "MCP_ALLOWED_USER_PASSWORD",
        "MCP_NO_ROLE_USER_PASSWORD",
    ],
)
def test_realm_renderer_requires_each_password_without_output(tmp_path, omit):
    result, output, values = render_realm(tmp_path, omit=omit)
    assert result.returncode != 0
    assert omit in result.stderr
    assert not output.exists()
    assert all(value not in result.stdout + result.stderr for value in values.values())


def test_compose_uses_only_t11_loopback_ports_and_storage():
    import yaml

    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    assert compose["name"] == "t11-mcp-auth"
    services = compose["services"]
    assert services["userservice"]["ports"] == ["127.0.0.1:8042:8000"]
    assert services["keycloak"]["ports"] == ["127.0.0.1:8089:8080"]
    assert (
        services["keycloak"]["environment"]["KC_BOOTSTRAP_ADMIN_PASSWORD"]
        == "${KEYCLOAK_ADMIN_PASSWORD:?Set KEYCLOAK_ADMIN_PASSWORD}"
    )
    assert services["keycloak"]["volumes"] == [
        "./keycloak/runtime/mcp-realm.json:/opt/keycloak/data/import/mcp-realm.json:ro",
        "t11_keycloak_data:/opt/keycloak/data",
    ]
    assert set(compose["volumes"]) == {"t11_keycloak_data"}
