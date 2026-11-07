"""Unit tests for ``backend/app/parse/normalize.py`` (M-05)."""

from __future__ import annotations

import pytest

from backend.app.parse.normalize import (
    collapse_whitespace,
    lowercase,
    normalize,
    translate_digits,
)


# --- Preservation of the original transcript ---------------------------------


def test_original_is_never_overwritten() -> None:
    raw = "ek muthi chal"
    result = normalize(raw)
    assert result.original == raw
    assert raw == "ek muthi chal"


def test_tokens_map_back_to_original_substrings() -> None:
    raw = "ek muthi chal, ২ কাপ জল"
    result = normalize(raw)
    for token in result.tokens:
        assert result.original_span(token) in raw
    assert [result.original_span(token) for token in result.tokens] == [
        "ek",
        "muthi",
        "chal",
        ",",
        "২",
        "কাপ",
        "জল",
    ]


def test_normalize_is_deterministic() -> None:
    raw = "EK Muthi চাল ar ২ কাপ জল।"
    assert normalize(raw) == normalize(raw)


def test_all_original_words_survive_in_tokens() -> None:
    raw = "alu kuchi kore kete dao, tarpor oile tel diye vaja koro"
    result = normalize(raw)
    for word in raw.split():
        expected = word.strip(",.").lower()
        assert any(token.text == expected for token in result.tokens), word


def test_no_transliteration_or_fuzzy_correction() -> None:
    result = normalize("muththi chawal chutki")
    assert result.text == "muththi chawal chutki"


# --- Scripts and case ---------------------------------------------------------


def test_roman_bengali_text() -> None:
    result = normalize("Ek Muthi Chal ar ek chimti nun")
    assert result.text == "ek muthi chal ar ek chimti nun"


def test_latin_case_is_lowercased() -> None:
    assert normalize("ONE CUP WATER").text == "one cup water"


def test_bengali_script_is_preserved() -> None:
    result = normalize("এক মুঠো চাল আর এক চিমটি নুন")
    assert result.text == "এক মুঠো চাল আর এক চিমটি নুন"
    assert all(token.text for token in result.tokens)


def test_bengali_digits_are_translated() -> None:
    result = normalize("২ কাপ জল")
    assert result.text == "2 কাপ জল"
    assert result.tokens[0].text == "2"
    assert result.tokens[0].orig_start == 0


def test_devnagari_digits_are_translated_but_words_preserved() -> None:
    result = normalize("आधा कप २ दूध")
    assert "2" in result.text
    assert "कप" in result.text


def test_mixed_script_narration() -> None:
    result = normalize("Ek muthi chal ar ২ কাপ জল")
    assert result.text == "ek muthi chal ar 2 কাপ জল"


# --- Numerals and quantity expressions ----------------------------------------


def test_bengali_decimal_stays_intact() -> None:
    result = normalize("আড়াই ২.৫ কাপ")
    assert "2.5" in result.text
    assert [token.text for token in result.tokens if token.text == "2.5"] == ["2.5"]


def test_number_and_unit_are_spaced_with_precise_spans() -> None:
    result = normalize("50g chal ar 2cup jol")
    assert result.text == "50 g chal ar 2 cup jol"
    unit = result.tokens[1]
    assert unit.text == "g"
    assert result.original_span(unit) == "g"
    assert result.original_span(result.tokens[0]) == "50"


def test_hyphen_range_and_decimal_are_not_split() -> None:
    result = normalize("panch-chhoy ta lonka ar 2.5 kap jol")
    texts = [token.text for token in result.tokens]
    assert "panch-chhoy" in texts
    assert "2.5" in texts


def test_number_words_are_not_converted() -> None:
    assert normalize("dosh minute").text == "dosh minute"


# --- Whitespace and punctuation -----------------------------------------------


def test_whitespace_is_collapsed() -> None:
    result = normalize("ek   muthi\n\tchal\r\n")
    assert result.text == "ek muthi chal"
    assert result.tokens[0].text == "ek"


def test_punctuation_is_split_but_preserved() -> None:
    result = normalize("jol dao। boro kore koro!")
    assert "।" in result.text
    assert "!" in result.text
    puncts = [token.text for token in result.tokens if token.text in {"।", "!"}]
    assert puncts == ["।", "!"]


def test_self_correction_words_and_ellipsis_preserved() -> None:
    result = normalize("ek chamoch... na na dui chamoch chini")
    assert "na na" in result.text
    assert "..." in result.text
    texts = [token.text for token in result.tokens]
    assert texts.count("na") == 2


# --- Negations ----------------------------------------------------------------


def test_negations_are_preserved() -> None:
    result = normalize("jol na diye nun ta na dao")
    assert result.text == "jol na diye nun ta na dao"


def test_bengali_negation_is_preserved() -> None:
    assert "না" in normalize("নুন না দিও").text


# --- Unit aliases -------------------------------------------------------------


def test_unit_alias_choto_chamoch_becomes_tsp() -> None:
    result = normalize("ek choto chamoch nun")
    assert result.text == "ek tsp nun"
    tsp = result.tokens[1]
    assert tsp.text == "tsp"
    assert result.original_span(tsp) == "choto chamoch"


def test_unit_alias_boro_chamoch_becomes_tbsp() -> None:
    assert normalize("ek boro chamoch tel").text == "ek tbsp tel"


def test_unit_alias_bengali_chamoch() -> None:
    assert normalize("এক ছোট চামচ নুন").text == "এক tsp নুন"


# --- Taste phrase is not destructively replaced --------------------------------


def test_taste_phrase_is_not_replaced_by_sentinel() -> None:
    result = normalize("nun jemon lage")
    assert result.text == "nun jemon lage"
    assert "<taste>" not in result.text


# --- Empty input and pure helpers ---------------------------------------------


def test_empty_and_whitespace_only_input() -> None:
    empty = normalize("")
    assert empty.text == ""
    assert empty.tokens == ()
    assert normalize("   \n\t  ").text == ""


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("১২৩", "123"),
        ("०४५", "045"),
        ("৬ ७", "6 7"),
        ("2.5", "2.5"),
    ],
)
def test_translate_digits(text: str, expected: str) -> None:
    assert translate_digits(text) == expected


def test_collapse_whitespace_pure() -> None:
    assert collapse_whitespace(" a   b\n\tc ") == "a b c"


def test_lowercase_pure() -> None:
    assert lowercase("Ek Muthi") == "ek muthi"
