import asyncio
import base64
import hashlib
import math
import os
import secrets
import socket
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Lock, Thread
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://127.0.0.1:8089").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "mcp-realm")
CLIENT_ID = os.getenv("MCP_CLIENT_ID", "mcp-client")

REDIRECT_PORT = 9999
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/callback"
CALLBACK_TIMEOUT = 120.0
TOKEN_TIMEOUT = 15.0

_BASE = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect"
AUTH_ENDPOINT = f"{_BASE}/auth"
TOKEN_ENDPOINT = f"{_BASE}/token"


def _generate_pkce_pair() -> tuple[str, str]:
    """Generate a fresh verifier and unpadded S256 challenge."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge.rstrip(b"=").decode("ascii")


def _build_auth_url(code_challenge: str, state: str) -> str:
    """Build the Keycloak /authorize URL with PKCE parameters"""
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "openid",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


def _callback_handler(code_holder: dict, ready_event: Event):
    class _CallbackHandler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(0.1)

        def do_GET(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query, keep_blank_values=True)
            expected = code_holder.get("expected_state")
            states = params.get("state", [])
            codes = params.get("code", [])
            valid = (
                parsed.path == "/callback"
                and isinstance(expected, str)
                and len(states) == 1
                and secrets.compare_digest(states[0].encode(), expected.encode())
                and "error" not in params
                and len(codes) == 1
                and bool(codes[0].strip())
            )
            self.send_response(
                200 if valid else 404 if parsed.path != "/callback" else 400
            )
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            body = (
                b"Callback accepted. You can close this tab."
                if valid
                else b"Invalid authentication callback."
            )
            try:
                self.wfile.write(body)
            except OSError:
                pass
            if valid:
                code_holder["code"] = codes[0]
                code_holder["state"] = states[0]
                ready_event.set()

        def log_message(self, format, *args):
            pass

    return _CallbackHandler


class _CallbackServer(HTTPServer):
    def __init__(self, *args):
        self._active = None
        self._closing = False
        self._socket_lock = Lock()
        super().__init__(*args)

    def get_request(self):
        connection, address = super().get_request()
        with self._socket_lock:
            if self._closing:
                connection.close()
                raise OSError("Callback listener is closing")
            self._active = connection
        return connection, address

    def shutdown_request(self, connection):
        with self._socket_lock:
            if self._active is connection:
                self._active = None
        super().shutdown_request(connection)

    def abort(self):
        with self._socket_lock:
            self._closing = True
            if self._active is not None:
                try:
                    self._active.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass


def _serve_callback(server: HTTPServer, ready_event: Event, stop_event: Event) -> None:
    server.timeout = 0.05
    while not stop_event.is_set() and not ready_event.is_set():
        server.handle_request()


def _run_callback_server(code_holder: dict, ready_event: Event) -> None:
    """Compatibility helper; supply expected_state in code_holder to validate callbacks."""
    deadline = time.monotonic() + CALLBACK_TIMEOUT
    with HTTPServer(
        ("127.0.0.1", REDIRECT_PORT), _callback_handler(code_holder, ready_event)
    ) as server:
        server.timeout = 0.05
        while not ready_event.is_set() and time.monotonic() < deadline:
            server.handle_request()


async def _token_request(data: dict[str, str]) -> dict:
    try:
        async with httpx.AsyncClient(timeout=TOKEN_TIMEOUT, trust_env=False) as client:
            response = await client.post(TOKEN_ENDPOINT, data=data)
            response.raise_for_status()
            tokens = response.json()
        if not isinstance(tokens, dict):
            raise TypeError
        return tokens
    except (httpx.HTTPError, ValueError, TypeError):
        raise RuntimeError(
            "OAuth token request failed; explicit login required."
        ) from None


async def _exchange_code_for_tokens(code: str, code_verifier: str) -> dict:
    """POST the authorization code + code_verifier to get access/refresh tokens"""
    return await _token_request(
        {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "code": code,
            "code_verifier": code_verifier,
        }
    )


async def _refresh_access_token(refresh_token: str) -> dict:
    """Use the refresh_token to get a new access_token without user interaction"""
    return await _token_request(
        {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": refresh_token,
        }
    )


class OAuthTokenManager:
    """
    Manages the full OAuth 2.0 + PKCE lifecycle:
      - Initial browser-based authorization
      - Stores access_token + refresh_token
      - Transparently refreshes tokens when expired

    Usage:
        manager = OAuthTokenManager()
        await manager.authenticate()          # opens browser once
        headers = await manager.auth_headers()  # always returns valid headers
    """

    def __init__(self):
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float | None = None
        self._refresh_lock = asyncio.Lock()

    async def authenticate(self) -> None:
        """
        Run the PKCE authorization code flow:
        1. Generate PKCE pair + state
        2. Open browser → Keycloak login page
        3. Wait for callback with auth code
        4. Exchange code for tokens
        """
        code_verifier, code_challenge = _generate_pkce_pair()
        state = secrets.token_urlsafe(16)

        code_holder: dict = {"expected_state": state}
        ready_event = Event()
        stop_event = Event()
        try:
            server = _CallbackServer(
                ("127.0.0.1", REDIRECT_PORT),
                _callback_handler(code_holder, ready_event),
            )
        except OSError:
            raise RuntimeError(
                "OAuth callback listener unavailable; explicit login required."
            ) from None
        thread = Thread(target=_serve_callback, args=(server, ready_event, stop_event))
        started = False
        try:
            deadline = time.monotonic() + CALLBACK_TIMEOUT
            thread.start()
            started = True
            try:
                opened = webbrowser.open(_build_auth_url(code_challenge, state))
            except (OSError, webbrowser.Error):
                raise RuntimeError(
                    "Could not open OAuth browser; explicit login required."
                ) from None
            if not opened:
                raise RuntimeError(
                    "Could not open OAuth browser; explicit login required."
                )
            while not ready_event.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        "OAuth callback timed out; explicit login required."
                    )
                await asyncio.sleep(min(0.01, remaining))
            try:
                tokens = await _exchange_code_for_tokens(
                    code_holder["code"], code_verifier
                )
                self._store_tokens(tokens, preserve_refresh=False)
            except (RuntimeError, ValueError, TypeError, httpx.HTTPError):
                raise RuntimeError(
                    "OAuth token exchange failed; explicit login required."
                ) from None
        finally:
            stop_event.set()
            try:
                server.abort()
            finally:
                server.server_close()
                if started:
                    thread.join(timeout=1)

    def _store_tokens(self, tokens: dict, *, preserve_refresh: bool = True) -> None:
        if not isinstance(tokens, dict):
            raise TypeError("Invalid OAuth token response; explicit login required.")
        access_token = tokens.get("access_token")
        refresh_token = tokens.get(
            "refresh_token", self._refresh_token if preserve_refresh else None
        )
        expires_in = tokens.get("expires_in")
        token_type = tokens.get("token_type")
        if isinstance(expires_in, bool) or not isinstance(expires_in, (int, float)):
            raise TypeError("Invalid OAuth token response; explicit login required.")
        try:
            expires_at = time.monotonic() + expires_in - 30
        except OverflowError:
            raise RuntimeError(
                "Invalid OAuth token response; explicit login required."
            ) from None
        valid_access = (
            isinstance(access_token, str)
            and bool(access_token)
            and not any(char.isspace() for char in access_token)
        )
        valid_refresh = (
            refresh_token is None
            and "refresh_token" not in tokens
            or isinstance(refresh_token, str)
            and bool(refresh_token)
            and not any(char.isspace() for char in refresh_token)
        )
        if (
            not valid_access
            or not valid_refresh
            or not isinstance(token_type, str)
            or token_type.lower() != "bearer"
            or not math.isfinite(expires_at)
            or expires_in <= 0
        ):
            raise RuntimeError("Invalid OAuth token response; explicit login required.")
        self._access_token, self._refresh_token, self._expires_at = (
            access_token,
            refresh_token,
            expires_at,
        )

    def is_token_expired(self) -> bool:
        """Returns True if the access token is missing or within 30s of expiry"""
        return (
            not self._access_token
            or self._expires_at is None
            or time.monotonic() >= self._expires_at
        )

    async def refresh(self) -> None:
        """Refresh the access token using the stored refresh_token"""
        async with self._refresh_lock:
            if not self.is_token_expired():
                return
            if not self._refresh_token:
                raise RuntimeError(
                    "No refresh token available; explicit login required."
                )
            try:
                tokens = await _refresh_access_token(self._refresh_token)
                self._store_tokens(tokens)
            except (RuntimeError, ValueError, TypeError, httpx.HTTPError):
                raise RuntimeError(
                    "OAuth refresh failed; explicit login required."
                ) from None

    async def auth_headers(self) -> dict[str, str]:
        """Return Authorization headers with the current access token"""
        if not self._access_token:
            raise RuntimeError("No access token available; explicit login required.")
        if self.is_token_expired():
            await self.refresh()
        if self.is_token_expired():
            raise RuntimeError(
                "OAuth token lifetime is too short; explicit login required."
            )
        return {"Authorization": f"Bearer {self._access_token}"}
