"""Offline unit tests for ``backend/app/parse/lexicon.py`` (M-07).

Everything here runs without the network, an LLM or any provider. The lexical
tables are checked against the M-07 brief, ``docs/05_PARSER_SPEC.md`` cases,
``docs/06_UNITS_REFERENCE.md`` and the Chitol Macher Muitha fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.parse.lexicon import (
    ALL_ENTRIES,
    LEXICON,
    Category,
    Entry,
    Lexicon,
    Match,
)
from backend.app.parse.normalize import normalize

FIXTURE = Path(__file__).parent / "fixtures" / "chitol_macher_muitha_narration.txt"


def _canon(tokens: list[str]) -> list[str]:
    return [match.canonical for match in LEXICON.find(tokens)]


def _canon_text(text: str) -> list[str]:
    return [match.canonical for match in LEXICON.find_in(normalize(text))]


def _canon_word(word: str) -> str:
    match = LEXICON.lookup(word)
    assert match is not None
    return match.canonical


# --------------------------------------------------------------------------- #
# 1. Exact Bengali ingredient matching                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("word", "canonical"),
    [
        ("চাল", "rice"),
        ("ডাল", "lentils"),
        ("আলু", "potato"),
        ("পেঁয়াজ", "onion"),
        ("আদা", "ginger"),
        ("রসুন", "garlic"),
        ("হলুদ", "turmeric"),
        ("জিরে", "cumin"),
        ("নুন", "salt"),
        ("চিনি", "sugar"),
        ("ঘি", "ghee"),
    ],
)
def test_exact_bengali_ingredients(word: str, canonical: str) -> None:
    match = LEXICON.lookup(word)
    assert match is not None
    assert match.canonical == canonical
    assert match.category is Category.INGREDIENT
    assert match.method == "exact"
    assert match.surface == word


# --------------------------------------------------------------------------- #
# 2. Roman Bengali ingredient aliases                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("word", "canonical"),
    [
        ("chal", "rice"),
        ("peyaj", "onion"),
        ("holud", "turmeric"),
        ("jeera", "cumin"),
        ("nun", "salt"),
        ("chini", "sugar"),
        ("dudh", "milk"),
        ("ghee", "ghee"),
    ],
)
def test_roman_bengali_ingredient_aliases(word: str, canonical: str) -> None:
    match = LEXICON.lookup(word)
    assert match is not None
    assert match.canonical == canonical
    assert match.category is Category.INGREDIENT
    assert match.method == "alias"


# --------------------------------------------------------------------------- #
# 3. Mixed-script vocabulary                                                  #
# --------------------------------------------------------------------------- #


def test_mixed_script_narration_recognition() -> None:
    canon = _canon_text("Ek muthi chal ar ২ কাপ জল")
    assert canon == ["1", "muthi", "rice", "2", "cup", "water"]

    result = normalize("Ek muthi chal ar ২ কাপ জল")
    categories = {match.category for match in LEXICON.find_in(result)}
    assert categories == {Category.NUMBER, Category.MEASURE, Category.INGREDIENT}


# --------------------------------------------------------------------------- #
# 4. Ingredient aliases                                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("word", "canonical"),
    [
        ("dhone", "coriander"),
        ("dhonepata", "coriander leaves"),
        ("jol", "water"),
        ("alu", "potato"),
        ("lonka", "chilli"),
        ("moyda", "flour"),
    ],
)
def test_ingredient_aliases(word: str, canonical: str) -> None:
    match = LEXICON.lookup(word)
    assert match is not None
    assert match.canonical == canonical


# --------------------------------------------------------------------------- #
# 5. Traditional measurement recognition                                      #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("word", "canonical"),
    [
        ("মুঠো", "muthi"),
        ("মুঠি", "muthi"),
        ("চিমটি", "chimti"),
        ("চামচ", "spoon"),
        ("বাটি", "bowl"),
        ("কাপ", "cup"),
        ("গ্লাস", "glass"),
        ("সের", "ser"),
        ("সামান্য", "a little"),
        ("অল্প অল্প", "little by little"),
        ("পরিমাণমতো", "as needed"),
        ("স্বাদমতো", "to taste"),
    ],
)
def test_traditional_measurements(word: str, canonical: str) -> None:
    match = LEXICON.lookup(word)
    assert match is not None
    assert match.canonical == canonical
    assert match.category is Category.MEASURE


def test_measurements_are_not_ingredients() -> None:
    for word in ("মুঠো", "চিমটি", "কাপ", "সামান্য"):
        match = LEXICON.lookup(word)
        assert match is not None
        assert match.category is not Category.INGREDIENT


def test_to_taste_marker_is_recorded() -> None:
    match = LEXICON.lookup("স্বাদমতো")
    assert match is not None
    assert match.to_taste is True
    assert match.kind == "taste"


# --------------------------------------------------------------------------- #
# 6. Compound measurement expressions                                         #
# --------------------------------------------------------------------------- #


def test_compound_measurement_is_one_match_after_normalisation() -> None:
    result = normalize("ek choto chamoch nun")
    matches = LEXICON.find_in(result)
    canon = [match.canonical for match in matches]
    assert canon == ["1", "tsp", "salt"]
    tsp = matches[1]
    assert tsp.surface == "choto chamoch"
    assert result.original[tsp.orig_start : tsp.orig_end] == "choto chamoch"


def test_compound_measurement_when_tokens_are_raw() -> None:
    matches = LEXICON.find(["ek", "ছোট", "চামচ", "নুন"])
    assert [match.canonical for match in matches] == ["1", "tsp", "salt"]
    assert matches[1].method == "phrase"


def test_boro_chamoch_is_tbsp() -> None:
    assert _canon_text("ek boro chamoch tel") == ["1", "tbsp", "oil"]


# --------------------------------------------------------------------------- #
# 7. Bengali number words                                                     #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("word", "value"),
    [
        ("এক", 1),
        ("দুই", 2),
        ("তিন", 3),
        ("দশ", 10),
        ("একটা", 1),
        ("একজোড়া", 1),
        ("আড়াই", 2.5),
        ("দেড়", 1.5),
        ("আধা", 0.5),
    ],
)
def test_bengali_number_words(word: str, value: float) -> None:
    match = LEXICON.lookup(word)
    assert match is not None
    assert match.category is Category.NUMBER
    assert match.value == value


def test_sadhe_is_an_add_half_modifier_not_a_number() -> None:
    match = LEXICON.lookup("সাড়ে")
    assert match is not None
    assert match.kind == "add_half"
    assert match.value == 0.5


def test_egyora_classifier_metadata() -> None:
    match = LEXICON.lookup("একজোড়া")
    assert match is not None
    assert match.classifier == "pair"


# --------------------------------------------------------------------------- #
# 8. Roman Bengali number words                                               #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("word", "value"),
    [("ek", 1), ("du", 2), ("dosh", 10), ("arai", 2.5), ("der", 1.5), ("dhai", 2.5)],
)
def test_roman_number_words(word: str, value: float) -> None:
    match = LEXICON.lookup(word)
    assert match is not None
    assert match.value == value


# --------------------------------------------------------------------------- #
# 9. Devanagari digits and number words (docs/05 case 22)                     #
# --------------------------------------------------------------------------- #


def test_devanagari_case_22() -> None:
    canon = _canon_text("आधा कप २ दूध")
    assert canon == ["0.5", "cup", "2", "milk"]


def test_devanagari_word_lookups() -> None:
    adha = LEXICON.lookup("आधा")
    kap = LEXICON.lookup("कप")
    dudh = LEXICON.lookup("दूध")
    assert adha is not None and adha.value == 0.5
    assert kap is not None and kap.canonical == "cup"
    assert dudh is not None and dudh.canonical == "milk"


# --------------------------------------------------------------------------- #
# 10. Numeric ranges                                                          #
# --------------------------------------------------------------------------- #


def test_numeric_range() -> None:
    match = LEXICON.lookup("5-6")
    assert match is not None
    assert match.category is Category.NUMBER
    assert (match.value, match.value_max) == (5, 6)
    assert match.canonical == "5-6"


def test_numeric_range_inside_narration() -> None:
    canon = _canon_text("5-6 lonka dao")
    assert canon == ["5-6", "chilli"]


# --------------------------------------------------------------------------- #
# 11. Spoken ranges                                                           #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("word", "low", "high"),
    [("panch-chhoy", 5, 6), ("tin-char", 3, 4)],
)
def test_spoken_ranges(word: str, low: int, high: int) -> None:
    match = LEXICON.lookup(word)
    assert match is not None
    assert (match.value, match.value_max) == (low, high)


def test_spoken_range_does_not_become_two_items() -> None:
    assert _canon_text("panch-chhoy ta lonka") == ["5-6", "chilli"]


# --------------------------------------------------------------------------- #
# 12. Duration recognition                                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("word", "canonical"),
    [("মিনিট", "minute"), ("ঘণ্টা", "hour"), ("সেকেন্ড", "second"), ("minute", "minute")],
)
def test_duration_words(word: str, canonical: str) -> None:
    match = LEXICON.lookup(word)
    assert match is not None
    assert match.canonical == canonical
    assert match.category is Category.DURATION


def test_vague_durations_are_marked() -> None:
    match = LEXICON.lookup("কিছুক্ষণ")
    assert match is not None
    assert match.category is Category.DURATION
    assert match.kind == "vague"


def test_duration_is_not_a_measure_or_yield() -> None:
    canon = _canon_text("পাঁচ মিনিট রান্না করো")
    assert canon == ["5", "minute"]


def test_duration_is_not_confused_with_ingredient_quantity() -> None:
    matches = LEXICON.find(["দশ", "মিনিট"])
    assert [match.canonical for match in matches] == ["10", "minute"]
    assert all(match.category is not Category.INGREDIENT for match in matches)


# --------------------------------------------------------------------------- #
# 13. Longest-match-first behaviour                                           #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("tokens", "canonical"),
    [
        (["সরষের", "তেল"], "mustard oil"),
        (["কাঁচা", "লঙ্কা"], "green chilli"),
        (["টমেটো", "বাটা"], "tomato paste"),
        (["গোটা", "জিরে"], "whole cumin"),
        (["গোটা", "গরম", "মশলা"], "whole garam masala"),
        (["গরম", "মশলা"], "garam masala"),
        (["লঙ্কার", "গুঁড়ো"], "chilli powder"),
        (["ধনের", "গুঁড়ো"], "coriander powder"),
    ],
)
def test_longest_match_first(tokens: list[str], canonical: str) -> None:
    assert _canon(tokens) == [canonical]


def test_whole_garam_masala_beats_garam_masala() -> None:
    three = LEXICON.find(["গোটা", "গরম", "মশলা"])
    two = LEXICON.find(["গরম", "মশলা"])
    assert [m.canonical for m in three] == ["whole garam masala"]
    assert [m.canonical for m in two] == ["garam masala"]


# --------------------------------------------------------------------------- #
# 14. Conservative suffix stripping                                           #
# --------------------------------------------------------------------------- #


def test_genitive_suffix_is_stripped_when_stem_is_known() -> None:
    match = LEXICON.lookup("মাছের")
    assert match is not None
    assert match.canonical == "fish"
    assert match.method == "suffix"
    assert match.surface == "মাছের"


def test_classifier_suffix_is_stripped_and_recorded() -> None:
    match = LEXICON.lookup("তিনটা")
    assert match is not None
    assert match.value == 3
    assert match.classifier == "টা"
    assert match.method == "suffix"


def test_exact_match_wins_over_suffix_stripping() -> None:
    # "একটা" is its own entry; it must not be reduced to "এক".
    match = LEXICON.lookup("একটা")
    assert match is not None
    assert match.method == "exact"
    assert match.canonical == "1"


def test_suffix_stripping_never_creates_a_match() -> None:
    # "মুইঠাগুলো" ends with the classifier "গুলো" but "মুইঠা" is not a unit.
    assert LEXICON.lookup("মুইঠাগুলো") is None


def test_locative_suffix_is_not_stripped() -> None:
    # Stripping "ে" would turn the connector "একে একে" into the number 1.
    assert LEXICON.lookup("একে") is None


def test_suffix_stripping_does_not_destroy_genuine_names() -> None:
    assert _canon_word("টমেটো") == "tomato"
    assert _canon_word("হলুদ") == "turmeric"


# --------------------------------------------------------------------------- #
# 15. Fuzzy match suggestions                                                 #
# --------------------------------------------------------------------------- #


def test_fuzzy_suggestion_finds_ingredient() -> None:
    suggestions = LEXICON.suggest("peyajj")
    assert [match.canonical for match in suggestions] == ["onion"]
    assert suggestions[0].method == "fuzzy"
    assert 0.85 <= suggestions[0].confidence < 1.0
    assert suggestions[0].surface == "peyajj"


def test_fuzzy_suggestion_second_example() -> None:
    suggestions = LEXICON.suggest("jeerra")
    assert "cumin" in [match.canonical for match in suggestions]


def test_fuzzy_is_not_applied_to_unknown_or_non_ascii() -> None:
    assert LEXICON.suggest("xyzzy") == ()
    assert LEXICON.suggest("চাল") == ()
    assert LEXICON.suggest("ta") == ()


def test_fuzzy_never_changes_a_match_in_find() -> None:
    assert LEXICON.find(["peyajj"]) == ()


# --------------------------------------------------------------------------- #
# 16. Ambiguous matches                                                       #
# --------------------------------------------------------------------------- #


def test_plain_chamoch_is_ambiguous() -> None:
    match = LEXICON.lookup("chamoch")
    assert match is not None
    assert match.ambiguous is True
    assert match.options == ("tsp", "tbsp")


def test_ambiguity_survives_phrase_scan() -> None:
    matches = LEXICON.find(["ek", "chamoch", "tel"])
    spoon = next(match for match in matches if match.canonical == "spoon")
    assert spoon.ambiguous is True
    assert spoon.options == ("tsp", "tbsp")


def test_cup_is_ambiguous_with_options() -> None:
    match = LEXICON.lookup("কাপ")
    assert match is not None
    assert match.ambiguous is True
    assert match.options == ("tea cup", "measuring cup", "my cup")


def test_resolved_compound_is_not_ambiguous() -> None:
    match = LEXICON.lookup("choto chamoch")
    assert match is not None
    assert match.canonical == "tsp"
    assert match.ambiguous is False


# --------------------------------------------------------------------------- #
# 17. Similar-looking but semantically different words                        #
# --------------------------------------------------------------------------- #


def test_similar_looking_words_stay_distinct() -> None:
    assert _canon_word("চাল") == "rice"
    assert LEXICON.lookup("চল") is None
    assert _canon_word("তেল") == "oil"
    assert LEXICON.lookup("ঠেল") is None
    assert _canon_word("দুধ") == "milk"
    assert _canon_word("দুই") == "2"


def test_muitha_is_not_in_the_vocabulary_at_all() -> None:
    assert LEXICON.lookup("মুইঠা") is None
    assert LEXICON.lookup("মুঠা") is None


# --------------------------------------------------------------------------- #
# 18. মুঠো versus মুইঠা                                                       #
# --------------------------------------------------------------------------- #


def test_mutho_is_a_handful() -> None:
    match = LEXICON.lookup("মুঠো")
    assert match is not None
    assert (match.canonical, match.category) == ("muthi", Category.MEASURE)


def test_muitha_is_never_a_handful() -> None:
    assert LEXICON.find(["মুইঠা"]) == ()
    canon = _canon_text("চিতল মাছের মুইঠা তৈরি করতে হবে")
    assert "muthi" not in canon
    assert "chitol fish" in canon


def test_mutho_and_muitha_together() -> None:
    canon = _canon_text("এক মুঠো চাল আর মুইঠা")
    assert "muthi" in canon
    # Only one handful was spoken; মুইঠা added nothing.
    assert canon.count("muthi") == 1


# --------------------------------------------------------------------------- #
# 19. Original source preservation                                            #
# --------------------------------------------------------------------------- #


def test_original_transcript_is_never_modified() -> None:
    raw = "এক মুঠো চাল দাও।"
    result = normalize(raw)
    matches = LEXICON.find_in(result)
    assert result.original == raw
    assert matches
    muthi = next(match for match in matches if match.canonical == "muthi")
    rice = next(match for match in matches if match.canonical == "rice")
    assert muthi.surface == "মুঠো"
    assert rice.surface == "চাল"


def test_surface_is_her_word_not_the_canonical_name() -> None:
    raw = "এক মুঠো চাল"
    matches = LEXICON.find_in(normalize(raw))
    surfaces = {match.surface for match in matches}
    assert "muthi" not in surfaces
    assert "rice" not in surfaces
    assert surfaces == {"এক", "মুঠো", "চাল"}


def test_fuzzy_surface_is_the_input_word() -> None:
    suggestions = LEXICON.suggest("peyajj")
    assert suggestions[0].surface == "peyajj"
    assert suggestions[0].surface != suggestions[0].canonical


# --------------------------------------------------------------------------- #
# 20. Source-span correctness                                                 #
# --------------------------------------------------------------------------- #


def test_source_spans_are_correct() -> None:
    raw = "প্রথমে চিতল মাছের কিমা তৈরি করো।"
    result = normalize(raw)
    matches = LEXICON.find_in(result)
    assert matches
    for match in matches:
        assert match.orig_start is not None and match.orig_end is not None
        assert raw[match.orig_start : match.orig_end] == match.surface
        assert match.char_start is not None and match.char_end is not None
        assert match.char_start < match.char_end <= len(result.text)
        assert 0 <= match.token_start < match.token_end <= len(result.tokens)


def test_phrase_span_covers_both_words() -> None:
    raw = "চিতল মাছের কিমা"
    matches = LEXICON.find_in(normalize(raw))
    chitol = next(match for match in matches if match.canonical == "chitol fish")
    assert chitol.surface == "চিতল মাছের"
    assert (chitol.token_start, chitol.token_end) == (0, 2)


# --------------------------------------------------------------------------- #
# 21. Deterministic lookup                                                    #
# --------------------------------------------------------------------------- #


def test_lookup_is_deterministic() -> None:
    tokens = ["ek", "muthi", "chal", "ar", "সরষের", "তেল"]
    assert LEXICON.find(tokens) == LEXICON.find(tokens)
    assert LEXICON.lookup("চাল") == LEXICON.lookup("চাল")
    assert LEXICON.suggest("peyajj") == LEXICON.suggest("peyajj")


def test_a_fresh_lexicon_matches_the_shared_one() -> None:
    fresh = Lexicon(ALL_ENTRIES)
    tokens = ["dui", "chamoch", "chini"]
    assert fresh.find(tokens) == LEXICON.find(tokens)


def test_conflicting_forms_are_rejected() -> None:
    first = Entry("one", Category.MEASURE, ("duplicate",), kind="unit")
    second = Entry("two", Category.MEASURE, ("duplicate",), kind="unit")
    with pytest.raises(ValueError):
        Lexicon([first, second])


# --------------------------------------------------------------------------- #
# 22. Unknown words stay unknown                                              #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("word", ["ঝোল", "কড়াই", "কুচি", "বাদামি", "হাঁড়িতে"])
def test_unknown_words_remain_unknown(word: str) -> None:
    assert LEXICON.lookup(word) is None


def test_unknown_words_are_skipped_not_corrected() -> None:
    matches = LEXICON.find(["chal", "ঝোল", "nun"])
    assert [match.canonical for match in matches] == ["rice", "salt"]


# --------------------------------------------------------------------------- #
# 23. Chitol Macher Muitha narration regression                               #
# --------------------------------------------------------------------------- #


def test_chitol_narration_lexical_recognition() -> None:
    raw = FIXTURE.read_text(encoding="utf-8").strip()
    result = normalize(raw)
    matches = LEXICON.find_in(result)
    canon = {match.canonical for match in matches}

    required = {
        "chitol fish",
        "fish",
        "potato",
        "onion",
        "ginger",
        "garlic",
        "ginger garlic paste",
        "green chilli",
        "turmeric",
        "chilli powder",
        "oil",
        "tomato",
        "salt",
        "water",
        "ghee",
        "garam masala",
        "a little",
        "to taste",
        "minute",
    }
    assert required <= canon

    # The narration says "পাঁচ মিনিট".
    assert "5" in canon
    assert "minute" in canon

    # "মুইঠা" is the fish preparation here; it must never become a handful.
    assert "muthi" not in canon
    assert "মুইঠা" in raw

    # Nothing is invented and every surface is really in the transcript.
    assert result.original == raw
    for match in matches:
        assert match.surface in raw


def test_chitol_narration_is_deterministic() -> None:
    raw = FIXTURE.read_text(encoding="utf-8").strip()
    first = LEXICON.find_in(normalize(raw))
    second = LEXICON.find_in(normalize(raw))
    assert first == second


def test_match_dataclass_exposes_provenance_fields() -> None:
    raw = "এক চিমটি নুন"
    match: Match = LEXICON.find_in(normalize(raw))[0]
    assert match.surface == "এক"
    assert match.category is Category.NUMBER
    assert match.orig_start == 0
