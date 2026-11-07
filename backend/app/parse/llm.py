"""LLM-driven extraction over the deterministic pipeline (M-10).

The LLM chooses *relationships* between already-recognised lexicon matches; it
never supplies wording, numbers or offsets. This module:

1. builds request-local evidence ids from the M-07 lexicon matches, grouped by
   the M-06 segments (the backend supplies the evidence);
2. asks the provider for a structured selection of those ids;
3. validates every id (existence, category, same-segment, no duplicates); and
4. constructs the existing internal :class:`~backend.app.parse.schema.ParseResult`
   using the *deterministic* rules builders, so all canonical labels, values,
   surface forms and source spans come from verified M-07 evidence.

If a selection cannot be validated safely this raises
:class:`~backend.app.providers.ProviderInvalidOutput`; the API turns that into a
controlled error instead of a successful-looking invented recipe.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from backend.app.models import Clarification, ParserMode, Source
from backend.app.parse import rules as rules_engine
from backend.app.parse.lexicon import LEXICON, Category, Lexicon, Match
from backend.app.parse.llm_schema import LLMSelection
from backend.app.parse.normalize import NormalizedText
from backend.app.parse.schema import (
    Duration,
    IngredientMention,
    ParseResult,
    Quantity,
    RecipeStep,
)
from backend.app.parse.segment import Segment, segment
from backend.app.providers import ProviderInvalidOutput, StructuredLLMProvider

__all__ = ["build_evidence", "build_prompt", "parse_llm", "SYSTEM_INSTRUCTION"]

SYSTEM_INSTRUCTION = """\
You extract structured ingredient and cooking-time evidence from Bengali or Roman
Bengali family recipe narration. You only select evidence ids that are given to
you; you never write your own words, numbers, labels or character offsets.

Original wording
- Preserve Bengali wording. Do not translate the narration into English.
- Do not rewrite, summarise or correct cooking instructions or spelling.
- Do not replace traditional expressions with modern measurements.

Quantities
- Preserve exact quantities and explicitly stated ranges exactly as spoken.
- Preserve vague quantities such as সামান্য, অল্প অল্প and পরিমাণমতো as vague.
- Preserve স্বাদমতো as a taste-based quantity, never as a number.
- Never invent grams, millilitres or any conversion.
- Never infer servings, yield or total cooked quantity.
- Do not attach a quantity to an ingredient unless the evidence clearly supports it.

Bengali terminology
- মুঠো / মুঠি may be traditional handful measures.
- মুইঠা (as in চিতল মাছের মুইঠা) is a fish preparation; never treat it as a handful.
- Never invent ingredients from cooking actions or preparation descriptions.
- Distinguish an ingredient from an instruction describing how it is prepared.

Ambiguity
- Do not resolve a plain চামচ into teaspoon or tablespoon.
- Do not assume a standard measuring cup for an uncalibrated কাপ.
- Keep the existing ambiguity; do not override it because one reading seems commoner.

Selection
- For each segment choose the ingredient evidence ids and the number/measure
  evidence ids that form their quantities.
- Put duration evidence ids in duration_match_ids, never in a quantity.
- Use each evidence id at most once per segment.
- Never use an evidence id that belongs to another segment.
- An ingredient may have no quantity; any array may be empty.

Return only JSON matching the required schema.
"""


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One selectable lexical match with its request-local id."""

    id: str
    segment_index: int
    match: Match


@dataclass(frozen=True, slots=True)
class Evidence:
    """All selectable matches for one request, keyed by id and by segment."""

    items: dict[str, EvidenceItem]
    by_segment: dict[int, tuple[EvidenceItem, ...]]


@dataclass(frozen=True, slots=True)
class _SelectedIngredient:
    match: Match
    quantities: tuple[Match, ...]


@dataclass(frozen=True, slots=True)
class _SelectedSegment:
    ingredients: tuple[_SelectedIngredient, ...]
    durations: tuple[Match, ...]


def build_evidence(
    normalized: NormalizedText, lexicon: Lexicon = LEXICON
) -> tuple[tuple[Segment, ...], Evidence]:
    """Group M-07 matches into M-06 segments and assign ``s{i}m{j}`` ids."""
    segments = segment(normalized)
    buckets: dict[int, list[EvidenceItem]] = {index: [] for index in range(len(segments))}
    items: dict[str, EvidenceItem] = {}
    for match in lexicon.find_in(normalized):
        segment_index = _segment_index(segments, match)
        if segment_index is None:
            continue
        item_id = f"s{segment_index}m{len(buckets[segment_index])}"
        item = EvidenceItem(id=item_id, segment_index=segment_index, match=match)
        buckets[segment_index].append(item)
        items[item_id] = item
    by_segment = {index: tuple(bucket) for index, bucket in buckets.items()}
    return segments, Evidence(items=items, by_segment=by_segment)


