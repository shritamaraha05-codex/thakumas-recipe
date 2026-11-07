"""Deterministic transcript segmentation for Bengali recipe narration (M-06).

This module consumes :class:`~backend.app.parse.normalize.NormalizedText`
(produced by ``normalize.py``, M-05) and splits the narration into ordered
cooking-instruction segments. It is a *structural* stage: it organises what the
cook said, it never reinterprets it.

A :class:`Segment` keeps, for every piece of instruction:

* ``idx``            - 1-based order in the narration;
* ``text``           - the normalised segment text;
* ``original_text``  - the exact original substring (never fabricated from the
                       normalised form);
* ``orig_start`` / ``orig_end`` - half-open span into the original transcript;
* ``text_start`` / ``text_end`` - half-open span into the normalised text;
* ``connector``      - the leading connector phrase, if the segment begins with
                       one (e.g. "তারপর", "prothome");
* ``boundary``       - why the segment started: ``start`` | ``punctuation`` |
                       ``connector``;
* ``conditional``    - condition expressions found inside the segment (tuple of
                       matched phrases, e.g. ``("হলে",)``), when supported.

Only three things ever begin a new segment (each is documented below): the start
of the narration, a sentence-final punctuation token, or a sequence connector.
Commas, negations and conditionals never split a segment, so an instruction such
as "পেঁয়াজ, আদা, রসুন ... কষাতে হবে।" stays one coherent step and a condition
stays attached to the action it governs.

Supported sentence boundaries
    ``।`` (danda), ``.``, ``!``, ``?``, ``;`` and ellipsis (``...`` or ``…``).
    Decimal points inside a number (``2.5``) and hyphens inside a range
    (``panch-chhoy``) are not boundaries. Commas, colons, parentheses, quotes
    and dashes never start a new segment.

Supported connectors (multi-word phrases are matched longest-first)
    প্রথমে, তারপর, এরপর, এবার, শেষে, সবশেষে, একে একে, তারপর আবার;
    prothome, tarpor, erpor, ebar, sheshe, then, phir, uske baad, tarpor abar.
    Connectors are kept, attached to the instruction that follows them, and
    recorded in ``connector`` with their original span preserved.

Conditional handling
    যখন, হলে, যতক্ষণ, যতক্ষণ না, যতক্ষণ পর্যন্ত, না হলে, যখনই. A condition is
    never turned into a standalone segment: the condition and its action stay in
    the same segment (association is structural), and the matched phrase(s) are
    recorded in ``conditional``. The condition is preserved, not interpreted.

Negation and self-correction handling
    না, নয়, করবেন না, দেবে না and corrections such as "না না" are ordinary
    words to this stage: they are never dropped, split or "repaired". A
    correction keeps its original sequence inside one segment; later stages
    (M-08 rules) decide how to use it.

What this module does NOT do (later tasks)
    * lexicon lookup, suffix stripping, fuzzy matching   -> lexicon.py (M-07)
    * number/unit/ingredient/duration extraction         -> rules.py (M-08)
    * yield/servings/weight inference                    -> never (product rule)
    * ingredient or measurement classification           -> later (M-07+)
    * speaker-turn splitting and <2-token fragment merge -> capture (CAP-4)

Limitations (inherited from M-05 and by design)
    * Newlines are collapsed to spaces by ``normalize``, so a line break is not
      a distinguishable boundary here; use the original transcript if it matters.
    * Verb-conditionals spelled as one word (e.g. "উঠলে", "দিলে") are preserved
      but not annotated in ``conditional`` (only the documented list is).
    * Punctuation glued inside a token (e.g. the comma in "ek,dui") is not a
      boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.parse.normalize import NormalizedText, Token, normalize

# Multi-word phrases first so that greedy, longest-first matching never splits a
# compound connector into unrelated pieces ("তারপর আবার" stays one connector).
CONNECTORS: tuple[tuple[str, ...], ...] = (
    ("একে", "একে"),
    ("তারপর", "আবার"),
    ("tarpor", "abar"),
    ("uske", "baad"),
    ("প্রথমে",),
    ("তারপর",),
    ("এরপর",),
    ("এবার",),
    ("শেষে",),
    ("সবশেষে",),
    ("prothome",),
    ("tarpor",),
    ("erpor",),
    ("ebar",),
    ("sheshe",),
    ("then",),
    ("phir",),
)

CONDITIONALS: tuple[tuple[str, ...], ...] = (
    ("যতক্ষণ", "না"),
    ("যতক্ষণ", "পর্যন্ত"),
    ("না", "হলে"),
    ("যখন",),
    ("হলে",),
    ("যতক্ষণ",),
    ("যখনই",),
)

SENTENCE_BOUNDARY_CHARS = frozenset("।.!?;…")


@dataclass(frozen=True, slots=True)
class Segment:
    """One ordered cooking-instruction segment with full source provenance."""

    idx: int
    text: str
    original_text: str
    orig_start: int
    orig_end: int
    text_start: int
    text_end: int
    connector: str | None = None
    boundary: str = "start"
    conditional: tuple[str, ...] = ()


def _is_sentence_boundary(token: Token) -> bool:
    """True for a token that ends a sentence (danda, ., !, ?, ;, ellipsis)."""
    text = token.text
    if text in SENTENCE_BOUNDARY_CHARS:
        return True
    return len(text) > 1 and all(char in ".…" for char in text)


def _match(
    tokens: list[Token], index: int, phrases: tuple[tuple[str, ...], ...]
) -> tuple[str, ...] | None:
    """Return the first phrase (longest-first) matching ``tokens[index:]``."""
    for phrase in phrases:
        end = index + len(phrase)
        if end <= len(tokens) and [token.text for token in tokens[index:end]] == list(phrase):
            return phrase
    return None


def _match_connector(tokens: list[Token], index: int) -> tuple[str, ...] | None:
    return _match(tokens, index, CONNECTORS)


def _match_conditional(tokens: list[Token], index: int) -> tuple[str, ...] | None:
    return _match(tokens, index, CONDITIONALS)


def _find_conditions(tokens: list[Token]) -> tuple[str, ...]:
    """Collect condition phrases present in a segment, in order."""
    conditions: list[str] = []
    index = 0
    while index < len(tokens):
        phrase = _match_conditional(tokens, index)
        if phrase is None:
            index += 1
            continue
        conditions.append(" ".join(phrase))
        index += len(phrase)
    return tuple(conditions)


def _phrase_text(tokens: list[Token], start: int, length: int) -> str:
    return " ".join(token.text for token in tokens[start : start + length])


def segment(normalized: NormalizedText) -> tuple[Segment, ...]:
    """Split a normalised narration into ordered segments.

    Pure and deterministic: the same ``NormalizedText`` always yields the same
    segments, and the original transcript is never modified.
    """
    tokens = list(normalized.tokens)
    segments: list[Segment] = []
    current: list[Token] = []
    connector: str | None = None
    boundary = "start"
    index = 0

    def flush() -> None:
        nonlocal current, connector
        if not current:
            return
        first = current[0]
        last = current[-1]
        segments.append(
            Segment(
                idx=len(segments) + 1,
                text=" ".join(token.text for token in current),
                original_text=normalized.original[first.orig_start : last.orig_end],
                orig_start=first.orig_start,
                orig_end=last.orig_end,
                text_start=first.start,
                text_end=last.end,
                connector=connector,
                boundary=boundary,
                conditional=_find_conditions(current),
            )
        )
        current = []
        connector = None

    while index < len(tokens):
        token = tokens[index]
        phrase = _match_connector(tokens, index)
        boundary_token = _is_sentence_boundary(token)

        if not current:
            # Opening a fresh segment.
            if boundary_token:
                index += 1  # stray boundary (e.g. "।।"): never an empty segment
                continue
            if phrase is not None:
                connector = _phrase_text(tokens, index, len(phrase))
                boundary = "connector" if segments else "start"
                current = tokens[index : index + len(phrase)]
                index += len(phrase)
            else:
                current = [token]
                index += 1
            continue

        if boundary_token:
            current.append(token)
            index += 1
            flush()
            boundary = "punctuation"
            continue

        if phrase is not None:
            flush()
            connector = _phrase_text(tokens, index, len(phrase))
            boundary = "connector"
            current = tokens[index : index + len(phrase)]
            index += len(phrase)
            continue

        current.append(token)
        index += 1

    flush()
    return tuple(segments)


def segment_text(text: str) -> tuple[Segment, ...]:
    """Convenience wrapper: normalize then segment a raw narration."""
    return segment(normalize(text))
