"""Request/response and row shapes for recipe persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _StrictRequest(BaseModel):
    """Reject unknown fields, including a client-supplied ownership id."""

    model_config = ConfigDict(extra="forbid")


class RecipeCreateRequest(_StrictRequest):
    title: str
    original_transcript: str
    draft: dict[str, Any]
    tags: list[str] = Field(default_factory=list)
    cook_person_id: str | None = None
    narrator_person_id: str | None = None

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be empty")
        return value

    @field_validator("original_transcript")
    @classmethod
    def _transcript_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("original_transcript must not be empty")
        return value

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, value: list[str]) -> list[str]:
        return [tag.strip() for tag in value if tag.strip()]


class RecipeUpdateRequest(_StrictRequest):
    title: str | None = None
    tags: list[str] | None = None
    original_transcript: str
    draft: dict[str, Any]

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("title must not be empty when supplied")
        return value

    @field_validator("original_transcript")
    @classmethod
    def _transcript_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("original_transcript must not be empty")
        return value

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [tag.strip() for tag in value if tag.strip()]


class RecipeCreated(BaseModel):
    id: str
    version: int


class RecipeUpdated(BaseModel):
    id: str
    version: int


class RecipeSummary(BaseModel):
    id: str
    title: str
    tags: list[str] = Field(default_factory=list)
    version: int
    created_at: datetime
    updated_at: datetime


class RecipeListResponse(BaseModel):
    items: list[RecipeSummary] = Field(default_factory=list)
    total: int


class RecipeDetail(BaseModel):
    id: str
    title: str
    version: int
    original_transcript: str
    draft: dict[str, Any]
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DeleteResponse(BaseModel):
    id: str
    deleted: bool = True


class ProfileResponse(BaseModel):
    id: str
    display_name: str | None = None
    created_at: datetime | None = None
