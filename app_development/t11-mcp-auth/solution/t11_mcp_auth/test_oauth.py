import asyncio
import base64
import hashlib
import http.client
import secrets
import socket
import threading
import time
from secrets import token_urlsafe
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest
from t11_mcp_auth.agent.mcp_clients import _oauth_keycloak as oauth


def token_response(**overrides):
    payload = {
        "access_token": token_urlsafe(32),
        "refresh_token": token_urlsafe(32),
        "token_type": "Bearer",
        "expires_in": 60,
    }
    payload.update(overrides)
    return payload


def same_secret(actual, expected):
    assert isinstance(actual, str)
    matches = secrets.compare_digest(actual, expected)
    assert matches


@pytest.fixture
def callback(monkeypatch):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    monkeypatch.setattr(oauth, "REDIRECT_PORT", port)
    monkeypatch.setattr(oauth, "REDIRECT_URI", f"http://127.0.0.1:{port}/callback")
    baseline = set(threading.enumerate())
    yield port
    assert not [thread for thread in threading.enumerate() if thread not in baseline]
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))


def send_callback(port, path, params):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
    try:
        connection.request("GET", f"{path}?{urlencode(params, doseq=True)}")
        response = connection.getresponse()
        status = response.status
        response.read()
        return status
    finally:
        connection.close()


@pytest.mark.asyncio
async def test_cancellation_closes_a_continuously_trickled_callback(
    monkeypatch, callback
):
    accepted = threading.Event()
    stop = threading.Event()
    original_handler = oauth._callback_handler
    sender = None

    def handler(*args):
        class Observed(original_handler(*args)):
            def setup(self):
                super().setup()
                accepted.set()

        return Observed

    def browser(url):
        nonlocal sender
        connection = socket.create_connection(("127.0.0.1", callback), timeout=1)

        def trickle():
            try:
                connection.sendall(b"GET /callback HTTP/1.1\r\nX-Slow: ")
                deadline = time.monotonic() + 0.8
                while time.monotonic() < deadline and not stop.wait(0.02):
                    connection.sendall(b"a")
            except OSError:
                pass
            finally:
                connection.close()

        sender = threading.Thread(target=trickle)
        sender.start()
        return True

    monkeypatch.setattr(oauth, "_callback_handler", handler)
    monkeypatch.setattr(oauth.webbrowser, "open", browser)
    task = asyncio.create_task(oauth.OAuthTokenManager().authenticate())
    try:
        async with asyncio.timeout(1):
            while not accepted.is_set():
                await asyncio.sleep(0.001)
        started = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert time.monotonic() - started < 0.3
    finally:
        stop.set()
        if sender is not None:
            sender.join(timeout=1)
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


def test_pkce_is_fresh_unpadded_s256():
    verifier, challenge = oauth._generate_pkce_pair()
    other_verifier, other_challenge = oauth._generate_pkce_pair()
    assert 43 <= len(verifier) <= 128
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    same_secret(challenge, expected.rstrip(b"=").decode())
    assert not secrets.compare_digest(verifier, other_verifier)
    assert not secrets.compare_digest(challenge, other_challenge)
    assert "=" not in challenge


