"""Authenticated recipe media endpoints (ImageKit + Supabase metadata).

Identity always comes from the verified Supabase token. The ImageKit folder is
derived from that identity, never from the request. The Data API client is built
per request with the user's own token, so RLS restricts media rows to recipes
the user owns.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from ..auth import AuthContext, get_auth_context
from ..config import Settings
from ..db import (
    DatabaseFailure,
    DatabaseUnavailable,
    DeleteResponse,
    RecipeMediaRepository,
    RecipeNotFound,
    build_user_client,
)
from ..dependencies import get_settings
from ..errors import ApiError
from ..media import (
    InvalidMediaType,
    MediaConsistencyError,
    MediaCreateResponse,
    MediaListResponse,
    MediaNotFound,
    MediaService,
    MediaStorage,
    MediaStorageFailure,
    MediaStorageUnavailable,
    MediaTooLarge,
    MediaUrlResponse,
    UnsupportedMediaType,
)
from ..models import ErrorCode

router = APIRouter(tags=["media"])


async def get_media_repository(
    settings: Settings = Depends(get_settings),
    auth: AuthContext = Depends(get_auth_context),
) -> AsyncIterator[RecipeMediaRepository]:
    """Yield a request-scoped media repository carrying this user's JWT."""
    try:
        client = build_user_client(settings, auth.access_token)
    except DatabaseUnavailable as exc:
        raise ApiError(
            status_code=503,
            code=ErrorCode.UPSTREAM_BUSY,
            message="The recipe store is temporarily unavailable.",
            hint="Try again shortly.",
        ) from exc
    try:
        yield RecipeMediaRepository(client)
    finally:
        await client.aclose()


def get_media_storage(request: Request) -> MediaStorage:
    """The storage adapter attached to the app (tests inject a fake)."""
    return request.app.state.media_storage


def get_media_service(
    repository: RecipeMediaRepository = Depends(get_media_repository),
    storage: MediaStorage = Depends(get_media_storage),
    settings: Settings = Depends(get_settings),
) -> MediaService:
    return MediaService(
        repository=repository,
        storage=storage,
        signed_url_ttl_seconds=settings.imagekit_signed_url_ttl_seconds,
        max_image_upload_mb=settings.imagekit_max_image_upload_mb,
        max_audio_upload_mb=settings.imagekit_max_audio_upload_mb,
    )


@router.post("/recipes/{recipe_id}/media", response_model=MediaCreateResponse, status_code=201)
async def upload_media(
    recipe_id: UUID,
    media_type: str = Form(...),
    file: UploadFile = File(...),
    auth: AuthContext = Depends(get_auth_context),
    service: MediaService = Depends(get_media_service),
) -> MediaCreateResponse:
    """Upload one private image or audio file against an owned recipe."""
    return await _run(
        service.upload(
            recipe_id=str(recipe_id),
            owner_id=auth.user.id,
            media_type=media_type,
            upload=file,
        )
    )


@router.get("/recipes/{recipe_id}/media", response_model=MediaListResponse)
async def list_media(
    recipe_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: MediaService = Depends(get_media_service),
) -> MediaListResponse:
    """List owned media with fresh short-lived signed delivery URLs."""
    return await _run(service.list_media(recipe_id=str(recipe_id), owner_id=auth.user.id))


@router.get(
    "/recipes/{recipe_id}/media/{media_id}/url",
    response_model=MediaUrlResponse,
)
async def get_media_url(
    recipe_id: UUID,
    media_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: MediaService = Depends(get_media_service),
) -> MediaUrlResponse:
    """Return a newly generated signed URL for one owned media record."""
    return await _run(
        service.signed_url(
            recipe_id=str(recipe_id),
            media_id=str(media_id),
            owner_id=auth.user.id,
        )
    )


@router.delete("/recipes/{recipe_id}/media/{media_id}", response_model=DeleteResponse)
async def delete_media(
    recipe_id: UUID,
    media_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: MediaService = Depends(get_media_service),
) -> DeleteResponse:
    """Delete the ImageKit file first, then its metadata row."""
    return await _run(
        service.delete_media(
            recipe_id=str(recipe_id),
            media_id=str(media_id),
            owner_id=auth.user.id,
        )
    )


async def _run(awaitable):
    """Map media domain failures onto the documented error envelope."""
    try:
        return await awaitable
    except RecipeNotFound as exc:
        raise _not_found("Recipe not found.") from exc
    except MediaNotFound as exc:
        raise _not_found("Media not found.") from exc
    except MediaConsistencyError as exc:
        raise ApiError(
            status_code=502,
            code=ErrorCode.UPSTREAM_ERROR,
            message=str(exc),
            hint="Retry the request; deleting the file again is safe.",
        ) from exc
    except MediaStorageUnavailable as exc:
        raise ApiError(
            status_code=503,
            code=ErrorCode.UPSTREAM_BUSY,
            message=str(exc) or "Media storage is unavailable.",
            hint="Set IMAGEKIT_PRIVATE_KEY and IMAGEKIT_URL_ENDPOINT on the backend.",
        ) from exc
    except MediaStorageFailure as exc:
        raise ApiError(
            status_code=502,
            code=ErrorCode.UPSTREAM_ERROR,
            message=str(exc) or "Media storage returned an error.",
            hint="No media was saved.",
        ) from exc
    except MediaTooLarge as exc:
        raise ApiError(
            status_code=413,
            code=ErrorCode.FILE_TOO_LARGE,
            message=str(exc),
            hint="Reduce the file size and try again.",
        ) from exc
    except UnsupportedMediaType as exc:
        raise ApiError(
            status_code=415,
            code=ErrorCode.UNSUPPORTED_MEDIA_TYPE,
            message=str(exc),
            hint="Send a supported image (JPEG/PNG/WEBP) or audio file.",
        ) from exc
    except InvalidMediaType as exc:
        raise ApiError(
            status_code=422,
            code=ErrorCode.INVALID_INPUT,
            message=str(exc),
            hint="Send media_type as 'audio' or 'image'.",
        ) from exc
    except DatabaseUnavailable as exc:
        raise ApiError(
            status_code=503,
            code=ErrorCode.UPSTREAM_BUSY,
            message="The recipe store is temporarily unavailable.",
            hint="Try again shortly.",
        ) from exc
    except DatabaseFailure as exc:
        raise ApiError(
            status_code=502,
            code=ErrorCode.UPSTREAM_ERROR,
            message="The recipe store returned an error.",
            hint="No change is reported as successful.",
        ) from exc


def _not_found(message: str) -> ApiError:
    return ApiError(
        status_code=404,
        code=ErrorCode.NOT_FOUND,
        message=message,
        hint="It does not exist or is not owned by this account.",
    )
