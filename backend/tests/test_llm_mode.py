"""``POST /api/parse`` mode selection and provider error handling (M-10).

The Gemini call is replaced by an injected fake provider, so these tests are
offline. They cover mode selection, truthful metadata, the controlled error
envelope for missing keys/failures/timeouts, and that no network call is made.
"""

from __future__ import annotations

import socket
from collections.abc import Callable
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.models import ParseResult
from backend.app.parse.lexicon import Category
from backend.app.parse.llm import build_evidence
from backend.app.parse.normalize import normalize
from backend.app.providers import (
    ProviderError,
    ProviderRateLimited,
    ProviderTimeout,
    StructuredLLMProvider,
)
from backend.tests.llm_helpers import FakeProvider, find_id

RICE_TEXT = "এক মুঠো চাল"


def _settings(**overrides: object) -> Settings:
    base: dict = {
        "api_prefix": "/api",
        "gnani_api_key": "",
        "gnani_mock": True,
        "llm_chain": "rules",
        "gemini_api_key": "test-key",
        "gemini_model": "gemini-3.5-flash-lite",
    }
    base.update(overrides)
    return Settings(**base)


@contextmanager
def _client(factory: Callable[[Settings], StructuredLLMProvider], **overrides: object):
    app = create_app(_settings(**overrides), llm_provider_factory=factory)
    with TestClient(app) as test_client:
        yield test_client


def _rice_selection() -> dict:
    _segments, evidence = build_evidence(normalize(RICE_TEXT))
    ingredient = find_id(evidence, Category.INGREDIENT, "চাল")
    number = find_id(evidence, Category.NUMBER)
    measure = find_id(evidence, Category.MEASURE)
    return {
        "segments": [
            {
                "segment_index": 0,
                "ingredients": [
                    {"ingredient_match_id": ingredient, "quantity_match_ids": [number, measure]}
                ],
            }
        ]
    }


# --------------------------------------------------------------------------- #
# Mode selection                                                              #
# --------------------------------------------------------------------------- #


def test_llm_mode_selects_gemini_with_truthful_metadata() -> None:
    provider = FakeProvider(selection=_rice_selection())
    with _client(lambda _settings: provider) as client:
        response = client.post("/api/parse", json={"text": RICE_TEXT, "mode": "llm"})

    assert response.status_code == 200
    body = response.json()
    ParseResult.model_validate(body)
    assert body["meta"]["parser_mode"] == "llm"
    assert body["meta"]["llm_provider"] == "gemini"
    assert body["meta"]["mock"] is False
    assert len(provider.calls) == 1


def test_llm_mode_returns_the_validated_internal_contract() -> None:
    provider = FakeProvider(selection=_rice_selection())
    with _client(lambda _settings: provider) as client:
        step = client.post("/api/parse", json={"text": RICE_TEXT, "mode": "llm"}).json()["recipe"][
            "steps"
        ][0]
    quantity = step["quantities"][0]
    assert quantity["ingredient"] == "rice"
    assert quantity["qty"] == 1
    assert quantity["unit"] == "muthi"
    assert quantity["raw_phrase"] == RICE_TEXT
    assert quantity["source"] == "llm"
    assert step["text"] == RICE_TEXT


def test_llm_request_passes_the_narration_without_translation() -> None:
    provider = FakeProvider(selection=_rice_selection())
    with _client(lambda _settings: provider) as client:
        client.post("/api/parse", json={"text": RICE_TEXT, "mode": "llm"})
    call = provider.calls[0]
    assert RICE_TEXT in call["prompt"]
    assert call["system_instruction"]
    assert call["response_schema"] is not None


def test_roman_bengali_is_passed_without_forced_correction() -> None:
    provider = FakeProvider(selection={"segments": []})
    with _client(lambda _settings: provider) as client:
        client.post("/api/parse", json={"text": "ek muthi chal", "mode": "llm"})
    assert "ek muthi chal" in provider.calls[0]["prompt"]


