"""System endpoints.

``GET /api/health`` reports what is actually true right now. It does not probe
external services, so those providers are reported as *configured / not
configured* with ``healthy=None`` ("not probed"); only the deterministic local
``rules`` provider is reported healthy.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

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


def _provider(
    name: str, configured: bool, healthy: bool | None, note: str
) -> LlmProviderStatus:
    return LlmProviderStatus(
        name=name, configured=configured, healthy=healthy, note=note
    )


def _llm_status(settings: Settings) -> LlmStatus:
    registry = {
        "gemini": _provider(
            "gemini",
            configured=bool(settings.gemini_api_key),
            healthy=None,
            note="selected primary extraction provider; live integration is a later task",
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


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    db = DbStatus(
        status="not_initialized",
        path=settings.db_path,
        note="SQLite persistence is a later task (M-18); no database is opened here.",
    )
    return HealthResponse(
        ok=True,
        db=db,
        gnani=GnaniStatus(
            configured=bool(settings.gnani_api_key),
            mock=settings.gnani_mock,
        ),
        llm=_llm_status(settings),
    )
