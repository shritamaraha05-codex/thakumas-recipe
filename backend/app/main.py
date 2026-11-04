"""FastAPI application factory.

Start locally with::

    uvicorn backend.app.main:app --reload

Interactive documentation is served at ``/docs`` and the OpenAPI schema at
``/openapi.json``.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import __version__
from .config import Settings, get_settings
from .models import ErrorCode, ErrorDetail, ErrorResponse
from .routers import health, parse


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application.

    Passing ``settings`` keeps the app testable and credential-free: tests can
    construct it with explicit values instead of touching the environment.
    """
    resolved = settings if settings is not None else get_settings()

    app = FastAPI(title=resolved.app_name, version=__version__)
    app.state.settings = resolved

    app.include_router(health.router, prefix=resolved.api_prefix)
    app.include_router(parse.router, prefix=resolved.api_prefix)

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

    return app


app = create_app()