def build_prompt(
    normalized: NormalizedText,
    segments: tuple[Segment, ...],
    evidence: Evidence,
) -> str:
    """Render the untouched narration, segments and evidence for the model."""
    lines = [
        "Original narration (verbatim; never translate or correct it):",
        normalized.original,
        "",
        "Segments (0-based index; original wording):",
    ]
    for index, segment_item in enumerate(segments):
        lines.append(f"[{index}] {segment_item.original_text}")

    lines.append("")
    lines.append("Lexical evidence (verified; select these ids only):")
    for index in range(len(segments)):
        items = evidence.by_segment.get(index, ())
        lines.append(f"Segment {index}:")
        if not items:
            lines.append("  (no lexical matches)")
        for item in items:
            lines.append(f"  {item.id}: {_describe(item.match)}")
    lines.append("")
    lines.append("Return the JSON selection.")
    return "\n".join(lines)


async def parse_llm(
    normalized: NormalizedText,
    provider: StructuredLLMProvider,
    lexicon: Lexicon = LEXICON,
) -> ParseResult:
    """Run the LLM provider and build a validated internal :class:`ParseResult`."""
    segments, evidence = build_evidence(normalized, lexicon)
    selection = await provider.generate(
        system_instruction=SYSTEM_INSTRUCTION,
        prompt=build_prompt(normalized, segments, evidence),
        response_schema=LLMSelection,
    )
    if not isinstance(selection, LLMSelection):
        raise ProviderInvalidOutput("The provider returned an unexpected schema.")
    return _construct(normalized, segments, evidence, selection, provider.name)


def _construct(
    normalized: NormalizedText,
    segments: tuple[Segment, ...],
    evidence: Evidence,
    selection: LLMSelection,
    provider_name: str,
) -> ParseResult:
    """Validate the selection and build the internal result deterministically."""
    validated = _validate(selection, segments, evidence)
    original = normalized.original
    counters: dict[str, int] = {}
    clarifications: list[Clarification] = []
    steps: list[RecipeStep] = []
    mentions: list[IngredientMention] = []

    for index, segment_item in enumerate(segments):
        selected = validated.get(index)
        ingredients: list[IngredientMention] = []
        durations: list[Duration] = []
        if selected is not None:
            for ingredient in selected.ingredients:
                ingredients.append(_build_mention(ingredient, original, counters, clarifications))
            durations = _build_durations(selected.durations, original)
        steps.append(
            RecipeStep(
                idx=segment_item.idx,
                text=segment_item.original_text,
                orig_start=segment_item.orig_start,
                orig_end=segment_item.orig_end,
                ingredients=tuple(ingredients),
                durations=tuple(durations),
                connector=segment_item.connector,
                conditional=segment_item.conditional,
            )
        )
        mentions.extend(ingredients)

    return ParseResult(
        steps=tuple(steps),
        ingredients=tuple(mentions),
        clarifications=tuple(clarifications),
        source=Source.llm,
        parser_mode=ParserMode.llm,
        llm_provider=provider_name,
    )


def _validate(
    selection: LLMSelection,
    segments: tuple[Segment, ...],
    evidence: Evidence,
) -> dict[int, _SelectedSegment]:
    """Check every id and return per-segment matches; raise on anything unsafe."""
    validated: dict[int, _SelectedSegment] = {}
    for segment_selection in selection.segments:
        index = segment_selection.segment_index
        if not 0 <= index < len(segments):
            raise ProviderInvalidOutput(f"Unknown segment index {index}.")
        if index in validated:
            raise ProviderInvalidOutput(f"Segment {index} was selected twice.")

        used: set[str] = set()
        ingredients: list[_SelectedIngredient] = []
        for ingredient in segment_selection.ingredients:
            item = _require(evidence, ingredient.ingredient_match_id, index, {Category.INGREDIENT})
            _claim(used, item.id)
            quantities: list[Match] = []
            for quantity_id in ingredient.quantity_match_ids:
                quantity_item = _require(
                    evidence,
                    quantity_id,
                    index,
                    {Category.NUMBER, Category.MEASURE},
                )
                _claim(used, quantity_item.id)
                quantities.append(quantity_item.match)
            ingredients.append(_SelectedIngredient(match=item.match, quantities=tuple(quantities)))

        durations: list[Match] = []
        for duration_id in segment_selection.duration_match_ids:
            duration_item = _require(
                evidence,
                duration_id,
                index,
                {Category.DURATION, Category.NUMBER},
            )
            _claim(used, duration_item.id)
            durations.append(duration_item.match)

        validated[index] = _SelectedSegment(
            ingredients=tuple(ingredients),
            durations=tuple(durations),
        )
    return validated


