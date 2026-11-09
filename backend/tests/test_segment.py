"""Unit tests for ``backend/app/parse/segment.py`` (M-06)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.parse.normalize import normalize
from backend.app.parse.segment import Segment, segment, segment_text

FIXTURE = Path(__file__).parent / "fixtures" / "chitol_macher_muitha_narration.txt"


def _seg(text: str) -> tuple[Segment, ...]:
    return segment(normalize(text))


def _assert_full_coverage(original: str, segments: tuple[Segment, ...]) -> None:
    """Every non-whitespace character of ``original`` falls inside a segment."""
    covered: set[int] = set()
    previous_end = -1
    for segment_ in segments:
        assert 0 <= segment_.orig_start <= segment_.orig_end <= len(original)
        assert segment_.orig_start >= previous_end, "segments must not overlap"
        previous_end = segment_.orig_end
        covered.update(range(segment_.orig_start, segment_.orig_end))
    for pos, char in enumerate(original):
        if not char.isspace():
            assert pos in covered, f"character {pos} ({char!r}) not covered by any segment"


# --- Basic segmentation -------------------------------------------------------


def test_single_instruction() -> None:
    segments = _seg("ek muthi chal diye ranna koro")
    assert len(segments) == 1
    step = segments[0]
    assert step.idx == 1
    assert step.text == "ek muthi chal diye ranna koro"
    assert step.connector is None
    assert step.boundary == "start"


def test_multiple_instructions_separated_by_punctuation() -> None:
    segments = _seg("tel gorom koro. peyaj dao।")
    assert len(segments) == 2
    assert segments[0].original_text == "tel gorom koro."
    assert segments[1].text == "peyaj dao ।"


def test_bengali_danda_boundary() -> None:
    segments = _seg("জল দাও। নুন দাও")
    assert len(segments) == 2
    assert segments[0].original_text == "জল দাও।"
    assert segments[1].text == "নুন দাও"


def test_tarpor_connector() -> None:
    segments = _seg("chal dhuye nao tarpor jol dao")
    assert len(segments) == 2
    assert segments[1].connector == "tarpor"
    assert segments[1].boundary == "connector"
    assert segments[1].text == "tarpor jol dao"


def test_sequence_connectors_bengali() -> None:
    text = "প্রথমে তেল গরম করো। তারপর পেঁয়াজ দাও। এবার আদা দাও। সবশেষে নুন দাও।"
    segments = _seg(text)
    assert [step.connector for step in segments] == ["প্রথমে", "তারপর", "এবার", "সবশেষে"]


def test_multiword_connector_eke_eke_is_not_split() -> None:
    segments = _seg("মুইঠাগুলো একে একে জলে ছেড়ে দাও")
    assert len(segments) == 2
    assert segments[1].connector == "একে একে"


def test_multiword_connector_tarpor_abar_is_not_split() -> None:
    segments = _seg("ek muthi chal dao tarpor abar jol dao")
    assert len(segments) == 2
    assert segments[1].connector == "tarpor abar"


def test_comma_separated_ingredients_stay_in_one_instruction() -> None:
    text = "একটি পাত্রে তেল গরম করে পেঁয়াজ, আদা, রসুন এবং কাঁচা লঙ্কা দিয়ে ভালো করে কষাতে হবে।"
    segments = _seg(text)
    assert len(segments) == 1
    assert segments[0].original_text == text


# --- Conditional and conversational behaviour ---------------------------------


def test_conditional_jokhon() -> None:
    segments = _seg("জল যখন ফুটবে তখন মুইঠা দাও")
    assert len(segments) == 1
    assert segments[0].conditional == ("যখন",)


def test_conditional_hole_stays_with_action() -> None:
    segments = _seg("আলু সেদ্ধ হলে তুলে নাও")
    assert len(segments) == 1
    assert "হলে" in segments[0].conditional
    assert "আলু সেদ্ধ" in segments[0].text
    assert "তুলে নাও" in segments[0].text


def test_conditional_yotokkhon_na() -> None:
    segments = _seg("যতক্ষণ না জল ফোটে ততক্ষণ ঢাকা দাও")
    assert len(segments) == 1
    assert segments[0].conditional == ("যতক্ষণ না",)


def test_negation_is_preserved() -> None:
    segments = _seg("নুন দেবে না")
    assert len(segments) == 1
    assert segments[0].text == "নুন দেবে না"


def test_self_correction_keeps_original_sequence() -> None:
    segments = _seg("একটু নুন দাও, না না, আরেকটু কম দাও।")
    assert len(segments) == 1
    assert segments[0].text.count("না") == 2
    assert "কম দাও" in segments[0].text
    assert segments[0].original_text == "একটু নুন দাও, না না, আরেকটু কম দাও।"


def test_mixed_conditional_and_sequential() -> None:
    text = "জল গরম হলে মুইঠা দাও। তারপর ঢাকা দিয়ে পাঁচ মিনিট রাখো।"
    segments = _seg(text)
    assert len(segments) == 2
    assert "হলে" in segments[0].conditional
    assert segments[1].connector == "তারপর"


# --- Text preservation --------------------------------------------------------


def test_bengali_numerals_are_preserved() -> None:
    segments = _seg("দুই কাপ জল দাও। তিন চামচ তেল দাও।")
    assert len(segments) == 2
    assert "দুই কাপ জল" in segments[0].text
    assert "তিন চামচ তেল" in segments[1].text


def test_traditional_measurements_are_preserved() -> None:
    text = "এক মুঠো চাল আর এক চিমটি নুন এবং সামান্য হলুদ দাও।"
    segments = _seg(text)
    assert len(segments) == 1
    for phrase in ["এক মুঠো চাল", "এক চিমটি নুন", "সামান্য হলুদ"]:
        assert phrase in segments[0].text


def test_roman_bengali_narration() -> None:
    segments = _seg("prothome tel gorom koro tarpor peyaj dao")
    assert len(segments) == 2
    assert segments[0].text == "prothome tel gorom koro"
    assert segments[1].connector == "tarpor"


def test_mixed_bengali_english_narration() -> None:
    segments = _seg("প্রথমে oil gorom koro। then add onion।")
    assert len(segments) == 2
    assert segments[0].connector == "প্রথমে"
    assert segments[1].connector == "then"


def test_decimal_quantities_are_not_boundaries() -> None:
    segments = _seg("2.5 কাপ জল দাও")
    assert len(segments) == 1
    assert "2.5" in segments[0].text


def test_spoken_quantity_ranges_are_not_boundaries() -> None:
    segments = _seg("panch-chhoy ta lonka dao")
    assert len(segments) == 1
    assert "panch-chhoy" in segments[0].text


def test_compound_measurement_expression() -> None:
    text = "এক মুঠো চাল আর দুই চিমটি নুন"
    segments = _seg(text)
    assert len(segments) == 1
    assert segments[0].text == text


def test_meaningful_punctuation_kinds() -> None:
    segments = _seg("জল দাও। নুন দাও! কি ভাবছো?")
    assert len(segments) == 3


def test_empty_and_whitespace_only_input() -> None:
    assert segment_text("") == ()
    assert segment_text("   \n\t ") == ()


# --- Source-span integrity ----------------------------------------------------


def test_original_spans_slice_valid_substrings() -> None:
    raw = "প্রথমে তেল গরম করো। তারপর পেঁয়াজ দাও!"
    segments = _seg(raw)
    assert len(segments) == 2
    for step in segments:
        assert raw[step.orig_start : step.orig_end] == step.original_text
        assert step.original_text in raw


def test_segment_ordering_is_stable_and_idx_sequential() -> None:
    segments = _seg("এক। দুই। তিন।")
    assert [step.idx for step in segments] == [1, 2, 3]
    assert [step.text for step in segments] == ["এক ।", "দুই ।", "তিন ।"]
    assert [step.orig_start for step in segments] == sorted(step.orig_start for step in segments)


def test_original_text_is_never_modified() -> None:
    raw = "এক মুঠো চাল দিয়ে রান্না করো।"
    result = normalize(raw)
    steps = segment(result)
    assert result.original == raw
    assert raw == "এক মুঠো চাল দিয়ে রান্না করো।"
    assert len(steps) == 1


def test_normalised_and_original_segment_text_correspond() -> None:
    raw = "প্রথমে তেল গরম করো। তারপর পেঁয়াজ দাও।"
    result = normalize(raw)
    for step in segment(result):
        assert step.text == result.text[step.text_start : step.text_end]


def test_repeated_segmentation_is_deterministic() -> None:
    raw = "এক মুঠো চাল। তারপর জল দাও।"
    assert segment(normalize(raw)) == segment(normalize(raw))


def test_connector_retains_original_source_relationship() -> None:
    raw = "chal dhuye nao, tarpor jol dao"
    segments = _seg(raw)
    connector_step = segments[1]
    assert connector_step.connector == "tarpor"
    assert connector_step.original_text == "tarpor jol dao"
    assert "tarpor" in connector_step.original_text
    assert raw[connector_step.orig_start : connector_step.orig_end] == connector_step.original_text


# --- Traditional measurements: no classification -------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "এক মুঠো চাল দিয়ে রান্না করো।",
        "চিতল মাছের মুইঠা তৈরি করতে হবে।",
    ],
)
def test_muthi_and_muitha_are_preserved_without_classification(text: str) -> None:
    segments = _seg(text)
    assert len(segments) == 1
    step = segments[0]
    assert step.connector is None
    assert step.original_text == text
    assert step.conditional == ()


def test_muitha_is_never_treated_as_a_handful_measurement() -> None:
    muitha = _seg("চিতল মাছের মুইঠা তৈরি করতে হবে।")[0]
    muthi = _seg("এক মুঠো চাল দিয়ে রান্না করো।")[0]
    assert "মুইঠা" in muitha.original_text
    assert "মুঠো" in muthi.original_text
    # The segmenter carries no quantity/unit/classification fields at all and
    # adds or removes no words: both words survive in the normalised form too.
    for step in (muitha, muthi):
        assert "মুইঠা" in step.text or "মুঠো" in step.text
        assert step.connector is None
        assert step.conditional == ()


def test_yield_is_not_inferred_or_calculated() -> None:
    segments = _seg("চার জনের জন্য এই রান্না")
    assert len(segments) == 1
    assert segments[0].text == "চার জনের জন্য এই রান্না"


# --- Long real-world narration regression (Chitol Macher Muitha) ---------------


def test_long_narration_regression() -> None:
    raw = FIXTURE.read_text(encoding="utf-8").strip()
    result = normalize(raw)
    steps = segment(result)

    assert len(steps) == 12
    assert [step.idx for step in steps] == list(range(1, 13))

    # Every original source span is valid and complete.
    for step in steps:
        assert raw[step.orig_start : step.orig_end] == step.original_text
        assert step.original_text in raw
    _assert_full_coverage(raw, steps)

    # Meaningful boundaries split the narration into the expected stages.
    expected_phrases = [
        "মাছের কিমা তৈরি",
        "ছোট ছোট মুইঠা গড়ে",
        "জল গরম করে",
        "ভেসে উঠলে",
        "ভেজে তুলে রাখো",
        "পেঁয়াজ কুচি দিয়ে",
        "বাদামি হলে",
        "স্বাদমতো নুন",
        "আলু কাটা",
        "আলু সেদ্ধ হলে",
        "ঘি আর গরম মসলা",
    ]
    phrase_indices = [
        next(i for i, step in enumerate(steps) if phrase in step.original_text)
        for phrase in expected_phrases
    ]
    assert phrase_indices == sorted(phrase_indices), "narration stages must stay in order"

    # Connector and conditional metadata survive on the right segments.
    assert steps[1].connector == "তারপর"
    assert steps[8].connector == "এরপর"
    assert steps[11].connector == "সবশেষে"
    assert steps[3].conditional == ("যখন",)
    assert "হলে" in steps[7].conditional
    assert "হলে" in steps[10].conditional

    # Conditional association and negations are preserved, not split.
    floating = next(step for step in steps if "ভেসে উঠলে" in step.original_text)
    assert "তুলে নাও" in floating.original_text
    boiling = next(step for step in steps if "ফুটতে শুরু করবে" in step.original_text)
    assert "নাড়বে না" in boiling.original_text

    # Traditional measures stay word-for-word; no quantities are invented.
    assert any("সামান্য হলুদ" in step.original_text for step in steps)
    assert any("স্বাদমতো নুন" in step.original_text for step in steps)
    assert "মুইঠা" in raw
