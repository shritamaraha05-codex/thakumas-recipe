"""The sample fixture must match the Pydantic contract (docs/04_API.md)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from backend.app.config import DEFAULT_MOCK_FIXTURE
from backend.app.models import ParseRequest, ParseResult, QuantityRange

QUANTITY_FIELDS = [
    "id",
    "ingredient",
    "ingredient_class",
    "qty",
    "qty_max",
    "unit",
    "to_taste",
    "raw_phrase",
    "confidence",
    "source",
    "range",
    "clarification",
]


def _raw() -> dict:
    return json.loads(DEFAULT_MOCK_FIXTURE.read_text(encoding="utf-8"))


def test_sample_fixture_validates_as_parse_result() -> None:
    result = ParseResult.model_validate(_raw())
    assert result.meta.parser_mode.value == "hybrid"
    assert result.meta.llm_provider == "gemini"
    assert result.meta.mock is False


def test_fixture_declares_mock_metadata_fields() -> None:
    meta = _raw()["meta"]
    assert "mock" in meta
    assert "mock_source" in meta


def test_fixture_quantities_use_the_documented_fields() -> None:
    quantity = _raw()["recipe"]["steps"][0]["quantities"][0]
    for field in QUANTITY_FIELDS:
        assert field in quantity, f"fixture quantity is missing '{field}'"


def test_parse_request_defaults() -> None:
    request = ParseRequest(text="ek muthi chal")
    assert request.mode.value == "auto"
    assert request.hand_profile_id is None
    assert request.servings is None


def test_range_basis_is_restricted_to_documented_values() -> None:
    with pytest.raises(ValidationError):
        QuantityRange.model_validate({"lo": 1, "hi": 2, "unit": "g", "basis": "guess"})
