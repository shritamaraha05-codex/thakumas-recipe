"""Supabase access-token verification.

Never trust a decoded-but-unverified JWT. Asymmetric projects are verified
against the project's JWKS endpoint (signature, ``kid``, algorithm, issuer,
audience and expiry). Legacy HS256 projects use Supabase Auth's ``/user``
endpoint, which verifies the token server-side; the project's JWT secret is
never requested, read or stored here.

The publishable key is used only as the ``apikey`` header for the legacy
endpoint. It is not a signing key and is never treated as an authentication
credential.
"""

from __future__ import annotations

import time
from typing import Any, Protocol

import httpx
import jwt
from jwt import PyJWK, PyJWTError

from backend.app.config import Settings

from .schemas import AuthenticatedUser

_ASYMMETRIC_ALGORITHMS = frozenset(
    {
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
        "EdDSA",
    }
)


class TokenVerificationError(Exception):
    """The token is missing, malformed, expired or otherwise invalid."""


class TokenVerificationUnavailable(Exception):
    """Supabase authentication could not be reached or is not configured."""


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> AuthenticatedUser: ...


class SupabaseTokenVerifier:
    """Verify Supabase access tokens for one project."""

    def __init__(
        self,
        *,
        url: str,
        publishable_key: str,
        audience: str = "authenticated",
        jwks_cache_seconds: int = 300,
        timeout: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        base = url.rstrip("/")
        self._issuer = f"{base}/auth/v1" if base else ""
        self._jwks_url = f"{self._issuer}/.well-known/jwks.json" if self._issuer else ""
        self._user_url = f"{self._issuer}/user" if self._issuer else ""
        self._publishable_key = publishable_key
        self._audience = audience
        self._jwks_cache_seconds = max(0, jwks_cache_seconds)
        self._timeout = timeout
        self._http_client = http_client
        self._jwks: dict[str, Any] | None = None
        self._jwks_expires_at = 0.0

    @classmethod
    def from_settings(cls, settings: Settings) -> SupabaseTokenVerifier:
        return cls(
            url=settings.supabase_url,
            publishable_key=settings.supabase_key,
            audience=settings.supabase_jwt_audience,
            jwks_cache_seconds=settings.supabase_jwks_cache_seconds,
            timeout=settings.supabase_request_timeout,
        )

    async def verify(self, token: str) -> AuthenticatedUser:
        if not self._issuer:
            raise TokenVerificationUnavailable("Supabase authentication is not configured.")

        try:
            header = jwt.get_unverified_header(token)
        except PyJWTError as exc:
            raise TokenVerificationError("Malformed token.") from exc

        algorithm = header.get("alg")
        if not isinstance(algorithm, str) or not algorithm or algorithm.lower() == "none":
            raise TokenVerificationError("Unsupported token algorithm.")

        if algorithm == "HS256":
            # A pre-signing-key Supabase project. Verify through the Auth API;
            # never fetch or use the project's JWT secret locally.
            return await self._verify_legacy(token)

        if algorithm not in _ASYMMETRIC_ALGORITHMS:
            raise TokenVerificationError("Unsupported token algorithm.")

        key_id = header.get("kid")
        if not isinstance(key_id, str) or not key_id:
            raise TokenVerificationError("Token is missing its signing key id.")

        key = await self._signing_key(key_id, algorithm)

        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[algorithm],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iss", "sub"]},
            )
        except PyJWTError as exc:
            raise TokenVerificationError("Token validation failed.") from exc

        return _user_from_claims(claims)

    async def _verify_legacy(self, token: str) -> AuthenticatedUser:
        if not self._publishable_key:
            raise TokenVerificationUnavailable("Supabase authentication is not configured.")
        try:
            response = await self._client().get(
                self._user_url,
                headers={
                    "apikey": self._publishable_key,
                    "Authorization": f"Bearer {token}",
                },
            )
        except httpx.HTTPError as exc:
            raise TokenVerificationUnavailable("The Supabase auth service is unavailable.") from exc

        if response.status_code in (401, 403, 400):
            raise TokenVerificationError("Token validation failed.")
        if response.status_code >= 500 or response.status_code != 200:
            raise TokenVerificationUnavailable("The Supabase auth service is unavailable.")

        try:
            data = response.json()
        except ValueError as exc:
            raise TokenVerificationError("Token validation failed.") from exc
        if not isinstance(data, dict):
            raise TokenVerificationError("Token validation failed.")

        user_id = data.get("id") or data.get("sub")
        if not isinstance(user_id, str) or not user_id:
            raise TokenVerificationError("Token validation failed.")

        metadata = data.get("user_metadata")
        return AuthenticatedUser(
            id=user_id,
            email=data.get("email") if isinstance(data.get("email"), str) else None,
            role=data.get("role") if isinstance(data.get("role"), str) else None,
            user_metadata=metadata if isinstance(metadata, dict) else {},
        )

    async def _signing_key(self, key_id: str, algorithm: str) -> PyJWK:
        jwks = await self._fetch_jwks()
        for key_data in jwks.get("keys", []):
            if not isinstance(key_data, dict) or key_data.get("kid") != key_id:
                continue
            key_algorithm = key_data.get("alg")
            if key_algorithm is not None and key_algorithm != algorithm:
                raise TokenVerificationError("Token algorithm does not match its signing key.")
            try:
                return PyJWK(key_data, algorithm=algorithm)
            except PyJWTError as exc:
                raise TokenVerificationError("The signing key is invalid.") from exc
        raise TokenVerificationError("Unknown signing key.")

    async def _fetch_jwks(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._jwks is not None and now < self._jwks_expires_at:
            return self._jwks
        try:
            response = await self._client().get(self._jwks_url)
        except httpx.HTTPError as exc:
            raise TokenVerificationUnavailable(
                "The Supabase signing keys are unavailable."
            ) from exc
        if response.status_code != 200:
            raise TokenVerificationUnavailable("The Supabase signing keys are unavailable.")
        try:
            data = response.json()
        except ValueError as exc:
            raise TokenVerificationUnavailable(
                "The Supabase signing keys are unavailable."
            ) from exc
        if not isinstance(data, dict) or not isinstance(data.get("keys"), list):
            raise TokenVerificationUnavailable("The Supabase signing keys are malformed.")
        self._jwks = data
        self._jwks_expires_at = now + self._jwks_cache_seconds
        return data

    def _client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self._timeout)
        return self._http_client


def _user_from_claims(claims: dict[str, Any]) -> AuthenticatedUser:
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise TokenVerificationError("Token has no subject.")
    metadata = claims.get("user_metadata")
    return AuthenticatedUser(
        id=subject,
        email=claims.get("email") if isinstance(claims.get("email"), str) else None,
        role=claims.get("role") if isinstance(claims.get("role"), str) else None,
        user_metadata=metadata if isinstance(metadata, dict) else {},
    )
