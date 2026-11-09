"""System endpoints.

``GET /api/health`` reports what is actually true right now. It never claims a
database is healthy merely because environment variables exist, and it never
contains a URL, key or connection string.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeAlias

import httpx
from fastapi import APIRouter, Depends, Request

from ..config import Settings
from ..dependencies import get_settings
from ..models import (
    DbStatus,
    GnaniStatus,
    HealthResponse,
    LlmProviderStatus,
    LlmStatus,
)

router = APIRouter(tags=["system"])

DbProbe: TypeAlias = Callable[[], Awaitable[bool | None]]


def _provider(name: str, configured: bool, healthy: bool | None, note: str) -> LlmProviderStatus:
    return LlmProviderStatus(name=name, configured=configured, healthy=healthy, note=note)


def _llm_status(settings: Settings) -> LlmStatus:
    registry = {
        "gemini": _provider(
            "gemini",
            configured=bool(settings.gemini_api_key),
            healthy=None,
            note="LLM extraction provider (M-10); reachability is not probed here",
        ),
        "ollama": _provider(
            "ollama",
            configured=bool(settings.ollama_base_url),
            healthy=None,
            note="local OpenAI-compatible provider; reachability is not probed here",
        ),
        "evon_kaggle": _provider(
            "evon_kaggle",
            configured=False,
            healthy=None,
            note="not part of the production path",
        ),
        "rules": _provider(
            "rules",
            configured=True,
            healthy=True,
            note="deterministic offline floor; makes no external call",
        ),
    }

    chain = settings.llm_chain_list
    # Always show Gemini (the selected primary) and rules (the floor), plus
    # anything else the configured chain names.
    names = list(dict.fromkeys([*chain, "gemini", "rules"]))
    providers = [
        registry.get(
            name,
            _provider(name, configured=False, healthy=None, note="unknown provider"),
        )
        for name in names
    ]
    healthy = [p.name for p in providers if p.healthy is True]
    return LlmStatus(chain=chain, healthy=healthy, providers=providers)


async def _db_status(settings: Settings, probe: DbProbe | None) -> DbStatus:
    if not settings.supabase_configured:
        return DbStatus(
            status="not_configured",
            configured=False,
            reachable=None,
            note="Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY to enable accounts and storage.",
        )
    if probe is None:
        return DbStatus(
            status="unverified",
            configured=True,
            reachable=None,
            note="Supabase is configured; connectivity was not probed.",
        )
    try:
        reachable = await probe()
    except Exception:  # noqa: BLE001 - a probe failure is reported, never raised
        reachable = False
    if reachable is None:
        return DbStatus(
            status="unverified",
            configured=True,
            reachable=None,
            note="Supabase is configured; connectivity was not verified.",
        )
    if reachable:
        return DbStatus(
            status="ok",
            configured=True,
            reachable=True,
            note="The Supabase Data API answered the health probe.",
        )
    return DbStatus(
        status="unavailable",
        configured=True,
        reachable=False,
        note="Supabase is configured but the Data API was unreachable.",
    )


def make_db_probe(settings: Settings) -> DbProbe:
    """Build the default Data API probe used by the running application.

    Tests inject their own probe (or none), so the suite never touches the
    network. The publishable key is sent as ``apikey``; it is a project
    identifier, not a password and not a user credential.
    """

    async def probe() -> bool | None:
        if not settings.supabase_configured:
            return None
        url = f"{settings.supabase_url.rstrip('/')}/rest/v1/"
        timeout = min(settings.supabase_request_timeout, 3.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, headers={"apikey": settings.supabase_key})
        except httpx.HTTPError:
            return False
        return response.status_code < 500

    return probe


@router.get("/health", response_model=HealthResponse)
async def health(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    return HealthResponse(
        ok=True,
        db=await _db_status(settings, getattr(request.app.state, "db_probe", None)),
        gnani=GnaniStatus(
            configured=bool(settings.gnani_api_key),
            mock=settings.gnani_mock,
        ),
        llm=_llm_status(settings),
    )
