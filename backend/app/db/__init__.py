"""Owner-scoped Supabase Data API access."""

from __future__ import annotations

from .client import PostgrestRpcClient, RpcClient, build_user_client
from .errors import DatabaseFailure, DatabaseUnavailable, InvalidPersonLink, RecipeNotFound
from .repository import RecipeRepository
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
    "PostgrestRpcClient",
    "ProfileResponse",
    "RecipeCreateRequest",
    "RecipeCreated",
    "RecipeDetail",
    "RecipeListResponse",
    "RecipeNotFound",
    "RecipeRepository",
    "RecipeSummary",
    "RecipeUpdateRequest",
    "RecipeUpdated",
    "RpcClient",
    "build_user_client",
]
