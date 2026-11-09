"""Owner-scoped recipe repository.

Every call passes the verified ``owner_user_id`` and the SQL functions check it
against ``auth.uid()`` before doing anything. The Data API client also carries
the user's access token, so RLS enforces the same rule independently.
"""

from __future__ import annotations

from typing import Any

from .client import MediaClient, RpcClient
from .errors import DatabaseFailure, InvalidPersonLink, RecipeNotFound
from .schemas import (
    ProfileResponse,
    RecipeCreateRequest,
    RecipeCreated,
    RecipeDetail,
    RecipeListResponse,
    RecipeUpdated,
)


class RecipeRepository:
    def __init__(self, client: RpcClient, owner_user_id: str) -> None:
        self._client = client
        self._owner = owner_user_id

    async def get_or_create_profile(self, display_name: str | None) -> ProfileResponse:
        data = await self._client.rpc(
            "get_or_create_profile",
            {"p_owner_user_id": self._owner, "p_display_name": display_name},
        )
        return ProfileResponse.model_validate(_mapping(data))

    async def create_recipe(self, request: RecipeCreateRequest) -> RecipeCreated:
        _reject_person_links(request.cook_person_id, request.narrator_person_id)
        data = await self._client.rpc(
            "create_recipe_with_version",
            {
                "p_owner_user_id": self._owner,
                "p_title": request.title,
                "p_original_transcript": request.original_transcript,
                "p_draft": request.draft,
                "p_tags": request.tags,
            },
        )
        return RecipeCreated.model_validate(_mapping(data))

    async def list_recipes(
        self,
        *,
        query: str | None = None,
        tag: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RecipeListResponse:
        data = await self._client.rpc(
            "list_recipes",
            {
                "p_owner_user_id": self._owner,
                "p_query": query or None,
                "p_tag": tag or None,
                "p_limit": limit,
                "p_offset": offset,
            },
        )
        return RecipeListResponse.model_validate(_mapping(data))

    async def get_recipe(
        self, recipe_id: str, *, version_number: int | None = None
    ) -> RecipeDetail:
        if version_number is None:
            data = await self._client.rpc(
                "get_recipe_detail",
                {"p_owner_user_id": self._owner, "p_recipe_id": recipe_id},
            )
        else:
            data = await self._client.rpc(
                "get_recipe_version",
                {
                    "p_owner_user_id": self._owner,
                    "p_recipe_id": recipe_id,
                    "p_version_number": version_number,
                },
            )
        if data is None:
            raise RecipeNotFound(recipe_id)
        return RecipeDetail.model_validate(_mapping(data))

    async def get_recipe_version(self, recipe_id: str, version_number: int) -> RecipeDetail:
        return await self.get_recipe(recipe_id, version_number=version_number)

    async def create_recipe_version(
        self,
        recipe_id: str,
        *,
        title: str | None,
        tags: list[str] | None,
        original_transcript: str,
        draft: dict[str, Any],
    ) -> RecipeUpdated:
        data = await self._client.rpc(
            "add_recipe_version",
            {
                "p_owner_user_id": self._owner,
                "p_recipe_id": recipe_id,
                "p_title": title,
                "p_tags": tags,
                "p_original_transcript": original_transcript,
                "p_draft": draft,
            },
        )
        if data is None:
            raise RecipeNotFound(recipe_id)
        return RecipeUpdated.model_validate(_mapping(data))

    async def delete_recipe(self, recipe_id: str) -> None:
        deleted = await self._client.rpc(
            "delete_recipe",
            {"p_owner_user_id": self._owner, "p_recipe_id": recipe_id},
        )
        if deleted is not True:
            raise RecipeNotFound(recipe_id)


class RecipeMediaRepository:
    """Owner-scoped access to ``public.recipe_media`` (see 0003_recipe_media.sql).

    Every query runs through the caller's authenticated Data API client, so RLS
    restricts rows to recipes the verified user owns. The repository never sends
    ``owner_user_id``: ownership is enforced by the database policy.
    """

    def __init__(self, client: MediaClient) -> None:
        self._client = client

    async def recipe_exists(self, recipe_id: str) -> bool:
        """True only if the recipe is visible to the authenticated user."""
        rows = await self._client.select(
            "recipes", columns="id", filters={"id": recipe_id}, limit=1
        )
        return bool(rows)

    async def current_version_id(self, recipe_id: str) -> str | None:
        """The UUID of the newest version, or ``None`` when no version exists.

        The RPCs expose only the numeric ``version_number``; the media table
        needs the version UUID, so it is read from ``recipe_versions`` directly
        under the user's own token (RLS applies).
        """
        rows = await self._client.select(
            "recipe_versions",
            columns="id",
            filters={"recipe_id": recipe_id},
            orders=[("version_number", True)],
            limit=1,
        )
        return str(rows[0]["id"]) if rows else None

    async def insert_media(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = await self._client.insert("recipe_media", row)
        return _mapping(rows)

    async def list_media(self, recipe_id: str) -> list[dict[str, Any]]:
        return await self._client.select(
            "recipe_media",
            columns="*",
            filters={"recipe_id": recipe_id},
            orders=[("created_at", True), ("id", True)],
        )

    async def get_media(self, recipe_id: str, media_id: str) -> dict[str, Any] | None:
        rows = await self._client.select(
            "recipe_media",
            columns="*",
            filters={"id": media_id, "recipe_id": recipe_id},
            limit=1,
        )
        return rows[0] if rows else None

    async def delete_media(self, recipe_id: str, media_id: str) -> bool:
        rows = await self._client.delete(
            "recipe_media", filters={"id": media_id, "recipe_id": recipe_id}
        )
        return bool(rows)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
        return value[0]
    if isinstance(value, dict):
        return value
    raise DatabaseFailure("The database returned an unexpected response.")


def _reject_person_links(cook_person_id: str | None, narrator_person_id: str | None) -> None:
    if cook_person_id is None and narrator_person_id is None:
        return
    raise InvalidPersonLink(
        "Person linking is not implemented yet; cook_person_id and narrator_person_id must be null."
    )
