"""FastAPI dependencies deriving identity from a verified Supabase token."""

from __future__ import annotations

from fastapi import Depends, Header, Request

from backend.app.errors import ApiError
from backend.app.models import ErrorCode

from .schemas import AuthenticatedUser, AuthContext
from .verification import (
    TokenVerificationError,
    TokenVerificationUnavailable,
    TokenVerifier,
)


def get_token_verifier(request: Request) -> TokenVerifier:
    """The verifier attached to the running app (tests inject a fake)."""
    return request.app.state.token_verifier


async def get_auth_context(
    request: Request,
    authorization: str | None = Header(default=None),
    verifier: TokenVerifier = Depends(get_token_verifier),
) -> AuthContext:
    """Parse and verify ``Authorization: Bearer <token>``.

    The returned identity comes only from verified claims. A client-supplied
    user id is never consulted.
    """
    token = _bearer_token(authorization)
    try:
        user = await verifier.verify(token)
    except TokenVerificationError as exc:
        raise _unauthorized() from exc
    except TokenVerificationUnavailable as exc:
        raise ApiError(
            status_code=503,
            code=ErrorCode.UPSTREAM_BUSY,
            message="Authentication is temporarily unavailable.",
            hint="Try again shortly.",
        ) from exc
    return AuthContext(user=user, access_token=token)


def get_current_user(auth: AuthContext = Depends(get_auth_context)) -> AuthenticatedUser:
    return auth.user


def get_access_token(auth: AuthContext = Depends(get_auth_context)) -> str:
    """The raw token, used only to build a per-request data client."""
    return auth.access_token


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise _unauthorized()
    scheme, _, token = authorization.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized()
    return token


def _unauthorized() -> ApiError:
    return ApiError(
        status_code=401,
        code=ErrorCode.UNAUTHORIZED,
        message="A valid access token is required.",
        hint="Send 'Authorization: Bearer <access_token>'.",
    )
