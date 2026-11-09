"""Verified identity representations.

Only :class:`AuthenticatedUser` is ever exposed to route handlers as identity;
the raw access token is kept on :class:`AuthContext` and is never serialised.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """The identity derived *exclusively* from a verified token's ``sub`` claim."""

    id: str
    email: str | None = None
    role: str | None = None
    user_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str | None:
        """A display name carried by the token, if the provider supplied one."""
        for key in ("full_name", "name", "display_name"):
            value = self.user_metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None


@dataclass(frozen=True, slots=True)
class AuthContext:
    """The verified user plus their raw token, for a single request only."""

    user: AuthenticatedUser
    access_token: str = field(repr=False)
