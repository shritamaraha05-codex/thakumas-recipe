"""Offline tests for the Gemini provider itself (M-10).

The ``google-genai`` client is replaced with a recording fake via monkeypatch,
so no network call is made and no credentials are needed. These tests prove the
configured model id is sent, structured output is requested, and SDK/network
errors are translated into provider-neutral exceptions.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from google import genai
from google.genai import errors

from backend.app.parse.llm_schema import LLMSelection
from backend.app.providers import (
    ProviderError,
    ProviderInvalidOutput,
    ProviderRateLimited,
    ProviderTimeout,
    ProviderUnavailable,
)
from backend.app.providers.gemini import DEFAULT_MODEL, GeminiProvider, build_provider


class _Response:
    def __init__(self, parsed: object) -> None:
        self.parsed = parsed


def _install_fake_client(
    monkeypatch: pytest.MonkeyPatch, *, parsed: object = None, error: Exception | None = None
) -> dict:
    """Replace ``genai.Client`` with a fake and return the recorded call."""
    record: dict = {}

    class _Models:
        async def generate_content(self, *, model: str, contents: str, config: object) -> _Response:
            record["model"] = model
            record["contents"] = contents
            record["config"] = config
            if error is not None:
                raise error
            return _Response(parsed)

    class _Aio:
        def __init__(self) -> None:
            self.models = _Models()

        async def aclose(self) -> None:
            record["closed"] = True

    class _Client:
        def __init__(self, *, api_key: str | None = None, http_options: object = None) -> None:
            record["api_key"] = api_key
            record["http_options"] = http_options
            self.aio = _Aio()

    monkeypatch.setattr(genai, "Client", _Client)
    return record


def _provider() -> GeminiProvider:
    return GeminiProvider(api_key="test-key", model="gemini-3.5-flash-lite")


def test_provider_sends_configured_model_and_requests_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _install_fake_client(monkeypatch, parsed=LLMSelection(segments=[]))
    result = asyncio.run(
        _provider().generate(
            system_instruction="sys",
            prompt="hello",
            response_schema=LLMSelection,
        )
    )
    assert record["model"] == "gemini-3.5-flash-lite"
    assert record["config"].response_mime_type == "application/json"
    assert record["config"].response_schema is LLMSelection
    assert record["config"].system_instruction == "sys"
    assert record["contents"] == "hello"
    assert record["api_key"] == "test-key"
    assert record["closed"] is True
    assert isinstance(result, LLMSelection)


def test_provider_requires_an_api_key() -> None:
    with pytest.raises(ProviderUnavailable):
        GeminiProvider(api_key="", model="gemini-3.5-flash-lite")


def test_provider_requires_a_model() -> None:
    with pytest.raises(ProviderUnavailable):
        GeminiProvider(api_key="k", model="")


def test_provider_maps_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    error = errors.APIError(429, {"error": {"message": "rate"}})
    _install_fake_client(monkeypatch, error=error)
    with pytest.raises(ProviderRateLimited):
        asyncio.run(
            _provider().generate(system_instruction="s", prompt="p", response_schema=LLMSelection)
        )


def test_provider_maps_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    error = errors.APIError(401, {"error": {"message": "bad key"}})
    _install_fake_client(monkeypatch, error=error)
    with pytest.raises(ProviderUnavailable):
        asyncio.run(
            _provider().generate(system_instruction="s", prompt="p", response_schema=LLMSelection)
        )


def test_provider_maps_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_client(monkeypatch, error=httpx.TimeoutException("slow"))
    with pytest.raises(ProviderTimeout):
        asyncio.run(
            _provider().generate(system_instruction="s", prompt="p", response_schema=LLMSelection)
        )


def test_provider_maps_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_client(monkeypatch, error=httpx.ConnectError("down"))
    with pytest.raises(ProviderError):
        asyncio.run(
            _provider().generate(system_instruction="s", prompt="p", response_schema=LLMSelection)
        )


def test_provider_rejects_missing_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_client(monkeypatch, parsed=None)
    with pytest.raises(ProviderInvalidOutput):
        asyncio.run(
            _provider().generate(system_instruction="s", prompt="p", response_schema=LLMSelection)
        )


def test_provider_rejects_wrong_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_client(monkeypatch, parsed={"segments": []})
    with pytest.raises(ProviderInvalidOutput):
        asyncio.run(
            _provider().generate(system_instruction="s", prompt="p", response_schema=LLMSelection)
        )


def test_build_provider_uses_the_configured_model() -> None:
    provider = build_provider(SimpleNamespace(gemini_api_key="k", gemini_model="custom-model"))
    assert provider.model == "custom-model"


def test_build_provider_defaults_when_model_is_blank() -> None:
    provider = build_provider(SimpleNamespace(gemini_api_key="k", gemini_model=""))
    assert provider.model == DEFAULT_MODEL


def test_build_provider_rejects_a_missing_key() -> None:
    with pytest.raises(ProviderUnavailable):
        build_provider(SimpleNamespace(gemini_api_key="", gemini_model="m"))
