"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Request

from .config import Settings
from .providers import StructuredLLMProvider


def get_settings(request: Request) -> Settings:
    """Return the settings attached to the running application.

    Reading settings from ``app.state`` (rather than a global) lets tests build
    an app with explicit, credential-free settings.
    """
    return request.app.state.settings


def get_llm_provider_factory(
    request: Request,
) -> Callable[[Settings], StructuredLLMProvider]:
    """Return the app's provider factory.

    The factory is resolved but *not* called here, and a provider (and therefore
    any SDK client) is only ever built when an LLM parser is actually selected.
    Tests override the factory to inject a fake provider.
    """
    return request.app.state.llm_provider_factory
