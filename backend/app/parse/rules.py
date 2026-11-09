"""Deterministic rules parser for Bengali recipe narration (M-08).

``parse_rules`` consumes the M-05 ``NormalizedText`` and M-06 ``Segment``
structures and the M-07 ``Lexicon`` matches and produces the internal
``parse.schema.ParseResult``. It is pure, offline and deterministic: the same
input always yields the same result, no LLM or network is involved, and the
original transcript is never modified.

Association strategy (the only thing this stage decides)
    Within one segment the recognised matches are scanned left to right. A
    *number* immediately followed by a *measure* forms one quantity; the same
    number immediately followed by a *duration* forms a duration (never an
    ingredient quantity). A quantity is attached to an ingredient only when the
    quantity's last token is immediately adjacent to the ingredient's first
    token. A bare number is attached as a count (unit left ``None``) only when
    it is immediately adjacent to the ingredient. Anything that is not adjacent
    is left unattached rather than guessed, so "একটা বড় হাঁড়িতে জল" never
    makes the water "1".

What is deliberately NOT done
    * no conversion of traditional measures to grams/millilitres;
    * no missing-unit inference (a count keeps ``unit=None``);
    * no cooking-time inference (durations stay in minute/hour/second);
    * no yield/servings/total inference, no scaling;
    * no fuzzy matching: only confirmed lexicon matches are used.

Clarifications
    An ambiguous measure (plain ``চামচ`` or uncalibrated ``কাপ``) keeps its
    spoken unit, gets a deterministic id (``unit_spoon_1``, ``unit_cup_1``, ...)
    and a question in ``ParseResult.clarifications``. Resolved compounds such as
    ``ছোট চামচ``/``বড় চামচ`` (already normalised to ``tsp``/``tbsp``) do not
    trigger a question. Personal calibration is out of scope here.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.models import Clarification, ParserMode, Source
from backend.app.parse.lexicon import LEXICON, Category, Lexicon, Match
from backend.app.parse.normalize import NormalizedText, normalize
from backend.app.parse.schema import (
    Duration,
    IngredientMention,
    ParseResult,
    Quantity,
    QuantityKind,
    RecipeStep,
)
from backend.app.parse.segment import Segment, segment

__all__ = ["parse_rules", "parse_rules_text"]

# Canonical unit -> clarification kind (docs/05 ambiguity table).
_CLARIFICATION_KINDS: dict[str, str] = {
    "spoon": "unit_spoon",
    "cup": "unit_cup",
}

# Stable, documented clarifications. The id is ``<kind>_<n>`` where ``n`` counts
# occurrences of that kind in narration order, so it is deterministic.
_CLARIFICATION_SPECS: dict[str, tuple[str, tuple[str, ...]]] = {
    "unit_spoon": (
        "এক চামচ মানে কোনটি — ছোট চামচ (চা-চামচ) না বড় চামচ (ভাত-চামচ)?",
        ("tsp", "tbsp"),
    ),
    "unit_cup": (
        "কোন কাপটি দিয়ে মাপছেন — চায়ের কাপ, মাপার কাপ, না আপনার নিজের কাপ?",
        ("tea cup", "measuring cup", "my cup"),
    ),
}

_BASE_CONFIDENCE: dict[QuantityKind, float] = {
    QuantityKind.EXACT: 1.0,
    QuantityKind.RANGE: 1.0,
    QuantityKind.VAGUE: 0.7,
    QuantityKind.TASTE: 0.9,
    QuantityKind.UNRESOLVED: 0.6,
}
_COUNT_CONFIDENCE = 0.8
_AMBIGUOUS_CONFIDENCE = 0.7


@dataclass(frozen=True, slots=True)
class _Number:
    """A recognised number awaiting a measure, duration or ingredient."""

    value: float | None
    value_max: float | None
    classifier: str | None
    token_start: int
    token_end: int
    orig_start: int
    orig_end: int


def parse_rules(normalized: NormalizedText, lexicon: Lexicon = LEXICON) -> ParseResult:
    """Parse a normalised narration into the internal :class:`ParseResult`."""
    steps = segment(normalized)
    matches = lexicon.find_in(normalized)
    counters: dict[str, int] = {}
    clarifications: list[Clarification] = []
    recipe_steps: list[RecipeStep] = []
    mentions: list[IngredientMention] = []

    for step in steps:
        step_matches = [
            match
            for match in matches
            if step.orig_start <= _span(match)[0] and _span(match)[1] <= step.orig_end
        ]
        built = _build_step(step, step_matches, normalized.original, counters, clarifications)
        recipe_steps.append(built)
        mentions.extend(built.ingredients)

    return ParseResult(
        steps=tuple(recipe_steps),
        ingredients=tuple(mentions),
        clarifications=tuple(clarifications),
        source=Source.rules,
        parser_mode=ParserMode.rules,
    )


def parse_rules_text(text: str, lexicon: Lexicon = LEXICON) -> ParseResult:
    """Convenience wrapper: normalise then parse a raw narration string."""
    return parse_rules(normalize(text), lexicon)


def _build_step(
    step: Segment,
    matches: list[Match],
    original: str,
    counters: dict[str, int],
    clarifications: list[Clarification],
) -> RecipeStep:
    numbers: list[_Number] = []
    pending: list[tuple[Quantity, int]] = []
    durations: list[Duration] = []
    ingredients: list[IngredientMention] = []

    index = 0
    while index < len(matches):
        match = matches[index]
        if match.category is Category.NUMBER:
            index = _consume_number(matches, index, numbers)
            continue
        if match.category is Category.MEASURE:
            number = _take_adjacent_number(numbers, match.token_start)
            quantity = _quantity_from_measure(number, match, original, counters, clarifications)
            pending.append((quantity, match.token_end))
        elif match.category is Category.DURATION:
            number = _take_adjacent_number(numbers, match.token_start)
            durations.append(_duration_from(number, match, original))
        elif match.category is Category.INGREDIENT:
            ingredients.append(_attach_ingredient(match, pending, numbers, original))
        index += 1

    return RecipeStep(
        idx=step.idx,
        text=step.original_text,
        orig_start=step.orig_start,
        orig_end=step.orig_end,
        ingredients=tuple(ingredients),
        durations=tuple(durations),
        connector=step.connector,
        conditional=step.conditional,
    )


def _consume_number(matches: list[Match], index: int, numbers: list[_Number]) -> int:
    """Push the number at ``index``; combine ``সাড়ে`` with a following number."""
    match = matches[index]
    if match.kind == "add_half":
        following = matches[index + 1] if index + 1 < len(matches) else None
        if (
            following is not None
            and following.category is Category.NUMBER
            and following.kind is None
            and match.token_end == following.token_start
        ):
            numbers.append(_combined_half(match, following))
            return index + 2
        return index + 1
    numbers.append(_number_from_match(match))
    return index + 1


def _number_from_match(match: Match) -> _Number:
    start, end = _span(match)
    return _Number(
        value=match.value,
        value_max=match.value_max,
        classifier=match.classifier,
        token_start=match.token_start,
        token_end=match.token_end,
        orig_start=start,
        orig_end=end,
    )


def _combined_half(first: Match, second: Match) -> _Number:
    start, _ = _span(first)
    _, end = _span(second)
    value = (second.value or 0.0) + 0.5
    value_max = None if second.value_max is None else second.value_max + 0.5
    return _Number(
        value=value,
        value_max=value_max,
        classifier=second.classifier,
        token_start=first.token_start,
        token_end=second.token_end,
        orig_start=start,
        orig_end=end,
    )


def _take_adjacent_number(numbers: list[_Number], start_token: int) -> _Number | None:
    """Pop the most recent number only if it sits immediately before ``start``."""
    if numbers and numbers[-1].token_end == start_token:
        return numbers.pop()
    return None


def _quantity_from_measure(
    number: _Number | None,
    measure: Match,
    original: str,
    counters: dict[str, int],
    clarifications: list[Clarification],
) -> Quantity:
    start, end = _span(measure)
    raw_start = number.orig_start if number is not None else start
    raw_phrase = original[raw_start:end]

    if measure.to_taste:
        kind = QuantityKind.TASTE
        qty = None
        qty_max = None
        unit = None
    elif measure.kind == "vague":
        kind = QuantityKind.VAGUE
        qty = number.value if number is not None else None
        qty_max = number.value_max if number is not None else None
        unit = None
    elif number is None:
        kind = QuantityKind.UNRESOLVED
        qty = None
        qty_max = None
        unit = measure.canonical
    else:
        kind = QuantityKind.RANGE if number.value_max is not None else QuantityKind.EXACT
        qty = number.value
        qty_max = number.value_max
        unit = measure.canonical

    confidence = _BASE_CONFIDENCE[kind]
    clarification_id = _clarify(measure, counters, clarifications)
    if clarification_id is not None:
        confidence = min(confidence, _AMBIGUOUS_CONFIDENCE)

    return Quantity(
        raw_phrase=raw_phrase,
        qty=qty,
        qty_max=qty_max,
        unit=unit,
        raw_unit=measure.surface,
        classifier=number.classifier if number is not None else None,
        to_taste=measure.to_taste,
        source=Source.rules,
        confidence=confidence,
        kind=kind,
        clarification_ids=(clarification_id,) if clarification_id is not None else (),
    )


def _count_quantity(number: _Number, original: str) -> Quantity:
    kind = QuantityKind.RANGE if number.value_max is not None else QuantityKind.EXACT
    return Quantity(
        raw_phrase=original[number.orig_start : number.orig_end],
        qty=number.value,
        qty_max=number.value_max,
        unit=None,
        raw_unit=None,
        classifier=number.classifier,
        to_taste=False,
        source=Source.rules,
        confidence=_COUNT_CONFIDENCE,
        kind=kind,
    )


def _duration_from(number: _Number | None, match: Match, original: str) -> Duration:
    start, end = _span(match)
    raw_start = number.orig_start if number is not None else start
    raw_phrase = original[raw_start:end]

    if match.kind == "vague":
        return Duration(
            raw_phrase=raw_phrase,
            kind=QuantityKind.VAGUE,
            orig_start=raw_start,
            orig_end=end,
        )
    if number is None:
        return Duration(
            raw_phrase=raw_phrase,
            unit=match.canonical,
            kind=QuantityKind.UNRESOLVED,
            orig_start=raw_start,
            orig_end=end,
        )
    kind = QuantityKind.RANGE if number.value_max is not None else QuantityKind.EXACT
    return Duration(
        raw_phrase=raw_phrase,
        value=number.value,
        value_max=number.value_max,
        unit=match.canonical,
        kind=kind,
        orig_start=raw_start,
        orig_end=end,
    )


def _attach_ingredient(
    match: Match,
    pending: list[tuple[Quantity, int]],
    numbers: list[_Number],
    original: str,
) -> IngredientMention:
    quantity: Quantity | None = None
    for position, (candidate, end_token) in enumerate(pending):
        if end_token == match.token_start:
            quantity = candidate
            del pending[position]
            break
    if quantity is None and numbers and numbers[-1].token_end == match.token_start:
        quantity = _count_quantity(numbers.pop(), original)

    start, end = _span(match)
    return IngredientMention(
        canonical=match.canonical,
        surface=match.surface,
        orig_start=start,
        orig_end=end,
        quantity=quantity,
        confidence=match.confidence,
        ambiguous=match.ambiguous,
        clarification_ids=quantity.clarification_ids if quantity is not None else (),
    )


def _clarify(
    measure: Match,
    counters: dict[str, int],
    clarifications: list[Clarification],
) -> str | None:
    kind = _CLARIFICATION_KINDS.get(measure.canonical)
    if kind is None or not measure.ambiguous:
        return None
    count = counters.get(kind, 0) + 1
    counters[kind] = count
    clarification_id = f"{kind}_{count}"
    question, options = _CLARIFICATION_SPECS[kind]
    clarifications.append(
        Clarification(
            id=clarification_id,
            kind=kind,
            question=question,
            options=list(options),
        )
    )
    return clarification_id


def _span(match: Match) -> tuple[int, int]:
    """Original-transcript span of a lexicon match (must be present)."""
    assert match.orig_start is not None and match.orig_end is not None
    return match.orig_start, match.orig_end
