"""Authenticated profile and recipe-management endpoints.

Identity always comes from the verified Supabase token. The Data API client is
built per request with that token, so ownership is enforced by RLS as well as by
the SQL functions' explicit ``auth.uid()`` checks.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..auth import AuthContext, get_auth_context
from ..config import Settings
from ..db import (
    DatabaseFailure,
    DatabaseUnavailable,
    DeleteResponse,
    InvalidPersonLink,
    ProfileResponse,
    RecipeCreateRequest,
    RecipeCreated,
    RecipeDetail,
    RecipeListResponse,
    RecipeNotFound,
    RecipeRepository,
    RecipeUpdateRequest,
    RecipeUpdated,
    build_user_client,
)
from ..dependencies import get_llm_provider_factory, get_settings
from ..errors import ApiError
from ..models import ErrorCode
from ..providers import ProviderError, StructuredLLMProvider

router = APIRouter(tags=["recipes"])


class TranslationResponse(BaseModel):
    translations: list[str]


class _TranslationsSchema(BaseModel):
    translations: list[str] = Field(min_length=1, max_length=100)


async def get_repository(
    settings: Settings = Depends(get_settings),
    auth: AuthContext = Depends(get_auth_context),
) -> AsyncIterator[RecipeRepository]:
    """Yield a request-scoped repository carrying this user's JWT."""
    try:
        client = build_user_client(settings, auth.access_token)
    except DatabaseUnavailable as exc:
        raise _database_unavailable() from exc
    try:
        yield RecipeRepository(client, auth.user.id)
    finally:
        await client.aclose()


@router.get("/me", response_model=ProfileResponse)
async def get_me(
    auth: AuthContext = Depends(get_auth_context),
    repository: RecipeRepository = Depends(get_repository),
) -> ProfileResponse:
    return await _call(repository.get_or_create_profile(auth.user.display_name))


@router.post("/recipes", response_model=RecipeCreated, status_code=201)
async def create_recipe(
    payload: RecipeCreateRequest,
    repository: RecipeRepository = Depends(get_repository),
) -> RecipeCreated:
    try:
        return await repository.create_recipe(payload)
    except InvalidPersonLink as exc:
        raise ApiError(
            status_code=422,
            code=ErrorCode.INVALID_INPUT,
            message=str(exc),
            hint="Cook/narrator person management is postponed; send null for both ids.",
        ) from exc


@router.get("/recipes", response_model=RecipeListResponse)
async def list_recipes(
    query: str | None = Query(default=None, max_length=200),
    tag: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    repository: RecipeRepository = Depends(get_repository),
) -> RecipeListResponse:
    return await _call(repository.list_recipes(query=query, tag=tag, limit=limit, offset=offset))


@router.get("/recipes/{recipe_id}", response_model=RecipeDetail)
async def get_recipe(
    recipe_id: UUID,
    repository: RecipeRepository = Depends(get_repository),
) -> RecipeDetail:
    return await _call(repository.get_recipe(str(recipe_id)))


@router.get("/recipes/{recipe_id}/translation", response_model=TranslationResponse)
async def translate_recipe_steps(
    recipe_id: UUID,
    repository: RecipeRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
    provider_factory: Callable[[Settings], StructuredLLMProvider] = Depends(get_llm_provider_factory),
) -> TranslationResponse:
    recipe = await _call(repository.get_recipe(str(recipe_id)))
    steps = recipe.draft.get("recipe", {}).get("steps", [])
    source_texts = [str(step.get("text", "")) for step in steps]
    if not source_texts:
        return TranslationResponse(translations=[])
    if not settings.gemini_api_key:
        raise ApiError(503, ErrorCode.LLM_UNAVAILABLE, "English translation is not configured.", "Keep the Bengali recipe visible or configure the translation provider.")
    try:
        provider = provider_factory(settings)
        result = await provider.generate(
            system_instruction=(
                "Translate each Bengali recipe step into clear, concise English. "
                "Preserve ingredients, quantities, order, and cooking meaning. "
                "Return exactly one translation per input step in the same order. "
                "Do not add instructions or facts."
            ),
            prompt=json.dumps({"steps": source_texts}, ensure_ascii=False),
            response_schema=_TranslationsSchema,
        )
    except ProviderError as exc:
        raise ApiError(503, ErrorCode.LLM_UNAVAILABLE, "English translation could not be loaded.", "Retry translation; the Bengali recipe is still available.") from exc
    translations = result.translations
    if len(translations) != len(source_texts) or any(not value.strip() for value in translations):
        raise ApiError(502, ErrorCode.UPSTREAM_ERROR, "English translation returned incomplete steps.", "Retry translation; the Bengali recipe is still available.")
    return TranslationResponse(translations=translations)


@router.put("/recipes/{recipe_id}", response_model=RecipeUpdated)
async def update_recipe(
    recipe_id: UUID,
    payload: RecipeUpdateRequest,
    repository: RecipeRepository = Depends(get_repository),
) -> RecipeUpdated:
    return await _call(
        repository.create_recipe_version(
            str(recipe_id),
            title=payload.title,
            tags=payload.tags,
            original_transcript=payload.original_transcript,
            draft=payload.draft,
        )
    )


@router.delete("/recipes/{recipe_id}", response_model=DeleteResponse)
async def delete_recipe(
    recipe_id: UUID,
    repository: RecipeRepository = Depends(get_repository),
) -> DeleteResponse:
    await _call(repository.delete_recipe(str(recipe_id)))
    return DeleteResponse(id=str(recipe_id))


async def _call(awaitable):
    """Map internal repository failures onto the documented error envelope."""
    try:
        return await awaitable
    except RecipeNotFound as exc:
        raise _not_found() from exc
    except InvalidPersonLink as exc:
        raise ApiError(
            status_code=422,
            code=ErrorCode.INVALID_INPUT,
            message=str(exc),
            hint="Cook/narrator person management is postponed; send null for both ids.",
        ) from exc
    except DatabaseUnavailable as exc:
        raise _database_unavailable() from exc
    except DatabaseFailure as exc:
        raise _database_failure() from exc


def _not_found() -> ApiError:
    return ApiError(
        status_code=404,
        code=ErrorCode.NOT_FOUND,
        message="Recipe not found.",
        hint="The recipe does not exist or is not owned by this account.",
    )


def _database_unavailable() -> ApiError:
    return ApiError(
        status_code=503,
        code=ErrorCode.UPSTREAM_BUSY,
        message="The recipe store is temporarily unavailable.",
        hint="Try again shortly.",
    )


def _database_failure() -> ApiError:
    return ApiError(
        status_code=502,
        code=ErrorCode.UPSTREAM_ERROR,
        message="The recipe store returned an error.",
        hint="No change is reported as successful.",
    )
