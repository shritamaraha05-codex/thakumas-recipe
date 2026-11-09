"""Request/response and row shapes for recipe media."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MediaRecord(BaseModel):
    """A validated ``public.recipe_media`` row (see ``0003_recipe_media.sql``).

    ``imagekit_file_path`` is the canonical path used to build signed URLs and to
    confirm the file lives under this user's recipe folder.
    """

    id: str
    recipe_id: str
    recipe_version_id: str | None = None
    media_type: str
    imagekit_file_id: str
    imagekit_url: str
    imagekit_file_path: str
    mime_type: str
    size_bytes: int
    original_filename: str | None = None
    created_at: datetime


class MediaCreateResponse(BaseModel):
    """The newly stored media metadata (never an ImageKit key or signed URL)."""

    id: str
    recipe_id: str
    recipe_version_id: str | None = None
    media_type: str
    mime_type: str
    size_bytes: int
    original_filename: str | None = None
    created_at: datetime


class MediaItem(BaseModel):
    """One media record for a listing, with a fresh short-lived delivery URL."""

    id: str
    recipe_version_id: str | None = None
    media_type: str
    mime_type: str
    size_bytes: int
    original_filename: str | None = None
    created_at: datetime
    delivery_url: str | None = None
    url_expires_in: int | None = None


class MediaListResponse(BaseModel):
    items: list[MediaItem] = Field(default_factory=list)
    total: int


class MediaUrlResponse(BaseModel):
    """A freshly generated signed delivery URL for one owned media record."""

    id: str
    delivery_url: str
    url_expires_in: int
