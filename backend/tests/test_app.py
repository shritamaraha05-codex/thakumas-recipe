"""FastAPI application startup and routing."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app


def test_create_app_returns_fastapi_app(test_settings: Settings) -> None:
    app = create_app(test_settings)
    assert isinstance(app, FastAPI)


def test_create_app_attaches_settings(test_settings: Settings) -> None:
    app = create_app(test_settings)
    assert app.state.settings is test_settings


def test_application_starts_and_serves(test_settings: Settings) -> None:
    app = create_app(test_settings)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200


def test_expected_routes_are_registered(test_settings: Settings) -> None:
    app = create_app(test_settings)
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/health" in paths
    assert "/api/parse" in paths


def test_openapi_schema_is_available(test_settings: Settings) -> None:
    app = create_app(test_settings)
    schema = app.openapi()
    assert schema["info"]["title"] == "Thakuma's Recipe"
    assert "/api/health" in schema["paths"]
    assert "/api/parse" in schema["paths"]
