"""``GET /api/health`` contract."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app


def test_health_is_ok_when_the_app_is_up(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_health_reports_database_state_honestly(client: TestClient) -> None:
    db = client.get("/api/health").json()["db"]
    assert db["status"] == "not_initialized"
    assert db["path"] == "thakuma.db"
    assert db["note"]


def test_health_reports_gnani_config_and_mock(client: TestClient) -> None:
    gnani = client.get("/api/health").json()["gnani"]
    assert gnani == {"configured": False, "mock": True}


def test_health_lists_chain_and_only_confirms_rules_healthy(client: TestClient) -> None:
    llm = client.get("/api/health").json()["llm"]
    assert llm["chain"] == ["rules"]
    assert llm["healthy"] == ["rules"]
    names = {provider["name"] for provider in llm["providers"]}
    assert {"gemini", "rules"} <= names


def test_health_does_not_claim_gemini_is_healthy(client: TestClient) -> None:
    llm = client.get("/api/health").json()["llm"]
    gemini = next(provider for provider in llm["providers"] if provider["name"] == "gemini")
    assert gemini["configured"] is False
    assert gemini["healthy"] is None


def test_key_presence_does_not_imply_health(test_settings: Settings) -> None:
    configured = test_settings.model_copy(update={"gemini_api_key": "test-key"})
    app = create_app(configured)
    with TestClient(app) as client:
        llm = client.get("/api/health").json()["llm"]
    gemini = next(provider for provider in llm["providers"] if provider["name"] == "gemini")
    assert gemini["configured"] is True
    assert gemini["healthy"] is None