def test_authorization_url_is_public_client_s256():
    challenge, state = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    url = urlsplit(oauth._build_auth_url(challenge, state))
    params = parse_qs(url.query)
    assert f"{url.scheme}://{url.netloc}{url.path}" == oauth.AUTH_ENDPOINT
    assert set(params) == {
        "response_type",
        "client_id",
        "redirect_uri",
        "scope",
        "state",
        "code_challenge",
        "code_challenge_method",
    }
    assert params["response_type"] == ["code"]
    assert params["client_id"] == [oauth.CLIENT_ID]
    assert params["redirect_uri"] == [oauth.REDIRECT_URI]
    assert params["scope"] == ["openid"]
    assert params["code_challenge_method"] == ["S256"]
    same_secret(params["state"][0], state)
    same_secret(params["code_challenge"][0], challenge)


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["path", "state", "error", "code", "duplicate"])
async def test_invalid_callback_allows_later_valid_callback(
    monkeypatch, callback, capsys, caplog, invalid
):
    code = secrets.token_urlsafe(32)
    payload = token_response()
    exchanged = []

    async def exchange(received_code, verifier):
        same_secret(received_code, code)
        assert 43 <= len(verifier) <= 128
        exchanged.append(True)
        return payload

    def browser(url):
        params = parse_qs(urlsplit(url).query)
        state = params["state"][0]
        bad = {"state": state, "code": code}
        path = "/callback"
        if invalid == "path":
            path = "/wrong"
        elif invalid == "state":
            bad["state"] = secrets.token_urlsafe(32)
        elif invalid == "error":
            bad["error"] = secrets.token_urlsafe(32)
        elif invalid == "code":
            bad.pop("code")
        else:
            bad["state"] = [state, state]
        assert send_callback(callback, path, bad) in {400, 404}
        assert not exchanged
        assert (
            send_callback(callback, "/callback", {"state": state, "code": code}) == 200
        )
        return True

    monkeypatch.setattr(oauth.webbrowser, "open", browser)
    monkeypatch.setattr(oauth, "_exchange_code_for_tokens", exchange)
    manager = oauth.OAuthTokenManager()
    await manager.authenticate()
    same_secret(
        (await manager.auth_headers())["Authorization"],
        f"Bearer {payload['access_token']}",
    )
    assert len(exchanged) == 1
    output = capsys.readouterr()
    assert not output.out and not output.err and not caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "timeout",
        "invalid_timeout",
        "cancel",
        "browser_false",
        "browser_raise",
        "exchange",
    ],
)
async def test_login_always_releases_listener(monkeypatch, callback, failure):
    manager = oauth.OAuthTokenManager()
    opened = asyncio.Event()
    monkeypatch.setattr(oauth, "CALLBACK_TIMEOUT", 0.05, raising=False)

    def browser(url):
        opened.set()
        if failure == "browser_false":
            return False
        if failure == "browser_raise":
            raise OSError(secrets.token_urlsafe(32))
        if failure == "invalid_timeout":
            assert (
                send_callback(
                    callback, "/callback", {"state": secrets.token_urlsafe(32)}
                )
                == 400
            )
        if failure == "exchange":
            state = parse_qs(urlsplit(url).query)["state"][0]
            assert (
                send_callback(
                    callback,
                    "/callback",
                    {"state": state, "code": secrets.token_urlsafe(32)},
                )
                == 200
            )
        return True

    async def exchange(*args):
        raise RuntimeError(secrets.token_urlsafe(32))

    monkeypatch.setattr(oauth.webbrowser, "open", browser)
    monkeypatch.setattr(oauth, "_exchange_code_for_tokens", exchange)
    task = asyncio.create_task(manager.authenticate())
    await opened.wait()
    if failure == "cancel":
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    elif failure in {"timeout", "invalid_timeout"}:
        with pytest.raises(TimeoutError):
            await task
    else:
        with pytest.raises(RuntimeError):
            await task
    assert manager._access_token is None


