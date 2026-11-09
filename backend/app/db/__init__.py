"""Owner-scoped Supabase Data API access."""

from __future__ import annotations

from .client import MediaClient, PostgrestRpcClient, RpcClient, build_user_client
from .errors import DatabaseFailure, DatabaseUnavailable, InvalidPersonLink, RecipeNotFound
from .repository import RecipeMediaRepository, RecipeRepository
from .schemas import (
    DeleteResponse,
    ProfileResponse,
    RecipeCreateRequest,
    RecipeCreated,
    RecipeDetail,
    RecipeListResponse,
    RecipeSummary,
    RecipeUpdateRequest,
    RecipeUpdated,
)

__all__ = [
    "DatabaseFailure",
    "DatabaseUnavailable",
    "DeleteResponse",
    "InvalidPersonLink",
    "MediaClient",
    "PostgrestRpcClient",
    "ProfileResponse",
    "RecipeCreateRequest",
    "RecipeCreated",
    "RecipeDetail",
    "RecipeListResponse",
    "RecipeMediaRepository",
    "RecipeNotFound",
    "RecipeRepository",
    "RecipeSummary",
    "RecipeUpdateRequest",
    "RecipeUpdated",
    "RpcClient",
    "build_user_client",
]
