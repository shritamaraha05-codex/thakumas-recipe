"""``GET /api/health`` contract."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.routers.health import DbProbe


def test_health_is_ok_when_the_app_is_up(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_health_reports_missing_supabase_configuration(client: TestClient) -> None:
    db = client.get("/api/health").json()["db"]
    assert db["status"] == "not_configured"
    assert db["configured"] is False
    assert db["reachable"] is None
    assert db["note"]
    assert "path" not in db


def _configured_settings() -> Settings:
    return Settings(
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="test-publishable-key",
        supabase_anon_key="",
    )


def _app_with_probe(probe: DbProbe) -> TestClient:
    return TestClient(create_app(_configured_settings(), db_probe=probe))


def test_configured_database_is_unverified_without_a_probe() -> None:
    app = create_app(_configured_settings())
    with TestClient(app) as client:
        db = client.get("/api/health").json()["db"]
    assert db["status"] == "unverified"
    assert db["configured"] is True
    assert db["reachable"] is None


def test_reachable_database_is_reported_ok() -> None:
    async def probe() -> bool:
        return True

    with _app_with_probe(probe) as client:
        db = client.get("/api/health").json()["db"]
    assert db["status"] == "ok"
    assert db["reachable"] is True


def test_unreachable_database_is_reported_unavailable() -> None:
    async def probe() -> bool:
        return False

    with _app_with_probe(probe) as client:
        db = client.get("/api/health").json()["db"]
    assert db["status"] == "unavailable"
    assert db["reachable"] is False


def test_probe_exception_is_reported_unavailable_not_leaked() -> None:
    async def probe() -> bool:
        raise RuntimeError("secret connection detail")

    with _app_with_probe(probe) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["db"]["status"] == "unavailable"
    assert "secret connection detail" not in response.text
    assert "example.supabase.co" not in response.text
    assert "test-publishable-key" not in response.text


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
