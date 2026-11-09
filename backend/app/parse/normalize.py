"""Deterministic text normalisation for Bengali recipe narration (M-05).

This module turns raw narration text into a canonical, token-friendly form that
later stages (segmentation M-06, lexicon M-07, rules M-08) can consume without
re-guessing spelling, case, digits or spacing. It never edits the original.

Input
    A raw transcript string: Bengali script, Roman Bengali, or mixed
    Bengali/English.

Output
    :class:`NormalizedText` exposes three distinct views of the same words:

    1. ``original`` - the raw input, byte-for-byte untouched;
    2. ``text``     - a single-line normalised form (Latin lower-cased,
                      Bengali/Devanagari digits -> ASCII, single spaces, a
                      space inserted between a number and an attached Latin
                      unit, punctuation preserved as tokens);
    3. ``tokens``   - words and punctuation, each with spans into both ``text``
                      and ``original``, so downstream extraction can quote her
                      exact words (golden rule 5) and validate that anything an
                      LLM suggests is grounded in the transcript.

All functions are pure: no network, database or external services, so they are
trivially testable offline.

What is intentionally NOT done here (later tasks)
    * sentence/step boundary marking and connectors       -> segment.py (M-06)
    * lexicon lookup, suffix stripping, fuzzy matching    -> lexicon.py (M-07)
    * number/unit/ingredient/duration extraction and the
      taste sentinel                                     -> rules.py (M-08)
    * speaker-label stripping                            -> capture (CAP-4)

Limitations
    * Only Bengali and Devanagari *digits* are translated; Devanagari *words*
      (e.g. "कप") are preserved for the lexicon in M-07.
    * No transliteration or fuzzy "correction": spelling variants such as
      "muththi" are kept as spoken. Correcting them is the lexicon's job.
    * Number-letter spacing is applied only to Latin units after a digit
      (``50g`` -> ``50 g``); a Bengali "২কাপ" without a space is left as-is.
    * Edge punctuation is separated into its own tokens; punctuation inside a
      token (e.g. the comma in "ek,dui") is left attached.
    * A leading minus ("-5") is treated as punctuation, not a negative number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_BENGALI_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# Punctuation separated from words into their own tokens. Never removed.
_PUNCTUATION = frozenset("।.,!?;:()[]{}“”\"'‘’…-–—")

# Compound unit phrases collapsed to a canonical token. Evidence: prototype
# ``UNIT_P`` and docs/05 case 19 ("ek choto chamoch nun" -> salt 1 tsp, no
# question). Non-destructive: ``original`` still holds "choto chamoch".
UNIT_ALIASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("choto", "chamoch"), "tsp"),
    (("chhoto", "chamoch"), "tsp"),
    (("ছোট", "চামচ"), "tsp"),
    (("boro", "chamoch"), "tbsp"),
    (("বড়", "চামচ"), "tbsp"),
)

_NUM_LETTER_BOUNDARY = re.compile(r"(?<=\d)(?=[A-Za-z])")
_WORD = re.compile(r"\S+")


@dataclass(frozen=True, slots=True)
class Token:
    """One word or punctuation mark.

    ``start``/``end`` index into :attr:`NormalizedText.text`;
    ``orig_start``/``orig_end`` index into :attr:`NormalizedText.original`.
    """

    text: str
    start: int
    end: int
    orig_start: int
    orig_end: int


@dataclass(frozen=True, slots=True)
class NormalizedText:
    original: str
    text: str
    tokens: tuple[Token, ...]

    def original_span(self, token: Token) -> str:
        """Slice the original transcript covered by ``token``."""
        return self.original[token.orig_start : token.orig_end]


# Internal working type: (token text, original start, original end).
RawToken = tuple[str, int, int]


def translate_digits(text: str) -> str:
    """Translate Bengali and Devanagari digits to ASCII."""
    return text.translate(_BENGALI_DIGITS).translate(_DEVANAGARI_DIGITS)


def lowercase(text: str) -> str:
    """Lowercase text (affects Latin only; Bengali/Devanagari have no case)."""
    return text.lower()


def collapse_whitespace(text: str) -> str:
    """Replace every run of whitespace with a single space and trim."""
    return re.sub(r"\s+", " ", text).strip()


def _split_edges(word: str) -> tuple[str, str, str]:
    """Return (leading punctuation, core, trailing punctuation) of a word."""
    lead = 0
    while lead < len(word) and word[lead] in _PUNCTUATION:
        lead += 1
    tail = len(word)
    while tail > lead and word[tail - 1] in _PUNCTUATION:
        tail -= 1
    return word[:lead], word[lead:tail], word[tail:]


def _tokenize_raw(text: str) -> list[RawToken]:
    """Split on whitespace, then separate edge punctuation into own tokens."""
    tokens: list[RawToken] = []
    for match in _WORD.finditer(text):
        word = match.group(0)
        lead, core, tail = _split_edges(word)
        pos = match.start()
        if lead:
            tokens.append((lead, pos, pos + len(lead)))
            pos += len(lead)
        if core:
            tokens.append((core, pos, pos + len(core)))
            pos += len(core)
        if tail:
            tokens.append((tail, pos, pos + len(tail)))
    return tokens


def _normalize_token(token: RawToken) -> RawToken:
    text, start, end = token
    return (translate_digits(lowercase(text)), start, end)


def _split_quantity_units(tokens: list[RawToken]) -> list[RawToken]:
    """Insert a space between a number and an attached Latin unit (``50g``)."""
    result: list[RawToken] = []
    for text, start, end in tokens:
        boundaries = [match.start() for match in _NUM_LETTER_BOUNDARY.finditer(text)]
        if not boundaries:
            result.append((text, start, end))
            continue
        cuts = [0, *boundaries, len(text)]
        for left, right in zip(cuts, cuts[1:]):
            result.append((text[left:right], start + left, start + right))
    return result


def _apply_unit_aliases(tokens: list[RawToken]) -> list[RawToken]:
    """Collapse compound unit phrases (e.g. ``choto chamoch``) to one token."""
    result: list[RawToken] = []
    index = 0
    while index < len(tokens):
        phrase: tuple[str, ...] | None = None
        replacement: str | None = None
        for candidate, alias in UNIT_ALIASES:
            window = [text for text, _, _ in tokens[index : index + len(candidate)]]
            if window == list(candidate):
                phrase, replacement = candidate, alias
                break
        if phrase is None or replacement is None:
            result.append(tokens[index])
            index += 1
            continue
        first_start = tokens[index][1]
        last_end = tokens[index + len(phrase) - 1][2]
        result.append((replacement, first_start, last_end))
        index += len(phrase)
    return result


def _build(original: str, tokens: list[RawToken]) -> NormalizedText:
    parts: list[str] = []
    final: list[Token] = []
    position = 0
    for text, orig_start, orig_end in tokens:
        parts.append(text)
        final.append(
            Token(
                text=text,
                start=position,
                end=position + len(text),
                orig_start=orig_start,
                orig_end=orig_end,
            )
        )
        position += len(text) + 1
    return NormalizedText(original=original, text=" ".join(parts), tokens=tuple(final))


def normalize(text: str) -> NormalizedText:
    """Normalise ``text`` into a canonical form while preserving the original."""
    tokens = _tokenize_raw(text)
    tokens = [_normalize_token(token) for token in tokens]
    tokens = _split_quantity_units(tokens)
    tokens = _apply_unit_aliases(tokens)
    return _build(text, tokens)