def _require(
    evidence: Evidence,
    item_id: str,
    segment_index: int,
    allowed: set[Category],
) -> EvidenceItem:
    item = evidence.items.get(item_id)
    if item is None:
        raise ProviderInvalidOutput(f"Unknown evidence id {item_id!r}.")
    if item.segment_index != segment_index:
        raise ProviderInvalidOutput(f"Evidence id {item_id!r} belongs to another segment.")
    if item.match.category not in allowed:
        raise ProviderInvalidOutput(f"Evidence id {item_id!r} has the wrong category.")
    return item


def _claim(used: set[str], item_id: str) -> None:
    if item_id in used:
        raise ProviderInvalidOutput(f"Evidence id {item_id!r} was used more than once.")
    used.add(item_id)


def _build_mention(
    ingredient: _SelectedIngredient,
    original: str,
    counters: dict[str, int],
    clarifications: list[Clarification],
) -> IngredientMention:
    match = ingredient.match
    quantity = _build_quantity(ingredient.quantities, original, counters, clarifications)
    start = _offset(match.orig_start)
    end = _offset(match.orig_end)
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


def _build_quantity(
    matches: tuple[Match, ...],
    original: str,
    counters: dict[str, int],
    clarifications: list[Clarification],
) -> Quantity | None:
    if not matches:
        return None
    measures = [match for match in matches if match.category is Category.MEASURE]
    numbers = sorted(
        (match for match in matches if match.category is Category.NUMBER),
        key=lambda match: match.token_start,
    )
    if len(measures) > 1:
        raise ProviderInvalidOutput("A quantity may reference at most one measure match.")
    number = _combine_numbers(numbers)
    if measures:
        quantity = rules_engine._quantity_from_measure(
            number, measures[0], original, counters, clarifications
        )
    elif number is not None:
        quantity = rules_engine._count_quantity(number, original)
    else:
        return None
    return replace(quantity, source=Source.llm)


def _combine_numbers(numbers: list[Match]) -> rules_engine._Number | None:
    if not numbers:
        return None
    if len(numbers) > 2:
        raise ProviderInvalidOutput("Too many number matches for one quantity.")
    if len(numbers) == 2:
        first, second = numbers
        adjacent = first.token_end == second.token_start
        if first.kind == "add_half" and second.kind is None and adjacent:
            return rules_engine._combined_half(first, second)
        raise ProviderInvalidOutput("The selected number matches cannot be combined safely.")
    only = numbers[0]
    if only.kind == "add_half":
        raise ProviderInvalidOutput("A half modifier needs a following number match.")
    return rules_engine._number_from_match(only)


def _build_durations(matches: tuple[Match, ...], original: str) -> list[Duration]:
    ordered = sorted(matches, key=lambda match: match.token_start)
    durations: list[Duration] = []
    pending_number: Match | None = None
    for match in ordered:
        if match.category is Category.NUMBER:
            if pending_number is not None:
                raise ProviderInvalidOutput("A duration number has no adjacent duration match.")
            pending_number = match
            continue
        number: rules_engine._Number | None = None
        if pending_number is not None:
            if pending_number.token_end != match.token_start:
                raise ProviderInvalidOutput("A duration number is not adjacent to its duration.")
            number = rules_engine._number_from_match(pending_number)
            pending_number = None
        durations.append(rules_engine._duration_from(number, match, original))
    if pending_number is not None:
        raise ProviderInvalidOutput("A duration number has no matching duration.")
    return durations


def _segment_index(segments: tuple[Segment, ...], match: Match) -> int | None:
    start = match.orig_start
    end = match.orig_end
    if start is None or end is None:
        return None
    for index, segment_item in enumerate(segments):
        if segment_item.orig_start <= start and end <= segment_item.orig_end:
            return index
    return None


def _describe(match: Match) -> str:
    parts = [f"surface={match.surface!r}", f"canonical={match.canonical!r}"]
    parts.append(f"category={match.category.value}")
    if match.kind is not None:
        parts.append(f"kind={match.kind}")
    if match.value is not None:
        parts.append(f"value={match.value:g}")
    if match.value_max is not None:
        parts.append(f"value_max={match.value_max:g}")
    if match.to_taste:
        parts.append("to_taste=true")
    if match.ambiguous:
        options = ",".join(match.options)
        parts.append(f"ambiguous=true options=[{options}]")
    return " ".join(parts)


def _offset(value: int | None) -> int:
    if value is None:  # pragma: no cover - evidence always carries original spans
        raise ProviderInvalidOutput("A selected match is missing its source span.")
    return value
