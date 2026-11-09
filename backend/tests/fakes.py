"""Offline fakes for auth and database tests.

No fake here reaches the network. ``FakeRpcClient`` mirrors the SQL functions'
ownership rules in memory so repository/API tests can exercise the real
repository code without a Supabase project.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI

from backend.app.auth import (
    AuthenticatedUser,
    AuthContext,
    TokenVerificationError,
    get_auth_context,
)
from backend.app.config import Settings
from backend.app.db import DatabaseFailure, RecipeMediaRepository, RecipeRepository
from backend.app.main import create_app
from backend.app.media import MediaStorage, UploadedAsset
from backend.app.routers.media import get_media_repository
from backend.app.routers.recipes import get_repository


class FakeTokenVerifier:
    def __init__(
        self,
        users: dict[str, AuthenticatedUser] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.users = users or {}
        self.error = error
        self.calls: list[str] = []

    async def verify(self, token: str) -> AuthenticatedUser:
        self.calls.append(token)
        if self.error is not None:
            raise self.error
        try:
            return self.users[token]
        except KeyError as exc:
            raise TokenVerificationError("unknown test token") from exc


def make_user(
    user_id: str,
    *,
    email: str | None = None,
    name: str | None = None,
) -> AuthenticatedUser:
    metadata: dict[str, Any] = {}
    if name:
        metadata["full_name"] = name
    return AuthenticatedUser(
        id=user_id,
        email=email,
        role="authenticated",
        user_metadata=metadata,
    )


def _sort_value(value: Any) -> Any:
    """Typing helper: the fake only orders by same-typed, non-null columns."""
    return value


class FakeStore:
    """Shared in-memory data for two simulated users."""

    def __init__(self) -> None:
        self.profiles: dict[str, dict[str, Any]] = {}
        self.recipes: dict[str, dict[str, Any]] = {}
        self.versions: dict[str, list[dict[str, Any]]] = {}
        self.media: dict[str, dict[str, Any]] = {}
        self.media_insert_error: Exception | None = None
        self.media_delete_error: Exception | None = None
        self._clock = 0

    def now(self) -> str:
        self._clock += 1
        return (
            datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=self._clock)
        ).isoformat()


class FakeRpcClient:
    """A parameterised RPC stub that enforces ``auth.uid()`` ownership."""

    def __init__(self, store: FakeStore, auth_uid: str) -> None:
        self.store = store
        self.auth_uid = auth_uid
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True

    async def rpc(self, function: str, params: dict[str, Any]) -> Any:
        self.calls.append((function, copy.deepcopy(params)))
        if params.get("p_owner_user_id") != self.auth_uid:
            raise AssertionError("the repository passed an owner other than the verified user")
        handler = getattr(self, f"_rpc_{function}", None)
        if handler is None:
            raise AssertionError(f"unexpected RPC {function!r}")
        return handler(params)

    def _owned_recipe(self, recipe_id: str) -> dict[str, Any] | None:
        recipe = self.store.recipes.get(recipe_id)
        if recipe is None or recipe["owner_user_id"] != self.auth_uid:
            return None
        return recipe

    def _rpc_get_or_create_profile(self, params: dict[str, Any]) -> dict[str, Any]:
        profile = self.store.profiles.get(self.auth_uid)
        if profile is None:
            profile = {
                "id": self.auth_uid,
                "display_name": params.get("p_display_name"),
                "created_at": self.store.now(),
            }
            self.store.profiles[self.auth_uid] = profile
        return copy.deepcopy(profile)

    def _rpc_create_recipe_with_version(self, params: dict[str, Any]) -> dict[str, Any]:
        recipe_id = str(uuid4())
        created = self.store.now()
        recipe = {
            "id": recipe_id,
            "owner_user_id": self.auth_uid,
            "title": params["p_title"].strip(),
            "tags": list(params.get("p_tags") or []),
            "created_at": created,
            "updated_at": created,
        }
        self.store.recipes[recipe_id] = recipe
        self.store.versions[recipe_id] = [
            {
                "id": str(uuid4()),
                "recipe_id": recipe_id,
                "version_number": 1,
                "original_transcript": params["p_original_transcript"],
                "draft": copy.deepcopy(params["p_draft"]),
                "created_at": created,
            }
        ]
        return {"id": recipe_id, "version": 1}

    def _rpc_add_recipe_version(self, params: dict[str, Any]) -> dict[str, Any] | None:
        recipe = self._owned_recipe(params["p_recipe_id"])
        if recipe is None:
            return None
        versions = self.store.versions.setdefault(recipe["id"], [])
        next_number = max((v["version_number"] for v in versions), default=0) + 1
        created = self.store.now()
        versions.append(
            {
                "id": str(uuid4()),
                "recipe_id": recipe["id"],
                "version_number": next_number,
                "original_transcript": params["p_original_transcript"],
                "draft": copy.deepcopy(params["p_draft"]),
                "created_at": created,
            }
        )
        if params.get("p_title") and params["p_title"].strip():
            recipe["title"] = params["p_title"].strip()
        if params.get("p_tags") is not None:
            recipe["tags"] = list(params["p_tags"])
        recipe["updated_at"] = created
        return {"id": recipe["id"], "version": next_number}

    def _detail(self, recipe: dict[str, Any], version: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": recipe["id"],
            "title": recipe["title"],
            "version": version["version_number"],
            "original_transcript": version["original_transcript"],
            "draft": copy.deepcopy(version["draft"]),
            "tags": list(recipe["tags"]),
            "created_at": recipe["created_at"],
            "updated_at": recipe["updated_at"],
        }

    def _rpc_get_recipe_detail(self, params: dict[str, Any]) -> dict[str, Any] | None:
        recipe = self._owned_recipe(params["p_recipe_id"])
        if recipe is None:
            return None
        versions = self.store.versions.get(recipe["id"], [])
        if not versions:
            return None
        latest = max(versions, key=lambda version: version["version_number"])
        return self._detail(recipe, latest)

    def _rpc_get_recipe_version(self, params: dict[str, Any]) -> dict[str, Any] | None:
        recipe = self._owned_recipe(params["p_recipe_id"])
        if recipe is None:
            return None
        for version in self.store.versions.get(recipe["id"], []):
            if version["version_number"] == params["p_version_number"]:
                return self._detail(recipe, version)
        return None

    def _rpc_list_recipes(self, params: dict[str, Any]) -> dict[str, Any]:
        query = (params.get("p_query") or "").lower()
        tag = params.get("p_tag")
        owned = [
            recipe
            for recipe in self.store.recipes.values()
            if recipe["owner_user_id"] == self.auth_uid
        ]
        filtered = [
            recipe
            for recipe in owned
            if (not query or query in recipe["title"].lower())
            and (not tag or tag in recipe["tags"])
        ]
        filtered.sort(key=lambda recipe: (recipe["created_at"], recipe["id"]), reverse=True)
        total = len(filtered)
        limit = max(1, min(int(params.get("p_limit") or 50), 100))
        offset = max(0, int(params.get("p_offset") or 0))
        items = []
        for recipe in filtered[offset : offset + limit]:
            versions = self.store.versions.get(recipe["id"], [])
            latest = max((version["version_number"] for version in versions), default=0)
            items.append(
                {
                    "id": recipe["id"],
                    "title": recipe["title"],
                    "tags": list(recipe["tags"]),
                    "version": latest,
                    "created_at": recipe["created_at"],
                    "updated_at": recipe["updated_at"],
                }
            )
        return {"items": items, "total": total}

    def _rpc_delete_recipe(self, params: dict[str, Any]) -> bool:
        recipe = self._owned_recipe(params["p_recipe_id"])
        if recipe is None:
            return False
        del self.store.recipes[recipe["id"]]
        self.store.versions.pop(recipe["id"], None)
        return True


class FakeMediaClient:
    """In-memory ``recipe_media`` table that enforces RLS-like ownership."""

    def __init__(self, store: FakeStore, auth_uid: str) -> None:
        self.store = store
        self.auth_uid = auth_uid
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True

    def _owned_recipe_ids(self) -> set[str]:
        return {
            recipe["id"]
            for recipe in self.store.recipes.values()
            if recipe["owner_user_id"] == self.auth_uid
        }

    async def select(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: dict[str, Any] | None = None,
        orders: Sequence[tuple[str, bool]] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        owned = self._owned_recipe_ids()
        if table == "recipes":
            rows = [r for r in self.store.recipes.values() if r["id"] in owned]
        elif table == "recipe_versions":
            rows = [
                version
                for recipe_id, versions in self.store.versions.items()
                if recipe_id in owned
                for version in versions
            ]
        elif table == "recipe_media":
            rows = [m for m in self.store.media.values() if m["recipe_id"] in owned]
        else:
            raise AssertionError(f"unexpected table {table!r}")

        for column, value in (filters or {}).items():
            rows = [row for row in rows if row.get(column) == value]
        for column, descending in reversed(orders or ()):
            rows.sort(key=lambda row: _sort_value(row.get(column)), reverse=descending)
        if limit is not None:
            rows = rows[:limit]
        return copy.deepcopy(rows)

    async def insert(self, table: str, row: dict[str, Any]) -> list[dict[str, Any]]:
        if table != "recipe_media":
            raise AssertionError(f"unexpected table {table!r}")
        if self.store.media_insert_error is not None:
            raise self.store.media_insert_error
        if row["recipe_id"] not in self._owned_recipe_ids():
            raise AssertionError("insert into a recipe not owned by the caller")
        if any(
            media["imagekit_file_id"] == row["imagekit_file_id"]
            for media in self.store.media.values()
        ):
            raise DatabaseFailure("duplicate imagekit file id")
        media_id = row.get("id") or str(uuid4())
        record = {**copy.deepcopy(row), "id": media_id, "created_at": self.store.now()}
        self.store.media[media_id] = record
        return [copy.deepcopy(record)]

    async def delete(self, table: str, *, filters: dict[str, Any]) -> list[dict[str, Any]]:
        if table != "recipe_media":
            raise AssertionError(f"unexpected table {table!r}")
        if self.store.media_delete_error is not None:
            raise self.store.media_delete_error
        owned = self._owned_recipe_ids()
        matched = [
            media
            for media in self.store.media.values()
            if media["recipe_id"] in owned
            and all(media.get(column) == value for column, value in filters.items())
        ]
        for media in matched:
            self.store.media.pop(media["id"], None)
        return copy.deepcopy(matched)


class FakeMediaStorage:
    """In-memory ImageKit replacement; records every upload/delete/sign call."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        upload_error: Exception | None = None,
        delete_error: Exception | None = None,
        base_url: str = "https://ik.imagekit.io/test",
    ) -> None:
        self._enabled = enabled
        self.upload_error = upload_error
        self.delete_error = delete_error
        self.base_url = base_url.rstrip("/")
        self.uploads: list[dict[str, Any]] = []
        self.deleted: list[str] = []
        self.signed: list[tuple[str, int]] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def upload_private(self, *, content: bytes, file_name: str, folder: str) -> UploadedAsset:
        if self.upload_error is not None:
            raise self.upload_error
        file_id = f"file_{len(self.uploads) + 1}"
        file_path = f"{folder}/{file_name}"
        self.uploads.append(
            {
                "content": content,
                "file_name": file_name,
                "folder": folder,
                "file_path": file_path,
            }
        )
        return UploadedAsset(
            file_id=file_id,
            url=f"{self.base_url}{file_path}",
            file_path=file_path,
            name=file_name,
            size=len(content),
        )

    async def delete_file(self, file_id: str) -> None:
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted.append(file_id)

    async def build_signed_url(self, *, file_path: str, expires_in: int) -> str:
        self.signed.append((file_path, expires_in))
        return f"{self.base_url}{file_path}?ik-t=1&ik-s=test&ttl={expires_in}"

    async def aclose(self) -> None:
        return None


def build_test_app(
    settings: Settings,
    verifier: FakeTokenVerifier,
    store: FakeStore,
    media_storage: MediaStorage | None = None,
) -> FastAPI:
    storage = media_storage if media_storage is not None else FakeMediaStorage()
    app = create_app(settings, token_verifier=verifier, media_storage=storage)

    def override_repository(
        auth: AuthContext = Depends(get_auth_context),
    ) -> RecipeRepository:
        return RecipeRepository(FakeRpcClient(store, auth.user.id), auth.user.id)

    def override_media_repository(
        auth: AuthContext = Depends(get_auth_context),
    ) -> RecipeMediaRepository:
        return RecipeMediaRepository(FakeMediaClient(store, auth.user.id))

    app.dependency_overrides[get_repository] = override_repository
    app.dependency_overrides[get_media_repository] = override_media_repository
    return app


def repository_for(store: FakeStore, user_id: str) -> RecipeRepository:
    return RecipeRepository(FakeRpcClient(store, user_id), user_id)
