"""The sample fixture must match the Pydantic contract (docs/04_API.md).

Since M-09 the fixture is the *actual* response of the rules parser for one
documented narration, not a hand-written mock. A test below re-runs that
narration through the API and compares, so the sample cannot drift from reality.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.config import DEFAULT_MOCK_FIXTURE
from backend.app.models import ParseRequest, ParseResult, QuantityRange

# The narration the sample fixture was generated from (docs/04_API.md).
SAMPLE_INPUT = (
    "এক চামচ তেল দাও। তারপর এক মুঠো চাল আর এক চিমটি নুন দাও, স্বাদমতো নুন। দশ মিনিট ঢিমে আঁচে রান্না করো।"
)

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
    "resolution",
]


def _raw() -> dict:
    return json.loads(DEFAULT_MOCK_FIXTURE.read_text(encoding="utf-8"))


def test_sample_fixture_validates_as_parse_result() -> None:
    result = ParseResult.model_validate(_raw())
    assert result.meta.parser_mode.value == "rules"
    assert result.meta.llm_provider is None
    assert result.meta.mock is False


def test_sample_fixture_matches_the_live_rules_response(client: TestClient) -> None:
    body = client.post("/api/parse", json={"text": SAMPLE_INPUT, "mode": "rules"}).json()
    assert body == _raw()


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