@pytest.mark.asyncio
async def test_cancel_during_exchange_releases_listener(monkeypatch, callback):
    exchanging = asyncio.Event()

    def browser(url):
        state = parse_qs(urlsplit(url).query)["state"][0]
        assert (
            send_callback(
                callback,
                "/callback",
                {"state": state, "code": secrets.token_urlsafe(32)},
            )
            == 200
        )
        return True

    async def exchange(*args):
        exchanging.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(oauth.webbrowser, "open", browser)
    monkeypatch.setattr(oauth, "_exchange_code_for_tokens", exchange)
    manager = oauth.OAuthTokenManager()
    task = asyncio.create_task(manager.authenticate())
    await asyncio.wait_for(exchanging.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert manager._access_token is None


@pytest.mark.asyncio
async def test_relogin_has_fresh_pkce_state_and_no_old_refresh_token(
    monkeypatch, callback
):
    attempts = []
    codes = []

    def browser(url):
        params = parse_qs(urlsplit(url).query)
        attempts.append(params)
        code = secrets.token_urlsafe(32)
        codes.append(code)
        assert (
            send_callback(
                callback, "/callback", {"state": params["state"][0], "code": code}
            )
            == 200
        )
        return True

    async def exchange(code, verifier):
        same_secret(code, codes[-1])
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        same_secret(challenge, attempts[-1]["code_challenge"][0])
        payload = token_response()
        if len(attempts) == 2:
            payload.pop("refresh_token")
        return payload

    monkeypatch.setattr(oauth.webbrowser, "open", browser)
    monkeypatch.setattr(oauth, "_exchange_code_for_tokens", exchange)
    manager = oauth.OAuthTokenManager()
    await manager.authenticate()
    await manager.authenticate()
    for field in ("state", "code_challenge"):
        reused = secrets.compare_digest(attempts[0][field][0], attempts[1][field][0])
        assert not reused
    refresh_missing = manager._refresh_token is None
    assert refresh_missing


@pytest.mark.asyncio
async def test_occupied_callback_port_does_not_open_browser(monkeypatch, callback):
    def browser(url):
        pytest.fail("browser opened before successful listener bind")

    monkeypatch.setattr(oauth.webbrowser, "open", browser)
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", callback))
        occupied.listen()
        with pytest.raises(RuntimeError, match="callback"):
            await oauth.OAuthTokenManager().authenticate()


@pytest.mark.asyncio
@pytest.mark.parametrize("grant", ["authorization_code", "refresh_token"])
async def test_token_http_boundary_uses_bounded_form_post(monkeypatch, grant):
    supplied, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    payload = token_response()
    requests = []
    client_type = httpx.AsyncClient

    def handler(request):
        requests.append(request)
        assert request.method == "POST"
        assert str(request.url) == oauth.TOKEN_ENDPOINT
        assert request.headers["content-type"] == "application/x-www-form-urlencoded"
        assert "authorization" not in request.headers
        form = parse_qs(request.content.decode())
        assert form["client_id"] == [oauth.CLIENT_ID]
        assert form["grant_type"] == [grant]
        assert "client_secret" not in form
        assert all(0 < value <= 30 for value in request.extensions["timeout"].values())
        if grant == "authorization_code":
            same_secret(form["code"][0], supplied)
            same_secret(form["code_verifier"][0], verifier)
            assert form["redirect_uri"] == [oauth.REDIRECT_URI]
        else:
            same_secret(form["refresh_token"][0], supplied)
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(
        oauth.httpx,
        "AsyncClient",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = await (
        oauth._exchange_code_for_tokens(supplied, verifier)
        if grant == "authorization_code"
        else oauth._refresh_access_token(supplied)
    )
    same_secret(result["access_token"], payload["access_token"])
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["status", "json", "shape", "network"])
async def test_token_http_errors_are_sanitized(monkeypatch, failure):
    sensitive = secrets.token_urlsafe(32)
    client_type = httpx.AsyncClient

    def handler(request):
        if failure == "network":
            raise httpx.ConnectError(sensitive, request=request)
        if failure == "status":
            return httpx.Response(400, text=sensitive)
        if failure == "json":
            return httpx.Response(200, text=sensitive)
        return httpx.Response(200, json=[sensitive])

    monkeypatch.setattr(
        oauth.httpx,
        "AsyncClient",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs),
    )
    with pytest.raises(RuntimeError) as caught:
        await oauth._refresh_access_token(secrets.token_urlsafe(32))
    assert sensitive not in str(caught.value)
    assert "login" in str(caught.value).lower()


