"""Media orchestration between ImageKit storage and Supabase metadata.

This module owns the two-system consistency rules:

* never insert metadata unless the ImageKit upload succeeded;
* if the metadata insert fails after an upload, best-effort delete the file;
* never delete metadata unless the ImageKit delete succeeded;
* if the metadata delete fails after a file delete, report it so the request
  can be retried (the ImageKit delete is idempotent).

The router is a thin adapter: it authenticates, then calls this service.
"""

from __future__ import annotations

import logging

from backend.app.db import (
    DatabaseFailure,
    DatabaseUnavailable,
    RecipeMediaRepository,
    RecipeNotFound,
)
from backend.app.db.schemas import DeleteResponse

from .errors import (
    InvalidMediaType,
    MediaConsistencyError,
    MediaNotFound,
    MediaStorageFailure,
    MediaStorageUnavailable,
)
from .imagekit_service import MediaStorage
from .schemas import (
    MediaCreateResponse,
    MediaItem,
    MediaListResponse,
    MediaRecord,
    MediaUrlResponse,
)
from .validation import (
    MIB,
    MEDIA_TYPES,
    ReadableUpload,
    read_bounded,
    sanitise_filename,
    server_filename,
    validate_upload,
)

logger = logging.getLogger(__name__)


class MediaService:
    """Per-request media operations scoped to one verified user."""

    def __init__(
        self,
        *,
        repository: RecipeMediaRepository,
        storage: MediaStorage,
        signed_url_ttl_seconds: int = 900,
        max_image_upload_mb: int = 8,
        max_audio_upload_mb: int = 25,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._ttl = max(1, signed_url_ttl_seconds)
        self._max_image_bytes = max(1, max_image_upload_mb) * MIB
        self._max_audio_bytes = max(1, max_audio_upload_mb) * MIB

    async def upload(
        self,
        *,
        recipe_id: str,
        owner_id: str,
        media_type: str,
        upload: ReadableUpload,
    ) -> MediaCreateResponse:
        self._require_storage()
        if media_type not in MEDIA_TYPES:
            raise InvalidMediaType("media_type must be 'audio' or 'image'.")
        if not await self._repository.recipe_exists(recipe_id):
            raise RecipeNotFound(recipe_id)

        version_id = await self._repository.current_version_id(recipe_id)
        max_bytes = self._max_image_bytes if media_type == "image" else self._max_audio_bytes
        content = await read_bounded(upload, max_bytes)
        validated = validate_upload(
            media_type=media_type,
            content_type=upload.content_type,
            content=content,
            max_image_bytes=self._max_image_bytes,
            max_audio_bytes=self._max_audio_bytes,
        )

        folder = self._folder(owner_id, recipe_id, media_type)
        file_name = server_filename(validated.family)
        asset = await self._storage.upload_private(
            content=content, file_name=file_name, folder=folder
        )
        if not asset.file_path.startswith(f"{folder}/"):
            await self._compensate_delete(asset.file_id)
            raise MediaStorageFailure("Media storage returned an unexpected file path.")

        row = {
            "recipe_id": recipe_id,
            "recipe_version_id": version_id,
            "media_type": media_type,
            "imagekit_file_id": asset.file_id,
            "imagekit_url": asset.url,
            "imagekit_file_path": asset.file_path,
            "mime_type": validated.mime_type,
            "size_bytes": validated.size_bytes,
            "original_filename": sanitise_filename(upload.filename),
        }
        try:
            saved = await self._repository.insert_media(row)
        except (DatabaseUnavailable, DatabaseFailure):
            await self._compensate_delete(asset.file_id)
            raise

        record = MediaRecord.model_validate(saved)
        return MediaCreateResponse(
            id=record.id,
            recipe_id=record.recipe_id,
            recipe_version_id=record.recipe_version_id,
            media_type=record.media_type,
            mime_type=record.mime_type,
            size_bytes=record.size_bytes,
            original_filename=record.original_filename,
            created_at=record.created_at,
        )

    async def list_media(self, *, recipe_id: str, owner_id: str) -> MediaListResponse:
        self._require_storage()
        if not await self._repository.recipe_exists(recipe_id):
            raise RecipeNotFound(recipe_id)

        items: list[MediaItem] = []
        for row in await self._repository.list_media(recipe_id):
            record = MediaRecord.model_validate(row)
            delivery_url = None
            expires_in = None
            if self._path_matches(record.imagekit_file_path, owner_id, recipe_id):
                delivery_url = await self._storage.build_signed_url(
                    file_path=record.imagekit_file_path, expires_in=self._ttl
                )
                expires_in = self._ttl
            items.append(_item(record, delivery_url, expires_in))
        return MediaListResponse(items=items, total=len(items))

    async def signed_url(self, *, recipe_id: str, media_id: str, owner_id: str) -> MediaUrlResponse:
        self._require_storage()
        record = await self._owned_record(recipe_id, media_id, owner_id)
        url = await self._storage.build_signed_url(
            file_path=record.imagekit_file_path, expires_in=self._ttl
        )
        return MediaUrlResponse(id=record.id, delivery_url=url, url_expires_in=self._ttl)

    async def delete_media(self, *, recipe_id: str, media_id: str, owner_id: str) -> DeleteResponse:
        self._require_storage()
        record = await self._owned_record(recipe_id, media_id, owner_id)

        # If this raises, the metadata row is kept and the request can be retried.
        await self._storage.delete_file(record.imagekit_file_id)

        message = (
            "The media file was removed but its metadata could not be deleted. "
            "Retry the request to finish cleanup."
        )
        try:
            metadata_deleted = await self._repository.delete_media(recipe_id, media_id)
        except (DatabaseUnavailable, DatabaseFailure) as exc:
            # The ImageKit delete already succeeded; surface this as a recoverable
            # consistency error rather than a generic database failure.
            raise MediaConsistencyError(message) from exc
        if not metadata_deleted:
            raise MediaConsistencyError(message)
        return DeleteResponse(id=media_id, deleted=True)

    async def _owned_record(self, recipe_id: str, media_id: str, owner_id: str) -> MediaRecord:
        if not await self._repository.recipe_exists(recipe_id):
            raise RecipeNotFound(recipe_id)
        row = await self._repository.get_media(recipe_id, media_id)
        if row is None:
            raise MediaNotFound(media_id)
        record = MediaRecord.model_validate(row)
        if record.recipe_id != recipe_id or not self._path_matches(
            record.imagekit_file_path, owner_id, recipe_id
        ):
            raise MediaNotFound(media_id)
        return record

    def _require_storage(self) -> None:
        if not self._storage.enabled:
            raise MediaStorageUnavailable("Media storage is not configured.")

    async def _compensate_delete(self, file_id: str) -> None:
        try:
            await self._storage.delete_file(file_id)
        except Exception:  # noqa: BLE001 - best effort; never mask the first error
            logger.warning("Could not remove an orphaned media file after a database error.")

    @staticmethod
    def _folder(owner_id: str, recipe_id: str, media_type: str) -> str:
        subfolder = "audio" if media_type == "audio" else "images"
        return f"/users/{owner_id}/recipes/{recipe_id}/{subfolder}"

    @staticmethod
    def _expected_prefix(owner_id: str, recipe_id: str) -> str:
        return f"/users/{owner_id}/recipes/{recipe_id}/"

    def _path_matches(self, path: str, owner_id: str, recipe_id: str) -> bool:
        return path.startswith(self._expected_prefix(owner_id, recipe_id))


def _item(record: MediaRecord, delivery_url: str | None, expires_in: int | None) -> MediaItem:
    return MediaItem(
        id=record.id,
        recipe_version_id=record.recipe_version_id,
        media_type=record.media_type,
        mime_type=record.mime_type,
        size_bytes=record.size_bytes,
        original_filename=record.original_filename,
        created_at=record.created_at,
        delivery_url=delivery_url,
        url_expires_in=expires_in,
    )
