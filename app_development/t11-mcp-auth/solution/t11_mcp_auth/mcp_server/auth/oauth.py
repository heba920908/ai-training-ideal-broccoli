import asyncio
import os

import httpx
import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class KeyServiceUnavailable(Exception):
    pass


class JWKSCache:
    def __init__(self, url: str, *, transport=None):
        self.url = url
        self.transport = transport
        self.keys = None
        self.lock = asyncio.Lock()

    async def _fetch(self):
        try:
            async with httpx.AsyncClient(
                timeout=5.0, transport=self.transport, trust_env=False
            ) as client:
                response = await client.get(self.url)
                response.raise_for_status()
                document = response.json()
            if not isinstance(document, dict) or not isinstance(
                document.get("keys"), list
            ):
                raise TypeError("Invalid key set")
            keys = {}
            for entry in document["keys"]:
                if not isinstance(entry, dict):
                    continue
                if entry.get("kty") != "RSA" or entry.get("use", "sig") != "sig":
                    continue
                if entry.get("alg", "RS256") != "RS256":
                    continue
                kid = entry.get("kid")
                if isinstance(kid, str) and kid:
                    keys[kid] = jwt.PyJWK.from_dict(entry, algorithm="RS256").key
            if not keys:
                raise ValueError("No signing keys")
        except (httpx.HTTPError, ValueError, TypeError, KeyError, jwt.PyJWTError):
            raise KeyServiceUnavailable() from None
        self.keys = keys

    async def get_key(self, kid: str):
        snapshot = self.keys
        if snapshot is not None and kid in snapshot:
            return snapshot[kid]
        async with self.lock:
            if self.keys is not snapshot:
                if kid in self.keys:
                    return self.keys[kid]
                raise jwt.InvalidTokenError()
            await self._fetch()
            if kid not in self.keys:
                raise jwt.InvalidTokenError()
            return self.keys[kid]


class JWTAuthMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app, *, issuer=None, audience=None, required_role=None, jwks_cache=None
    ):
        super().__init__(app)
        base_url = os.getenv("KEYCLOAK_URL", "http://127.0.0.1:8089").rstrip("/")
        realm = os.getenv("KEYCLOAK_REALM", "mcp-realm")
        self.issuer = issuer or f"{base_url}/realms/{realm}"
        self.audience = audience or os.getenv("MCP_AUDIENCE", "mcp-users")
        self.required_role = required_role or os.getenv("MCP_REQUIRED_ROLE", "mcp-user")
        self.jwks = jwks_cache or JWKSCache(
            f"{self.issuer}/protocol/openid-connect/certs"
        )

    async def dispatch(self, request: Request, call_next):
        unauthorized = JSONResponse(
            {"error": "Unauthorized"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
        parts = request.headers.get("Authorization", "").split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return unauthorized
        token = parts[1]
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if header.get("alg") != "RS256" or not isinstance(kid, str) or not kid:
                return unauthorized
            key = await self.jwks.get_key(kid)
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["iss", "aud", "exp"]},
            )
        except KeyServiceUnavailable:
            return JSONResponse(
                {"error": "Authentication service unavailable"}, status_code=503
            )
        except (jwt.PyJWTError, ValueError, TypeError):
            return unauthorized
        realm_access = claims.get("realm_access")
        roles = realm_access.get("roles") if isinstance(realm_access, dict) else None
        if (
            not isinstance(roles, list)
            or not all(isinstance(role, str) for role in roles)
            or self.required_role not in roles
        ):
            return JSONResponse({"error": "Forbidden"}, status_code=403)
        return await call_next(request)