def test_auto_mode_uses_gemini_first_when_configured() -> None:
    provider = FakeProvider(selection=_rice_selection())
    with _client(lambda _settings: provider, llm_chain="gemini,rules") as client:
        body = client.post("/api/parse", json={"text": RICE_TEXT, "mode": "auto"}).json()
    assert body["meta"]["parser_mode"] == "llm"
    assert len(provider.calls) == 1


def test_auto_mode_with_rules_chain_never_builds_a_provider() -> None:
    built: list[Settings] = []

    def factory(settings: Settings) -> StructuredLLMProvider:
        built.append(settings)
        raise AssertionError("an LLM provider was built for a rules-only chain")

    with _client(factory, llm_chain="rules") as client:
        response = client.post("/api/parse", json={"text": RICE_TEXT, "mode": "auto"})
    assert response.status_code == 200
    assert response.json()["meta"]["parser_mode"] == "rules"
    assert built == []


# --------------------------------------------------------------------------- #
# Provider-unavailable and failure handling                                   #
# --------------------------------------------------------------------------- #


def test_missing_api_key_returns_controlled_unavailable() -> None:
    app = create_app(_settings(gemini_api_key=""))  # default factory, no key
    with TestClient(app) as client:
        response = client.post("/api/parse", json={"text": RICE_TEXT, "mode": "llm"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LLM_UNAVAILABLE"


def test_provider_failure_returns_controlled_error() -> None:
    provider = FakeProvider(error=ProviderError("secret upstream detail"))
    with _client(lambda _settings: provider) as client:
        response = client.post("/api/parse", json={"text": RICE_TEXT, "mode": "llm"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"
    assert "secret upstream detail" not in response.text
    assert RICE_TEXT not in response.text


def test_provider_timeout_returns_controlled_error() -> None:
    provider = FakeProvider(error=ProviderTimeout("slow"))
    with _client(lambda _settings: provider) as client:
        response = client.post("/api/parse", json={"text": RICE_TEXT, "mode": "llm"})
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_BUSY"


def test_provider_rate_limit_returns_controlled_error() -> None:
    provider = FakeProvider(error=ProviderRateLimited("rl"))
    with _client(lambda _settings: provider) as client:
        response = client.post("/api/parse", json={"text": RICE_TEXT, "mode": "llm"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UPSTREAM_BUSY"


def test_invalid_structured_response_returns_controlled_error() -> None:
    selection = {
        "segments": [{"segment_index": 0, "ingredients": [{"ingredient_match_id": "s9m9"}]}]
    }
    provider = FakeProvider(selection=selection)
    with _client(lambda _settings: provider) as client:
        response = client.post("/api/parse", json={"text": RICE_TEXT, "mode": "llm"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"
    assert "recipe" not in response.json()


# --------------------------------------------------------------------------- #
# Offline guarantees                                                          #
# --------------------------------------------------------------------------- #


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted during an offline test")

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)


def test_rules_and_auto_are_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_network(monkeypatch)
    with _client(lambda _settings: FakeProvider(selection={"segments": []})) as client:
        assert (
            client.post("/api/parse", json={"text": RICE_TEXT, "mode": "rules"}).status_code == 200
        )
        assert (
            client.post("/api/parse", json={"text": RICE_TEXT, "mode": "auto"}).status_code == 200
        )


def test_llm_mode_with_a_fake_provider_is_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_network(monkeypatch)
    provider = FakeProvider(selection=_rice_selection())
    with _client(lambda _settings: provider) as client:
        response = client.post("/api/parse", json={"text": RICE_TEXT, "mode": "llm"})
    assert response.status_code == 200
    assert response.json()["meta"]["llm_provider"] == "gemini"


def test_rules_mode_remains_deterministic() -> None:
    with _client(lambda _settings: FakeProvider(selection={"segments": []})) as client:
        first = client.post("/api/parse", json={"text": RICE_TEXT, "mode": "rules"}).json()
        second = client.post("/api/parse", json={"text": RICE_TEXT, "mode": "rules"}).json()
    assert first == second
