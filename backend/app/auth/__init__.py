"""Supabase access-token verification and authenticated-user dependencies."""

from __future__ import annotations

from .dependencies import (
    get_access_token,
    get_auth_context,
    get_current_user,
    get_token_verifier,
)
from .schemas import AuthenticatedUser, AuthContext
from .verification import (
    SupabaseTokenVerifier,
    TokenVerificationError,
    TokenVerificationUnavailable,
    TokenVerifier,
)

__all__ = [
    "AuthenticatedUser",
    "AuthContext",
    "SupabaseTokenVerifier",
    "TokenVerificationError",
    "TokenVerificationUnavailable",
    "TokenVerifier",
    "get_access_token",
    "get_auth_context",
    "get_current_user",
    "get_token_verifier",
]
