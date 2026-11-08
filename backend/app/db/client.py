"""Per-request PostgREST Data API client.

Each request builds its own client carrying that user's access token. There is
no shared mutable client and no service-role key: Supabase RLS therefore sees
the real authenticated user for every query.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx
from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError

from backend.app.config import Settings

from .errors import DatabaseFailure, DatabaseUnavailable


class RpcClient(Protocol):
    """The minimal Data API surface the repository needs (easy to fake)."""

    async def rpc(self, function: str, params: dict[str, Any]) -> Any: ...

    async def aclose(self) -> None: ...


class PostgrestRpcClient:
    """An owner-scoped client that only calls parameterised SQL functions."""

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

    async def aclose(self) -> None:
        await self._client.aclose()


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
