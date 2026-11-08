"""Per-request Data API client behaviour (no network)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from backend.app.config import Settings
from backend.app.db import (
    DatabaseFailure,
    DatabaseUnavailable,
    PostgrestRpcClient,
    build_user_client,
)


def _client(access_token: str, http_client: httpx.AsyncClient) -> PostgrestRpcClient:
    return PostgrestRpcClient(
        supabase_url="https://project.supabase.co",
        publishable_key="test-publishable-key",
        access_token=access_token,
        http_client=http_client,
    )


def test_each_client_sends_its_own_user_jwt() -> None:
    seen: list[tuple[str | None, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.headers.get("apikey"), request.headers.get("authorization")))
        return httpx.Response(200, json={"ok": True})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            first = _client("token-a", http)
            second = _client("token-b", http)
            await asyncio.gather(first.rpc("any_function", {}), second.rpc("any_function", {}))

    asyncio.run(run())
    assert {apikey for apikey, _ in seen} == {"test-publishable-key"}
    assert {authorization for _, authorization in seen} == {
        "Bearer token-a",
        "Bearer token-b",
    }


def test_successful_rpc_returns_its_json_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "recipe-1", "version": 1})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = _client("token-a", http)
            return await client.rpc("create_recipe_with_version", {})

    assert asyncio.run(run()) == {"id": "recipe-1", "version": 1}


def test_timeout_maps_to_database_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("too slow", request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = _client("token-a", http)
            await client.rpc("list_recipes", {})

    with pytest.raises(DatabaseUnavailable):
        asyncio.run(run())


def test_server_error_maps_to_database_failure_without_leaking_the_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={"message": "secret SQL detail", "code": "XX000"},
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = _client("token-a", http)
            await client.rpc("list_recipes", {})

    with pytest.raises(DatabaseFailure) as exc_info:
        asyncio.run(run())
    assert "secret SQL detail" not in str(exc_info.value)


def test_build_user_client_refuses_an_unconfigured_project() -> None:
    settings = Settings(supabase_url="", supabase_publishable_key="", supabase_anon_key="")
    with pytest.raises(DatabaseUnavailable):
        build_user_client(settings, "token-a")


def test_build_user_client_uses_the_publishable_key_and_user_token() -> None:
    settings = Settings(
        supabase_url="https://project.supabase.co",
        supabase_publishable_key="test-publishable-key",
        supabase_anon_key="",
    )
    client = build_user_client(settings, "token-a")
    assert isinstance(client, PostgrestRpcClient)
