"""``POST /api/parse`` contract (fixture/mock path)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.models import ParseResult


def test_parse_returns_fixture_labelled_as_mock(client: TestClient) -> None:
    response = client.post(
        "/api/parse",
        json={"text": "ek muthi chal ar ek chimti nun", "mode": "auto"},
    )
    assert response.status_code == 200
    meta = response.json()["meta"]
    assert meta["mock"] is True
    assert meta["mock_source"] == "docs/fixtures/parse_result.sample.json"
    assert meta["llm_provider"] is None
    assert meta["parser_mode"] == "rules"
    assert meta["replayed"] is False


def test_parse_returns_the_sample_recipe(client: TestClient) -> None:
    body = client.post("/api/parse", json={"text": "ek muthi chal"}).json()
    assert body["recipe"]["title"] == "Sample (synthetic)"
    assert body["recipe"]["language"] == "bn-IN"
    assert body["recipe"]["base_servings"] == 4
    assert len(body["recipe"]["steps"]) == 3
    first_quantity = body["recipe"]["steps"][0]["quantities"][0]
    assert first_quantity["range"]["basis"] == "typical"
    assert body["recipe"]["steps"][2]["timer_seconds"] == 600


@pytest.mark.parametrize("mode", ["auto", "rules", "llm"])
def test_all_supported_modes_are_served_by_mock(client: TestClient, mode: str) -> None:
    response = client.post("/api/parse", json={"text": "ek muthi chal", "mode": mode})
    assert response.status_code == 200
    assert response.json()["meta"]["mock"] is True


def test_optional_contract_fields_are_accepted(client: TestClient) -> None:
    response = client.post(
        "/api/parse",
        json={"text": "ek muthi chal", "mode": "auto", "hand_profile_id": 1, "servings": 2},
    )
    assert response.status_code == 200


def test_response_validates_against_the_model(client: TestClient) -> None:
    body = client.post("/api/parse", json={"text": "ek muthi chal"}).json()
    ParseResult.model_validate(body)
