"""Per-request PostgREST Data API client.

Each request builds its own client carrying that user's access token. There is
no shared mutable client and no service-role key: Supabase RLS therefore sees
the real authenticated user for every query.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

import httpx
from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError

from backend.app.config import Settings

from .errors import DatabaseFailure, DatabaseUnavailable

# A table query is expressed as equality filters plus an optional ordered list
# of (column, descending) pairs. RLS still applies to every call.
Filters = dict[str, Any]
Orders = Sequence[tuple[str, bool]]


class RpcClient(Protocol):
    """The minimal Data API surface the repository needs (easy to fake)."""

    async def rpc(self, function: str, params: dict[str, Any]) -> Any: ...

    async def aclose(self) -> None: ...


class MediaClient(Protocol):
    """Owner-scoped table access used by the media repository (easy to fake)."""

    async def select(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: Filters | None = None,
        orders: Orders | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]: ...

    async def insert(self, table: str, row: dict[str, Any]) -> list[dict[str, Any]]: ...

    async def delete(self, table: str, *, filters: Filters) -> list[dict[str, Any]]: ...

    async def aclose(self) -> None: ...


class PostgrestRpcClient:
    """An owner-scoped Data API client (RPC calls plus recipe-media table access)."""

    def __init__(
        self,
        *,
        supabase_url: str,
        publishable_key: str,
        access_token: str,
        timeout: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if http_client is None:
            http_client = httpx.AsyncClient(timeout=timeout)
        self._client = AsyncPostgrestClient(
            f"{supabase_url.rstrip('/')}/rest/v1",
            headers={
                "apikey": publishable_key,
                "Authorization": f"Bearer {access_token}",
            },
            http_client=http_client,
        )

    async def rpc(self, function: str, params: dict[str, Any]) -> Any:
        try:
            response = await self._client.rpc(function, params).execute()
        except httpx.TimeoutException as exc:
            raise DatabaseUnavailable("The database did not answer in time.") from exc
        except (httpx.HTTPError, APIError) as exc:
            raise DatabaseFailure("The database request failed.") from exc
        return response.data

    async def select(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: Filters | None = None,
        orders: Orders | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Read rows from one table; RLS restricts the result to owned records."""
        try:
            query = self._client.table(table).select(columns)
            for column, value in (filters or {}).items():
                query = query.eq(column, value)
            for column, descending in orders or ():
                query = query.order(column, desc=descending)
            if limit is not None:
                query = query.limit(limit)
            response = await query.execute()
        except httpx.TimeoutException as exc:
            raise DatabaseUnavailable("The database did not answer in time.") from exc
        except (httpx.HTTPError, APIError) as exc:
            raise DatabaseFailure("The database request failed.") from exc
        return _rows(response.data)

    async def insert(self, table: str, row: dict[str, Any]) -> list[dict[str, Any]]:
        """Insert one row and return the representation PostgREST echoes back."""
        try:
            response = await self._client.table(table).insert(row).execute()
        except httpx.TimeoutException as exc:
            raise DatabaseUnavailable("The database did not answer in time.") from exc
        except (httpx.HTTPError, APIError) as exc:
            raise DatabaseFailure("The database request failed.") from exc
        return _rows(response.data)

    async def delete(self, table: str, *, filters: Filters) -> list[dict[str, Any]]:
        """Delete matching rows and return the deleted representation."""
        try:
            query = self._client.table(table).delete()
            for column, value in filters.items():
                query = query.eq(column, value)
            response = await query.execute()
        except httpx.TimeoutException as exc:
            raise DatabaseUnavailable("The database did not answer in time.") from exc
        except (httpx.HTTPError, APIError) as exc:
            raise DatabaseFailure("The database request failed.") from exc
        return _rows(response.data)

    async def aclose(self) -> None:
        await self._client.aclose()


def _rows(data: Any) -> list[dict[str, Any]]:
    """Normalise a PostgREST payload to a list of row mappings."""
    if data is None:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    raise DatabaseFailure("The database returned an unexpected response.")


def build_user_client(
    settings: Settings,
    access_token: str,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> PostgrestRpcClient:
    if not settings.supabase_configured:
        raise DatabaseUnavailable("Supabase is not configured.")
    return PostgrestRpcClient(
        supabase_url=settings.supabase_url,
        publishable_key=settings.supabase_key,
        access_token=access_token,
        timeout=settings.supabase_request_timeout,
        http_client=http_client,
    )
