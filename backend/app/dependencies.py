"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from .config import Settings


def get_settings(request: Request) -> Settings:
    """Return the settings attached to the running application.

    Reading settings from ``app.state`` (rather than a global) lets tests build
    an app with explicit, credential-free settings.
    """
    return request.app.state.settings
