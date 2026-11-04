"""The mock path must work with no credentials and no network."""

from __future__ import annotations

import socket

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app


def test_settings_are_credential_free(test_settings: Settings) -> None:
    assert test_settings.gnani_api_key == ""
    assert test_settings.gemini_api_key == ""
    assert test_settings.llm_chain_list == ["rules"]


def test_endpoints_work_without_credentials(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 200
    response = client.post("/api/parse", json={"text": "ek muthi chal", "mode": "llm"})
    assert response.status_code == 200


def test_no_outbound_connection_is_made(
    monkeypatch: pytest.MonkeyPatch, test_settings: Settings
) -> None:
    def _blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted during an offline test")

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)

    app = create_app(test_settings)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/parse", json={"text": "ek muthi chal"}).status_code == 200