def test_monotonic_expiry_uses_thirty_second_margin(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(oauth.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(oauth.time, "time", lambda: pytest.fail("wall clock used"))
    manager = oauth.OAuthTokenManager()
    assert manager.is_token_expired()
    manager._store_tokens(token_response())
    clock[0] = 129.999
    assert not manager.is_token_expired()
    clock[0] = 130
    assert manager.is_token_expired()


@pytest.mark.parametrize(
    "invalid",
    [
        {},
        {"access_token": ""},
        {"access_token": None},
        {"access_token": 12},
        {"access_token": "\r\n"},
        {"refresh_token": ""},
        {"refresh_token": None},
        {"token_type": "Basic"},
        {"token_type": None},
        {"expires_in": 0},
        {"expires_in": -1},
        {"expires_in": True},
        {"expires_in": "60"},
        {"expires_in": float("inf")},
        {"expires_in": float("nan")},
        {"expires_in": 10**400},
    ],
)
def test_invalid_token_response_does_not_partially_store(invalid):
    manager = oauth.OAuthTokenManager()
    original = token_response()
    manager._store_tokens(original)
    before = manager._expires_at
    candidate = token_response(**invalid) if invalid else {}
    with pytest.raises((RuntimeError, TypeError), match="login"):
        manager._store_tokens(candidate)
    same_secret(manager._access_token, original["access_token"])
    same_secret(manager._refresh_token, original["refresh_token"])
    assert manager._expires_at == before


@pytest.mark.asyncio
@pytest.mark.parametrize("rotate", [False, True])
async def test_concurrent_headers_refresh_once_and_preserve_or_rotate(
    monkeypatch, rotate
):
    clock = [100.0]
    monkeypatch.setattr(oauth.time, "monotonic", lambda: clock[0])
    manager = oauth.OAuthTokenManager()
    original = token_response()
    manager._store_tokens(original)
    replacement = token_response()
    if not rotate:
        replacement.pop("refresh_token")
    calls = []

    async def refresh(refresh_token):
        same_secret(refresh_token, original["refresh_token"])
        calls.append(True)
        await asyncio.sleep(0)
        return replacement

    monkeypatch.setattr(oauth, "_refresh_access_token", refresh)
    clock[0] = 130
    headers = await asyncio.gather(*(manager.auth_headers() for _ in range(12)))
    assert len(calls) == 1
    for header in headers:
        same_secret(header["Authorization"], f"Bearer {replacement['access_token']}")
    same_secret(
        manager._refresh_token,
        replacement.get("refresh_token", original["refresh_token"]),
    )
    await manager.refresh()
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing", "endpoint", "invalid"])
async def test_refresh_failure_requires_explicit_login_without_browser(
    monkeypatch, failure
):
    clock = [100.0]
    monkeypatch.setattr(oauth.time, "monotonic", lambda: clock[0])
    manager = oauth.OAuthTokenManager()
    original = token_response()
    if failure == "missing":
        original.pop("refresh_token")
    manager._store_tokens(original)
    before = manager._expires_at
    sensitive = secrets.token_urlsafe(32)

    async def refresh(refresh_token):
        if failure == "missing":
            pytest.fail("refresh attempted without a refresh token")
        if failure == "endpoint":
            raise RuntimeError(sensitive)
        return token_response(expires_in=0)

    def browser(url):
        pytest.fail("refresh reopened browser")

    monkeypatch.setattr(oauth, "_refresh_access_token", refresh)
    monkeypatch.setattr(oauth.webbrowser, "open", browser)
    clock[0] = 130
    with pytest.raises(RuntimeError, match="login") as caught:
        await manager.auth_headers()
    assert sensitive not in str(caught.value)
    same_secret(manager._access_token, original["access_token"])
    assert manager._expires_at == before


@pytest.mark.asyncio
async def test_headers_before_login_require_explicit_login():
    with pytest.raises(RuntimeError, match="login"):
        await oauth.OAuthTokenManager().auth_headers()


@pytest.mark.asyncio
async def test_short_lived_refresh_is_not_sent_as_fresh_credentials(monkeypatch):
    manager = oauth.OAuthTokenManager()
    manager._store_tokens(token_response(expires_in=1))

    async def refresh(refresh_token):
        return token_response(expires_in=1)

    monkeypatch.setattr(oauth, "_refresh_access_token", refresh)
    with pytest.raises(RuntimeError, match="login"):
        await manager.auth_headers()
