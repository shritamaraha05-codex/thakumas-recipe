"""Offline tests for the LLM extraction pipeline (M-10).

The Gemini network call is replaced by :class:`backend.tests.llm_helpers.FakeProvider`,
so every test is deterministic and credential-free. They prove that the model
only chooses relationships between verified evidence ids and that the backend
still owns all wording, values and spans.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.app.models import ParserMode, Source
from backend.app.parse.lexicon import LEXICON, Category
from backend.app.parse.llm import build_evidence, parse_llm
from backend.app.parse.llm_schema import (
    IngredientSelection,
    LLMSelection,
    SegmentSelection,
)
from backend.app.parse.normalize import normalize
from backend.app.parse.schema import QuantityKind
from backend.app.providers import ProviderInvalidOutput
from backend.tests.llm_helpers import FakeProvider, find_id, ids_by_category


def _run(text: str, selection: dict):
    normalized = normalize(text)
    return asyncio.run(parse_llm(normalized, FakeProvider(selection=selection)))


def _evidence(text: str):
    normalized = normalize(text)
    return build_evidence(normalized)


# --------------------------------------------------------------------------- #
# Construction from verified evidence                                         #
# --------------------------------------------------------------------------- #


def test_llm_builds_quantity_from_verified_evidence() -> None:
    text = "এক মুঠো চাল"
    normalized = normalize(text)
    _segments, evidence = build_evidence(normalized)
    ingredient = find_id(evidence, Category.INGREDIENT, "চাল")
    number = find_id(evidence, Category.NUMBER)
    measure = find_id(evidence, Category.MEASURE)
    selection = {
        "segments": [
            {
                "segment_index": 0,
                "ingredients": [
                    {"ingredient_match_id": ingredient, "quantity_match_ids": [number, measure]}
                ],
            }
        ]
    }

    result = asyncio.run(parse_llm(normalized, FakeProvider(selection=selection)))

    assert result.parser_mode is ParserMode.llm
    assert result.source is Source.llm
    assert result.llm_provider == "gemini"
    assert result.steps[0].text == text
    mention = result.ingredients[0]
    assert mention.canonical == "rice"
    assert mention.surface == "চাল"
    quantity = mention.quantity
    assert quantity is not None
    assert quantity.qty == 1
    assert quantity.unit == "muthi"
    assert quantity.raw_unit == "মুঠো"
    assert quantity.kind is QuantityKind.EXACT
    assert quantity.source is Source.llm
    assert quantity.raw_phrase == "এক মুঠো"


def test_multiple_ingredients_in_one_segment() -> None:
    text = "এক মুঠো চাল আর এক চিমটি নুন"
    _segments, evidence = _evidence(text)
    rice = find_id(evidence, Category.INGREDIENT, "চাল")
    salt = find_id(evidence, Category.INGREDIENT, "নুন")
    numbers = ids_by_category(evidence, Category.NUMBER)
    measures = ids_by_category(evidence, Category.MEASURE)
    selection = {
        "segments": [
            {
                "segment_index": 0,
                "ingredients": [
                    {"ingredient_match_id": rice, "quantity_match_ids": [numbers[0], measures[0]]},
                    {"ingredient_match_id": salt, "quantity_match_ids": [numbers[1], measures[1]]},
                ],
            }
        ]
    }
    result = _run(text, selection)
    assert [mention.canonical for mention in result.ingredients] == ["rice", "salt"]
    second = result.ingredients[1].quantity
    assert second is not None
    assert second.qty == 1


def test_ingredient_without_quantity_is_allowed() -> None:
    text = "এক মুঠো চাল আর এক চিমটি নুন"
    _segments, evidence = _evidence(text)
    salt = find_id(evidence, Category.INGREDIENT, "নুন")
    selection = {
        "segments": [
            {"segment_index": 0, "ingredients": [{"ingredient_match_id": salt}]},
        ]
    }
    result = _run(text, selection)
    assert result.ingredients[0].canonical == "salt"
    assert result.ingredients[0].quantity is None


def test_half_modifier_combines_with_following_number() -> None:
    text = "সাড়ে তিন মুঠো চাল"
    _segments, evidence = _evidence(text)
    ingredient = find_id(evidence, Category.INGREDIENT, "চাল")
    measure = find_id(evidence, Category.MEASURE)
    numbers = ids_by_category(evidence, Category.NUMBER)
    selection = {
        "segments": [
            {
                "segment_index": 0,
                "ingredients": [
                    {
                        "ingredient_match_id": ingredient,
                        "quantity_match_ids": [*numbers, measure],
                    }
                ],
            }
        ]
    }
    result = _run(text, selection)
    quantity = result.ingredients[0].quantity
    assert quantity is not None
    assert quantity.qty == 3.5


# --------------------------------------------------------------------------- #
# Durations (never ingredient quantities)                                     #
# --------------------------------------------------------------------------- #


def test_duration_is_built_from_duration_evidence() -> None:
    text = "দশ মিনিট ঢিমে আঁচে রান্না করো"
    _segments, evidence = _evidence(text)
    number = find_id(evidence, Category.NUMBER)
    duration = find_id(evidence, Category.DURATION)
    selection = {
        "segments": [
            {"segment_index": 0, "duration_match_ids": [number, duration]},
        ]
    }
    result = _run(text, selection)
    assert result.steps[0].ingredients == ()
    assert len(result.steps[0].durations) == 1
    cooked = result.steps[0].durations[0]
    assert (cooked.value, cooked.unit, cooked.kind) == (10, "minute", QuantityKind.EXACT)


def test_multiple_durations_in_one_segment() -> None:
    text = "দশ মিনিট আর পাঁচ মিনিট রান্না করো"
    _segments, evidence = _evidence(text)
    numbers = ids_by_category(evidence, Category.NUMBER)
    durations_ = ids_by_category(evidence, Category.DURATION)
    selection = {
        "segments": [
            {
                "segment_index": 0,
                "duration_match_ids": [numbers[0], durations_[0], numbers[1], durations_[1]],
            }
        ]
    }
    result = _run(text, selection)
    values = [duration.value for duration in result.steps[0].durations]
    assert values == [10, 5]


# --------------------------------------------------------------------------- #
# Evidence validation                                                         #
# --------------------------------------------------------------------------- #


def test_unknown_evidence_id_is_rejected() -> None:
    text = "এক মুঠো চাল"
    normalized = normalize(text)
    selection = {
        "segments": [{"segment_index": 0, "ingredients": [{"ingredient_match_id": "s9m9"}]}]
    }
    with pytest.raises(ProviderInvalidOutput):
        asyncio.run(parse_llm(normalized, FakeProvider(selection=selection)))


def test_ingredient_id_must_be_an_ingredient_match() -> None:
    text = "এক মুঠো চাল"
    normalized = normalize(text)
    _segments, evidence = build_evidence(normalized)
    number = find_id(evidence, Category.NUMBER)
    selection = {
        "segments": [{"segment_index": 0, "ingredients": [{"ingredient_match_id": number}]}]
    }
    with pytest.raises(ProviderInvalidOutput):
        asyncio.run(parse_llm(normalized, FakeProvider(selection=selection)))


def test_quantity_id_must_be_number_or_measure() -> None:
    text = "এক মুঠো চাল"
    normalized = normalize(text)
    _segments, evidence = build_evidence(normalized)
    ingredient = find_id(evidence, Category.INGREDIENT, "চাল")
    measure = find_id(evidence, Category.MEASURE)
    selection = {
        "segments": [
            {
                "segment_index": 0,
                "ingredients": [
                    {"ingredient_match_id": ingredient, "quantity_match_ids": [measure, ingredient]}
                ],
            }
        ]
    }
    with pytest.raises(ProviderInvalidOutput):
        asyncio.run(parse_llm(normalized, FakeProvider(selection=selection)))


def test_duration_id_must_be_a_duration_match() -> None:
    text = "এক মুঠো চাল"
    normalized = normalize(text)
    _segments, evidence = build_evidence(normalized)
    ingredient = find_id(evidence, Category.INGREDIENT, "চাল")
    selection = {"segments": [{"segment_index": 0, "duration_match_ids": [ingredient]}]}
    with pytest.raises(ProviderInvalidOutput):
        asyncio.run(parse_llm(normalized, FakeProvider(selection=selection)))


def test_cross_segment_evidence_id_is_rejected() -> None:
    text = "এক মুঠো চাল। দশ মিনিট রান্না করো।"
    normalized = normalize(text)
    segments, evidence = build_evidence(normalized)
    assert len(segments) == 2
    rice = find_id(evidence, Category.INGREDIENT, "চাল")
    selection = {"segments": [{"segment_index": 1, "ingredients": [{"ingredient_match_id": rice}]}]}
    with pytest.raises(ProviderInvalidOutput):
        asyncio.run(parse_llm(normalized, FakeProvider(selection=selection)))


def test_duplicate_evidence_ids_are_rejected() -> None:
    text = "এক মুঠো চাল আর এক চিমটি নুন"
    normalized = normalize(text)
    _segments, evidence = build_evidence(normalized)
    rice = find_id(evidence, Category.INGREDIENT, "চাল")
    selection = {
        "segments": [
            {
                "segment_index": 0,
                "ingredients": [
                    {"ingredient_match_id": rice},
                    {"ingredient_match_id": rice},
                ],
            }
        ]
    }
    with pytest.raises(ProviderInvalidOutput):
        asyncio.run(parse_llm(normalized, FakeProvider(selection=selection)))


def test_selection_schema_cannot_carry_offsets_or_labels() -> None:
    assert set(LLMSelection.model_fields) == {"segments"}
    assert set(SegmentSelection.model_fields) == {
        "segment_index",
        "ingredients",
        "duration_match_ids",
    }
    assert set(IngredientSelection.model_fields) == {
        "ingredient_match_id",
        "quantity_match_ids",
    }


# --------------------------------------------------------------------------- #
# Source preservation and ambiguity retention                                 #
# --------------------------------------------------------------------------- #


def test_spans_and_wording_come_from_the_original_transcript() -> None:
    text = "এক মুঠো চাল"
    normalized = normalize(text)
    _segments, evidence = build_evidence(normalized)
    ingredient = find_id(evidence, Category.INGREDIENT, "চাল")
    number = find_id(evidence, Category.NUMBER)
    measure = find_id(evidence, Category.MEASURE)
    selection = {
        "segments": [
            {
                "segment_index": 0,
                "ingredients": [
                    {"ingredient_match_id": ingredient, "quantity_match_ids": [number, measure]}
                ],
            }
        ]
    }
    result = asyncio.run(parse_llm(normalized, FakeProvider(selection=selection)))
    mention = result.ingredients[0]
    assert text[mention.orig_start : mention.orig_end] == mention.surface == "চাল"
    assert mention.quantity is not None
    assert mention.quantity.raw_phrase in text
    assert result.steps[0].text == text


def test_plain_chamoch_stays_ambiguous() -> None:
    text = "এক চামচ তেল"
    _segments, evidence = _evidence(text)
    ingredient = find_id(evidence, Category.INGREDIENT, "তেল")
    number = find_id(evidence, Category.NUMBER)
    measure = find_id(evidence, Category.MEASURE, "চামচ")
    selection = {
        "segments": [
            {
                "segment_index": 0,
                "ingredients": [
                    {"ingredient_match_id": ingredient, "quantity_match_ids": [number, measure]}
                ],
            }
        ]
    }
    result = _run(text, selection)
    quantity = result.ingredients[0].quantity
    assert quantity is not None
    assert quantity.unit == "spoon"
    assert quantity.clarification_ids == ("unit_spoon_1",)
    assert result.clarifications[0].kind == "unit_spoon"


def test_uncalibrated_cup_stays_ambiguous() -> None:
    text = "আধা কাপ দুধ"
    _segments, evidence = _evidence(text)
    ingredient = find_id(evidence, Category.INGREDIENT, "দুধ")
    number = find_id(evidence, Category.NUMBER)
    measure = find_id(evidence, Category.MEASURE, "কাপ")
    selection = {
        "segments": [
            {
                "segment_index": 0,
                "ingredients": [
                    {"ingredient_match_id": ingredient, "quantity_match_ids": [number, measure]}
                ],
            }
        ]
    }
    result = _run(text, selection)
    quantity = result.ingredients[0].quantity
    assert quantity is not None
    assert quantity.unit == "cup"
    assert quantity.clarification_ids == ("unit_cup_1",)
    assert result.clarifications[0].kind == "unit_cup"


def test_vague_quantity_stays_vague() -> None:
    text = "একটু লবণ"
    _segments, evidence = _evidence(text)
    ingredient = find_id(evidence, Category.INGREDIENT, "লবণ")
    measure = find_id(evidence, Category.MEASURE, "একটু")
    selection = {
        "segments": [
            {
                "segment_index": 0,
                "ingredients": [
                    {"ingredient_match_id": ingredient, "quantity_match_ids": [measure]}
                ],
            }
        ]
    }
    result = _run(text, selection)
    quantity = result.ingredients[0].quantity
    assert quantity is not None
    assert quantity.kind is QuantityKind.VAGUE
    assert quantity.qty is None
    assert quantity.unit is None


def test_taste_quantity_stays_taste() -> None:
    text = "স্বাদমতো নুন"
    _segments, evidence = _evidence(text)
    ingredient = find_id(evidence, Category.INGREDIENT, "নুন")
    measure = find_id(evidence, Category.MEASURE, "স্বাদমতো")
    selection = {
        "segments": [
            {
                "segment_index": 0,
                "ingredients": [
                    {"ingredient_match_id": ingredient, "quantity_match_ids": [measure]}
                ],
            }
        ]
    }
    result = _run(text, selection)
    quantity = result.ingredients[0].quantity
    assert quantity is not None
    assert quantity.kind is QuantityKind.TASTE
    assert quantity.to_taste is True
    assert quantity.qty is None


def test_muitha_is_never_interpreted_as_a_handful() -> None:
    text = "ছোট ছোট মুইঠা গড়ে নাও"
    normalized = normalize(text)
    _segments, evidence = build_evidence(normalized)
    assert evidence.items == {}
    assert LEXICON.lookup("মুইঠা") is None
    result = asyncio.run(parse_llm(normalized, FakeProvider(selection={"segments": []})))
    assert result.ingredients == ()
    assert result.steps[0].text == text
