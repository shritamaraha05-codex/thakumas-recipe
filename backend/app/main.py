"""FastAPI application factory.

Start locally with::

    uvicorn backend.app.main:app --reload

Interactive documentation is served at ``/docs`` and the OpenAPI schema at
``/openapi.json``.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .auth import SupabaseTokenVerifier, TokenVerifier
from .config import Settings, get_settings
from .errors import ApiError
from .media import ImageKitMediaStorage, MediaStorage
from .models import ErrorCode, ErrorDetail, ErrorResponse
from .providers import StructuredLLMProvider
from .routers import health, media, parse, recipes
from .routers.health import DbProbe, make_db_probe


def _default_provider_factory(settings: Settings) -> StructuredLLMProvider:
    """Build the configured LLM provider (imported lazily; no client yet)."""
    from .providers.gemini import build_provider

    return build_provider(settings)


def create_app(
    settings: Settings | None = None,
    llm_provider_factory: Callable[[Settings], StructuredLLMProvider] | None = None,
    token_verifier: TokenVerifier | None = None,
    db_probe: DbProbe | None = None,
    media_storage: MediaStorage | None = None,
) -> FastAPI:
    """Build the application.

    Passing ``settings`` keeps the app testable and credential-free: tests can
    construct it with explicit values instead of touching the environment.
    ``llm_provider_factory`` lets tests inject a fake provider; the default only
    ever builds a real client when an LLM parser is selected. ``token_verifier``
    and ``db_probe`` are injection points for offline auth/database tests.
    """
    resolved = settings if settings is not None else get_settings()

    app = FastAPI(title=resolved.app_name, version=__version__)
    app.state.settings = resolved
    app.state.llm_provider_factory = llm_provider_factory or _default_provider_factory
    app.state.token_verifier = token_verifier or SupabaseTokenVerifier.from_settings(resolved)
    app.state.db_probe = db_probe
    # ImageKit stays optional: the adapter is cheap to build and imports the SDK
    # lazily, so missing credentials never prevent startup.
    app.state.media_storage = media_storage or ImageKitMediaStorage.from_settings(resolved)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.frontend_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(health.router, prefix=resolved.api_prefix)
    app.include_router(parse.router, prefix=resolved.api_prefix)
    app.include_router(recipes.router, prefix=resolved.api_prefix)
    app.include_router(media.router, prefix=resolved.api_prefix)

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        detail = ErrorDetail(
            code=ErrorCode.INVALID_INPUT,
            message="Request validation failed.",
            hint="Check the request body against the documented schema in docs/04_API.md.",
        )
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(error=detail).model_dump(mode="json"),
        )

    @app.exception_handler(ApiError)
    async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        detail = ErrorDetail(code=exc.code, message=exc.message, hint=exc.hint)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error=detail).model_dump(mode="json"),
        )

    return app


_startup_settings = get_settings()
app = create_app(_startup_settings, db_probe=make_db_probe(_startup_settings))
