"""Offline tests for the deterministic rules parser (M-08).

Every test is pure and network-free. Source wording and spans are checked against
the original transcript, and the Chitol Macher Muitha narration is used as the
long regression case.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.models import ParserMode, Source
from backend.app.parse.normalize import normalize
from backend.app.parse.rules import parse_rules, parse_rules_text
from backend.app.parse.schema import QuantityKind

FIXTURE = Path(__file__).parent / "fixtures" / "chitol_macher_muitha_narration.txt"


def _first(text: str):
    result = parse_rules_text(text)
    assert result.ingredients, f"no ingredient found in {text!r}"
    return result.ingredients[0]


def _all(text: str):
    return parse_rules_text(text).ingredients


# --------------------------------------------------------------------------- #
# 1. Bengali ingredient + quantity + measure                                  #
# --------------------------------------------------------------------------- #


def test_bengali_ingredient_quantity_measure() -> None:
    mention = _first("দুই মুঠো চাল")
    assert mention.canonical == "rice"
    assert mention.surface == "চাল"
    quantity = mention.quantity
    assert quantity is not None
    assert quantity.qty == 2
    assert quantity.qty_max is None
    assert quantity.unit == "muthi"
    assert quantity.raw_unit == "মুঠো"
    assert quantity.raw_phrase == "দুই মুঠো"
    assert quantity.kind is QuantityKind.EXACT
    assert quantity.source is Source.rules


def test_quantity_raw_phrase_is_original_substring() -> None:
    raw = "দুই মুঠো চাল"
    mention = _first(raw)
    assert mention.quantity is not None
    assert mention.quantity.raw_phrase in raw
    assert raw[mention.orig_start : mention.orig_end] == mention.surface


# --------------------------------------------------------------------------- #
# 2. Roman Bengali ingredient + quantity                                      #
# --------------------------------------------------------------------------- #


def test_roman_bengali_quantity() -> None:
    mention = _first("ek muthi chal")
    assert mention.canonical == "rice"
    assert mention.surface == "chal"
    assert mention.quantity is not None
    assert (mention.quantity.qty, mention.quantity.unit) == (1, "muthi")


# --------------------------------------------------------------------------- #
# 3-5. Exact, spoken, decimal and fraction quantities                         #
# --------------------------------------------------------------------------- #


def test_exact_numeric_quantity() -> None:
    mention = _first("২ চিমটি নুন")
    assert mention.canonical == "salt"
    assert mention.quantity is not None
    assert (mention.quantity.qty, mention.quantity.unit) == (2, "chimti")


def test_spoken_number_quantity() -> None:
    mention = _first("এক চিমটি নুন")
    assert mention.quantity is not None
    assert (mention.quantity.qty, mention.quantity.unit) == (1, "chimti")


def test_decimal_quantity() -> None:
    mention = _first("আধা চিমটি নুন")
    assert mention.quantity is not None
    assert mention.quantity.qty == 0.5
    assert mention.quantity.kind is QuantityKind.EXACT


def test_fraction_quantity() -> None:
    mention = _first("1/2 চিমটি নুন")
    assert mention.quantity is not None
    assert mention.quantity.qty == 0.5


def test_sadhe_combines_with_following_number() -> None:
    mention = _first("সাড়ে তিন চিমটি নুন")
    assert mention.quantity is not None
    assert mention.quantity.qty == 3.5
    assert mention.quantity.raw_phrase == "সাড়ে তিন চিমটি"


# --------------------------------------------------------------------------- #
# 6. Explicit ranges                                                          #
# --------------------------------------------------------------------------- #


def test_spoken_quantity_range() -> None:
    mention = _first("তিন-চার মুঠো চাল")
    assert mention.quantity is not None
    assert (mention.quantity.qty, mention.quantity.qty_max) == (3, 4)
    assert mention.quantity.kind is QuantityKind.RANGE
    assert mention.quantity.raw_phrase == "তিন-চার মুঠো"


def test_numeric_quantity_range() -> None:
    mention = _first("৫-৬ মুঠো চাল")
    assert mention.quantity is not None
    assert (mention.quantity.qty, mention.quantity.qty_max) == (5, 6)
    assert mention.quantity.kind is QuantityKind.RANGE


def test_single_number_is_not_turned_into_range() -> None:
    mention = _first("দুই মুঠো চাল")
    assert mention.quantity is not None
    assert mention.quantity.qty_max is None


# --------------------------------------------------------------------------- #
# 7-8. Vague and taste quantities                                             #
# --------------------------------------------------------------------------- #


def test_vague_quantity_has_no_invented_number() -> None:
    mention = _first("একটু লবণ")
    assert mention.canonical == "salt"
    assert mention.quantity is not None
    assert mention.quantity.qty is None
    assert mention.quantity.qty_max is None
    assert mention.quantity.kind is QuantityKind.VAGUE
    assert mention.quantity.raw_phrase == "একটু"
    assert mention.quantity.raw_unit == "একটু"


def test_porimanimato_is_vague_and_unconverted() -> None:
    mention = _first("পরিমাণমতো জল")
    assert mention.quantity is not None
    assert mention.quantity.kind is QuantityKind.VAGUE
    assert mention.quantity.qty is None


def test_taste_quantity() -> None:
    mention = _first("স্বাদমতো নুন")
    assert mention.canonical == "salt"
    assert mention.quantity is not None
    assert mention.quantity.to_taste is True
    assert mention.quantity.qty is None
    assert mention.quantity.unit is None
    assert mention.quantity.kind is QuantityKind.TASTE


# --------------------------------------------------------------------------- #
# 9-11. Spoon and cup ambiguity, resolved compounds                           #
# --------------------------------------------------------------------------- #


def test_plain_chamoch_creates_spoon_clarification() -> None:
    result = parse_rules_text("এক চামচ নুন")
    mention = result.ingredients[0]
    assert mention.quantity is not None
    assert mention.quantity.qty == 1
    assert mention.quantity.unit == "spoon"
    assert mention.quantity.raw_unit == "চামচ"
    assert mention.quantity.clarification_ids == ("unit_spoon_1",)
    assert len(result.clarifications) == 1
    clarification = result.clarifications[0]
    assert (clarification.id, clarification.kind) == ("unit_spoon_1", "unit_spoon")
    assert clarification.options == ["tsp", "tbsp"]
    assert clarification.question


def test_uncalibrated_cup_creates_cup_clarification() -> None:
    result = parse_rules_text("আধা কাপ দুধ")
    mention = result.ingredients[0]
    assert mention.quantity is not None
    assert mention.quantity.qty == 0.5
    assert mention.quantity.unit == "cup"
    assert mention.quantity.clarification_ids == ("unit_cup_1",)
    clarification = result.clarifications[0]
    assert (clarification.id, clarification.kind) == ("unit_cup_1", "unit_cup")
    assert clarification.options == ["tea cup", "measuring cup", "my cup"]


def test_resolved_small_spoon_has_no_clarification() -> None:
    result = parse_rules_text("এক ছোট চামচ নুন")
    mention = result.ingredients[0]
    assert mention.quantity is not None
    assert mention.quantity.unit == "tsp"
    assert mention.quantity.raw_unit == "ছোট চামচ"
    assert mention.quantity.clarification_ids == ()
    assert result.clarifications == ()


def test_resolved_large_spoon_has_no_clarification() -> None:
    result = parse_rules_text("এক বড় চামচ তেল")
    mention = result.ingredients[0]
    assert mention.quantity is not None
    assert mention.quantity.unit == "tbsp"
    assert result.clarifications == ()


def test_clarification_ids_are_deterministic_and_numbered() -> None:
    result = parse_rules_text("এক চামচ নুন, এক চামচ চিনি")
    ids = [clarification.id for clarification in result.clarifications]
    assert ids == ["unit_spoon_1", "unit_spoon_2"]
    assert result == parse_rules_text("এক চামচ নুন, এক চামচ চিনি")


def test_unresolved_measure_without_number() -> None:
    mention = _first("চামচ নুন")
    assert mention.quantity is not None
    assert mention.quantity.qty is None
    assert mention.quantity.unit == "spoon"
    assert mention.quantity.kind is QuantityKind.UNRESOLVED


# --------------------------------------------------------------------------- #
# 12-13. Multiple ingredients and multiple steps                              #
# --------------------------------------------------------------------------- #


def test_multiple_ingredients_in_one_segment() -> None:
    mentions = _all("এক মুঠো চাল আর এক মুঠো ডাল")
    assert [mention.canonical for mention in mentions] == ["rice", "lentils"]
    assert mentions[0].quantity is not None and mentions[0].quantity.qty == 1
    assert mentions[1].quantity is not None and mentions[1].quantity.qty == 1
    assert mentions[0].quantity.unit == "muthi"
    assert mentions[1].quantity.unit == "muthi"


def test_multiple_steps_from_m06_connector() -> None:
    result = parse_rules_text("chal dhuye nao tarpor jol dao")
    assert len(result.steps) == 2
    assert result.steps[0].text == "chal dhuye nao"
    assert result.steps[1].connector == "tarpor"
    assert [mention.canonical for mention in result.ingredients] == ["rice", "water"]


def test_count_without_unit_is_not_given_a_unit() -> None:
    mention = _first("দুটো পেঁয়াজ কুচি করো")
    assert mention.canonical == "onion"
    assert mention.quantity is not None
    assert mention.quantity.qty == 2
    assert mention.quantity.unit is None


def test_non_adjacent_number_is_not_attached() -> None:
    mention = _first("একটা বড় হাঁড়িতে জল গরম করো")
    assert mention.canonical == "water"
    assert mention.quantity is None


# --------------------------------------------------------------------------- #
# 14. Durations are not ingredient quantities                                 #
# --------------------------------------------------------------------------- #


def test_duration_is_recorded_separately() -> None:
    result = parse_rules_text("পাঁচ মিনিট রান্না করো")
    assert result.ingredients == ()
    assert len(result.steps[0].durations) == 1
    duration = result.steps[0].durations[0]
    assert (duration.value, duration.value_max, duration.unit) == (5, None, "minute")
    assert duration.raw_phrase == "পাঁচ মিনিট"


def test_duration_range() -> None:
    result = parse_rules_text("৫-৬ মিনিট রান্না করো")
    duration = result.steps[0].durations[0]
    assert (duration.value, duration.value_max, duration.unit) == (5, 6, "minute")
    assert duration.kind is QuantityKind.RANGE


def test_duration_is_not_attached_to_ingredient() -> None:
    result = parse_rules_text("ঝোলে আলু দিয়ে পাঁচ মিনিট রান্না করো")
    potato = next(m for m in result.ingredients if m.canonical == "potato")
    assert potato.quantity is None
    assert result.steps[0].durations[0].value == 5


def test_vague_duration() -> None:
    result = parse_rules_text("কিছুক্ষণ ঢাকা দিয়ে রাখো")
    duration = result.steps[0].durations[0]
    assert duration.kind is QuantityKind.VAGUE
    assert duration.value is None


# --------------------------------------------------------------------------- #
# 15-16. Unknown words, negation and conditionals preserved                   #
# --------------------------------------------------------------------------- #


def test_unknown_words_stay_unknown() -> None:
    result = parse_rules_text("ঝোল কড়াইতে ঢালো")
    assert result.ingredients == ()


def test_negation_wording_is_preserved() -> None:
    result = parse_rules_text("জল না দিয়ে নুন দেবে না")
    assert result.ingredients
    assert all(mention.quantity is None for mention in result.ingredients)
    assert "না" in result.steps[0].text


def test_conditional_wording_and_metadata_are_preserved() -> None:
    result = parse_rules_text("আলু সেদ্ধ হলে তুলে নাও")
    assert result.steps[0].text == "আলু সেদ্ধ হলে তুলে নাও"
    assert "হলে" in result.steps[0].conditional
    potato = next(m for m in result.ingredients if m.canonical == "potato")
    assert potato.quantity is None


# --------------------------------------------------------------------------- #
# 17. Source-span exactness                                                   #
# --------------------------------------------------------------------------- #


def test_all_spans_reference_original_transcript() -> None:
    raw = "এক মুঠো চাল, আধা কাপ দুধ আর দুই চামচ চিনি।"
    result = parse_rules_text(raw)
    assert result.ingredients
    for mention in result.ingredients:
        assert raw[mention.orig_start : mention.orig_end] == mention.surface
        if mention.quantity is not None:
            assert mention.quantity.raw_phrase in raw
    for step in result.steps:
        assert raw[step.orig_start : step.orig_end] == step.text


def test_original_transcript_is_never_modified() -> None:
    raw = "দুই মুঠো চাল"
    result = parse_rules(normalize(raw))
    assert result.ingredients[0].surface == "চাল"
    assert raw == "দুই মুঠো চাল"


# --------------------------------------------------------------------------- #
# Parser metadata and determinism                                             #
# --------------------------------------------------------------------------- #


def test_metadata_is_rules_only() -> None:
    result = parse_rules_text("এক মিনিট")
    assert result.source is Source.rules
    assert result.parser_mode is ParserMode.rules


def test_parse_is_deterministic() -> None:
    text = "এক মুঠো চাল আর আধা কাপ দুধ। তারপর পাঁচ মিনিট রান্না করো।"
    assert parse_rules_text(text) == parse_rules_text(text)
    assert parse_rules(normalize(text)) == parse_rules_text(text)


def test_empty_input_is_empty_result() -> None:
    result = parse_rules_text("")
    assert result.steps == ()
    assert result.ingredients == ()
    assert result.clarifications == ()


# --------------------------------------------------------------------------- #
# 18. Chitol Macher Muitha regression                                         #
# --------------------------------------------------------------------------- #


def test_chitol_narration_regression() -> None:
    raw = FIXTURE.read_text(encoding="utf-8").strip()
    result = parse_rules_text(raw)

    assert len(result.steps) == 12
    assert [step.idx for step in result.steps] == list(range(1, 13))

    canon = {mention.canonical for mention in result.ingredients}
    assert "chitol fish" in canon
    assert "potato" in canon
    assert "onion" in canon
    assert "ginger garlic paste" in canon
    assert "green chilli" in canon
    assert "turmeric" in canon
    assert "chilli powder" in canon
    assert "tomato" in canon
    assert "oil" in canon
    assert "salt" in canon
    assert "ghee" in canon
    assert "garam masala" in canon

    # মুইঠা is the fish preparation, never a handful: no muthi quantity exists.
    assert "muthi" not in {
        mention.quantity.unit for mention in result.ingredients if mention.quantity
    }
    assert all(
        mention.quantity is None or "মুইঠা" not in mention.surface for mention in result.ingredients
    )

    # The only spoken quantities are honest and explicitly stated.
    stated = {
        (mention.canonical, mention.quantity.qty, mention.quantity.unit)
        for mention in result.ingredients
        if mention.quantity is not None and mention.quantity.qty is not None
    }
    assert stated == set()

    # Durations are recorded, not attached as ingredients.
    all_durations = [d for step in result.steps for d in step.durations]
    assert [(d.value, d.unit) for d in all_durations] == [(5, "minute")]

    # Every span and surface is exact against the untouched transcript.
    for step in result.steps:
        assert raw[step.orig_start : step.orig_end] == step.text
        assert step.text in raw
    for mention in result.ingredients:
        assert raw[mention.orig_start : mention.orig_end] == mention.surface
        if mention.quantity is not None:
            assert mention.quantity.raw_phrase in raw


def test_chitol_positions_in_original() -> None:
    raw = FIXTURE.read_text(encoding="utf-8").strip()
    result = parse_rules_text(raw)
    for mention in result.ingredients:
        assert mention.surface in raw
        assert mention.orig_start < mention.orig_end


@pytest.mark.parametrize("text", ["দুই মুঠো চাল", "ek muthi chal", "এক চামচ নুন"])
def test_repeated_parse_is_stable(text: str) -> None:
    assert parse_rules_text(text) == parse_rules_text(text)


def test_brief_typo_spelling_is_left_unknown() -> None:
    # The M-07 vocabulary (frozen in M-08) spells the fish "চিতল". The brief's
    # ``চিটল`` (ট) variant is not in that vocabulary, so the parser must not
    # fuzzy-correct it: only the plain "মাছ" is recognised.
    mentions = _all("চিটল মাছ")
    assert [mention.canonical for mention in mentions] == ["fish"]
