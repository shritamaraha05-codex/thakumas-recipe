"""Invalid ``POST /api/parse`` requests use the documented error envelope."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_missing_text_returns_error_envelope(client: TestClient) -> None:
    response = client.post("/api/parse", json={"mode": "auto"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_INPUT"
    assert error["message"]
    assert error["hint"]


def test_empty_text_is_rejected(client: TestClient) -> None:
    response = client.post("/api/parse", json={"text": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_whitespace_only_text_is_rejected(client: TestClient) -> None:
    response = client.post("/api/parse", json={"text": "   \n\t "})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_unsupported_mode_is_rejected(client: TestClient) -> None:
    response = client.post("/api/parse", json={"text": "ek muthi chal", "mode": "magic"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_non_positive_servings_is_rejected(client: TestClient) -> None:
    response = client.post("/api/parse", json={"text": "ek muthi chal", "servings": 0})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_non_string_text_is_rejected(client: TestClient) -> None:
    response = client.post("/api/parse", json={"text": 123})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"
