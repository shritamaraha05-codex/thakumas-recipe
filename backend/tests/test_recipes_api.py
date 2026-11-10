"""Protected recipe API contract and cross-user isolation (M-20)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from backend.app.auth import AuthContext, get_auth_context
from backend.app.config import Settings
from backend.app.db import DatabaseFailure, DatabaseUnavailable
from backend.app.routers.recipes import get_repository
from backend.tests.fakes import (
    FakeStore,
    FakeTokenVerifier,
    build_test_app,
    make_user,
)

TRANSCRIPT = "চিতল মাছ ভালো করে ধুয়ে নাও।\nতারপর এক চিমটি নুন আর একটু হলুদ দাও।  "
DRAFT: dict[str, Any] = {
    "recipe": {
        "title": "চিতল মাছের মুইঠা",
        "language": "bn",
        "base_servings": None,
        "steps": [
            {
                "idx": 1,
                "text": "চিতল মাছ ভালো করে ধুয়ে নাও।",
                "orig_start": 0,
                "orig_end": 28,
                "timer_seconds": None,
                "durations": [],
                "quantities": [
                    {
                        "id": "q1",
                        "ingredient": "নুন",
                        "qty": 1.0,
                        "qty_max": None,
                        "unit": "pinch",
                        "raw_phrase": "এক চিমটি নুন",
                        "range": None,
                        "clarification": None,
                    }
                ],
            }
        ],
    },
    "meta": {
        "parser_mode": "rules",
        "llm_provider": None,
        "replayed": False,
        "mock": False,
        "mock_source": None,
    },
}


def _settings() -> Settings:
    return Settings(
        supabase_url="https://project.supabase.co",
        supabase_publishable_key="test-publishable-key",
        supabase_anon_key="",
        gnani_api_key="",
        gnani_mock=True,
        llm_chain="rules",
        gemini_api_key="",
        gemini_model="",
    )


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def verifier() -> FakeTokenVerifier:
    return FakeTokenVerifier(
        {
            "token-a": make_user("user-a", name="Alice"),
            "token-b": make_user("user-b", name="Bob"),
        }
    )


@pytest.fixture
def client(store: FakeStore, verifier: FakeTokenVerifier) -> Iterator[TestClient]:
    with TestClient(build_test_app(_settings(), verifier, store)) as test_client:
        yield test_client


def _auth(token: str = "token-a") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Chitol Macher Muitha",
        "original_transcript": TRANSCRIPT,
        "draft": DRAFT,
        "tags": ["fish", "bengali"],
        "cook_person_id": None,
        "narrator_person_id": None,
    }
    payload.update(overrides)
    return payload


def _create(client: TestClient, token: str = "token-a", **overrides: Any):
    return client.post("/api/recipes", headers=_auth(token), json=_payload(**overrides))


def test_create_recipe_returns_id_and_version_one(client: TestClient, store: FakeStore) -> None:
    response = _create(client)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "version"}
    assert body["version"] == 1
    assert store.recipes[body["id"]]["owner_user_id"] == "user-a"


def test_list_returns_only_concise_metadata(client: TestClient) -> None:
    created = _create(client).json()
    response = client.get("/api/recipes", headers=_auth())
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == created["id"]
    assert item["title"] == "Chitol Macher Muitha"
    assert item["tags"] == ["fish", "bengali"]
    assert item["version"] == 1
    assert "draft" not in item
    assert "original_transcript" not in item


def test_get_recipe_returns_exact_transcript_and_full_draft(client: TestClient) -> None:
    created = _create(client).json()
    response = client.get(f"/api/recipes/{created['id']}", headers=_auth())
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["version"] == 1
    assert body["original_transcript"] == TRANSCRIPT
    assert body["draft"] == DRAFT
    assert body["tags"] == ["fish", "bengali"]


def test_recipe_translation_returns_one_english_line_per_bengali_step(client: TestClient) -> None:
    class FakeTranslationProvider:
        name = "test"

        async def generate(self, *, system_instruction, prompt, response_schema):
            assert "Translate each Bengali recipe step" in system_instruction
            assert "চিতল মাছ" in prompt
            return response_schema(translations=["Wash the fish well."])

    client.app.state.settings = client.app.state.settings.model_copy(
        update={"gemini_api_key": "test-key"}
    )
    client.app.state.llm_provider_factory = lambda settings: FakeTranslationProvider()
    created = _create(client).json()
    response = client.get(
        f"/api/recipes/{created['id']}/translation", headers=_auth()
    )
    assert response.status_code == 200
    assert response.json() == {"translations": ["Wash the fish well."]}


def test_recipe_translation_requires_configured_provider(client: TestClient) -> None:
    created = _create(client).json()
    response = client.get(
        f"/api/recipes/{created['id']}/translation", headers=_auth()
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LLM_UNAVAILABLE"


def test_bengali_unicode_survives_the_round_trip(client: TestClient) -> None:
    created = _create(client).json()
    body = client.get(f"/api/recipes/{created['id']}", headers=_auth()).json()
    assert "চিতল মাছ" in body["original_transcript"]
    assert body["draft"]["recipe"]["title"] == "চিতল মাছের মুইঠা"
    assert body["draft"]["recipe"]["steps"][0]["quantities"][0]["raw_phrase"] == "এক চিমটি নুন"


def test_title_search_and_tag_filter(client: TestClient) -> None:
    _create(client)
    _create(client, title="Aloo Posto", tags=["vegetarian"])

    by_query = client.get("/api/recipes?query=aloo", headers=_auth()).json()
    assert by_query["total"] == 1
    assert by_query["items"][0]["title"] == "Aloo Posto"

    by_tag = client.get("/api/recipes?tag=fish", headers=_auth()).json()
    assert by_tag["total"] == 1
    assert by_tag["items"][0]["title"] == "Chitol Macher Muitha"


def test_pagination_parameters_are_validated(client: TestClient) -> None:
    assert client.get("/api/recipes?limit=0", headers=_auth()).status_code == 422
    assert client.get("/api/recipes?offset=-1", headers=_auth()).status_code == 422


def test_update_creates_version_two_and_keeps_version_one(
    client: TestClient, store: FakeStore
) -> None:
    created = _create(client).json()
    response = client.put(
        f"/api/recipes/{created['id']}",
        headers=_auth(),
        json={
            "title": "সংস্করণ ২",
            "tags": ["edited"],
            "original_transcript": "নতুন ট্রান্সক্রিপ্ট",
            "draft": {"recipe": {"title": "সংস্করণ ২", "steps": []}, "meta": {}},
        },
    )
    assert response.status_code == 200
    assert response.json() == {"id": created["id"], "version": 2}

    detail = client.get(f"/api/recipes/{created['id']}", headers=_auth()).json()
    assert detail["version"] == 2
    assert detail["title"] == "সংস্করণ ২"
    assert detail["original_transcript"] == "নতুন ট্রান্সক্রিপ্ট"

    versions = store.versions[created["id"]]
    assert [version["version_number"] for version in versions] == [1, 2]
    assert versions[0]["original_transcript"] == TRANSCRIPT
    assert versions[0]["draft"] == DRAFT


def test_update_without_title_or_tags_keeps_them(client: TestClient) -> None:
    created = _create(client).json()
    response = client.put(
        f"/api/recipes/{created['id']}",
        headers=_auth(),
        json={
            "original_transcript": "শুধু নতুন ট্রান্সক্রিপ্ট",
            "draft": {"recipe": {"title": "kept", "steps": []}, "meta": {}},
        },
    )
    assert response.status_code == 200
    detail = client.get(f"/api/recipes/{created['id']}", headers=_auth()).json()
    assert detail["title"] == "Chitol Macher Muitha"
    assert detail["tags"] == ["fish", "bengali"]


def test_delete_recipe(client: TestClient, store: FakeStore) -> None:
    created = _create(client).json()
    response = client.delete(f"/api/recipes/{created['id']}", headers=_auth())
    assert response.status_code == 200
    assert response.json() == {"id": created["id"], "deleted": True}
    assert created["id"] not in store.recipes
    assert created["id"] not in store.versions
    assert client.get(f"/api/recipes/{created['id']}", headers=_auth()).status_code == 404


def test_user_a_cannot_read_update_or_delete_user_b_recipe(client: TestClient) -> None:
    created = _create(client, token="token-a").json()

    assert client.get(f"/api/recipes/{created['id']}", headers=_auth("token-b")).status_code == 404
    assert (
        client.put(
            f"/api/recipes/{created['id']}",
            headers=_auth("token-b"),
            json={"original_transcript": "hijack", "draft": {}},
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/recipes/{created['id']}", headers=_auth("token-b")).status_code == 404
    )

    listing = client.get("/api/recipes", headers=_auth("token-b")).json()
    assert listing == {"items": [], "total": 0}


def test_missing_or_malformed_recipe_ids_do_not_leak(client: TestClient) -> None:
    missing = client.get("/api/recipes/00000000-0000-0000-0000-000000000000", headers=_auth())
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    malformed = client.get("/api/recipes/not-a-uuid", headers=_auth())
    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "INVALID_INPUT"


def test_client_cannot_choose_the_owner(client: TestClient) -> None:
    response = _create(client, owner_user_id="user-b")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_non_null_person_ids_are_rejected_with_clear_422(client: TestClient) -> None:
    for field in ("cook_person_id", "narrator_person_id"):
        response = _create(client, **{field: "person-1"})
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "INVALID_INPUT"
        assert "not implemented" in body["error"]["message"].lower()


def test_empty_title_or_transcript_is_rejected(client: TestClient) -> None:
    assert _create(client, title="   ").status_code == 422
    assert _create(client, original_transcript="   ").status_code == 422


def test_me_returns_profile_without_tokens(client: TestClient) -> None:
    response = client.get("/api/me", headers=_auth())
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "user-a"
    assert body["display_name"] == "Alice"
    assert "access_token" not in body
    assert "token-a" not in response.text


def test_parse_endpoint_remains_public_and_unchanged(client: TestClient) -> None:
    response = client.post(
        "/api/parse",
        json={"text": "এক চামচ তেল দাও।", "mode": "rules"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["parser_mode"] == "rules"
    assert body["meta"]["llm_provider"] is None
    assert body["recipe"]["steps"]


class _FailingRepository:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def get_or_create_profile(self, *args, **kwargs):
        raise self.error

    async def create_recipe(self, *args, **kwargs):
        raise self.error

    async def list_recipes(self, *args, **kwargs):
        raise self.error

    async def get_recipe(self, *args, **kwargs):
        raise self.error

    async def create_recipe_version(self, *args, **kwargs):
        raise self.error

    async def delete_recipe(self, *args, **kwargs):
        raise self.error


def _app_with_repository(error: Exception):
    app = build_test_app(
        _settings(),
        FakeTokenVerifier({"token-a": make_user("user-a", name="Alice")}),
        FakeStore(),
    )
    repository = _FailingRepository(error)

    def override(auth: AuthContext = Depends(get_auth_context)):
        return repository

    app.dependency_overrides[get_repository] = override
    return app


def test_database_timeout_maps_to_503_without_leaking_details() -> None:
    app = _app_with_repository(DatabaseUnavailable("postgres://secret-host:5432"))
    with TestClient(app) as client:
        response = client.get("/api/recipes", headers=_auth())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UPSTREAM_BUSY"
    assert "secret-host" not in response.text


def test_database_failure_maps_to_502_without_leaking_details() -> None:
    app = _app_with_repository(DatabaseFailure("SELECT * FROM secret_table failed"))
    with TestClient(app) as client:
        response = client.get("/api/recipes", headers=_auth())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"
    assert "secret_table" not in response.text
