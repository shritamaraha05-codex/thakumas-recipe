"""Serialization from the internal parser result to the public API models (M-09).

This adapter is the *only* place that knows how ``parse.schema`` maps onto the
Pydantic models served by ``POST /api/parse``. Keeping it separate means the
internal dataclasses never leak into the public contract by accident, and the
API shape can be reviewed on its own. It converts both the deterministic rules
result and the LLM result (M-10): ``meta`` is taken from the internal
``source``/``parser_mode``/``llm_provider`` fields rather than hard-coded, so
metadata is always truthful about which stage produced the recipe.

It is deliberately lossless for what the rules stage produces:

* every ``IngredientMention`` becomes one ``Quantity`` (so ingredient mentions
  without a number are still visible, with ``qty=None``);
* ``kind`` carries the exact/range/vague/taste/unresolved distinction;
* ``Duration`` objects stay in the cook's own unit (never seconds);
* clarification ids and questions are attached as the ``clarification`` object;
* ``raw_phrase`` and ``orig_start``/``orig_end`` are exact slices of the original
  transcript, located from the internal spans — nothing is rebuilt from labels.

``range`` (the grams/millilitres interval) is always ``None`` here: unit
conversion is a later task and the rules parser must not fabricate it.
"""

from __future__ import annotations

from backend.app.models import (
    Clarification,
    CookingStep,
    Duration,
    Metadata,
    ParseResult as ApiParseResult,
    Quantity,
    Recipe,
    Source,
)
from backend.app.parse import schema
from backend.app.parse.lexicon import LEXICON, Category

DEFAULT_TITLE = "Untitled recipe"

_INGREDIENT_CLASS: dict[str, str | None] = {
    # M-07's Entry places the class in ``kind`` for ingredient rows (the
    # ``ingredient_class`` field is always None there); read both so the public
    # ``ingredient_class`` is populated without modifying the frozen module.
    entry.canonical: entry.ingredient_class or entry.kind
    for entry in LEXICON.entries
    if entry.category is Category.INGREDIENT
}


def to_api_result(
    result: schema.ParseResult,
    *,
    original: str,
    title: str = DEFAULT_TITLE,
) -> ApiParseResult:
    """Convert an internal rules result into the public ``ParseResult``."""
    clarifications = {clarification.id: clarification for clarification in result.clarifications}

    steps: list[CookingStep] = []
    quantity_index = 0
    for step in result.steps:
        quantities: list[Quantity] = []
        for mention in step.ingredients:
            quantity_index += 1
            quantities.append(
                _api_quantity(mention, f"q{quantity_index}", original, clarifications)
            )
        steps.append(
            CookingStep(
                idx=step.idx,
                text=step.text,
                orig_start=step.orig_start,
                orig_end=step.orig_end,
                timer_seconds=None,
                durations=[_api_duration(duration) for duration in step.durations],
                quantities=quantities,
            )
        )

    return ApiParseResult(
        recipe=Recipe(title=title, language=None, base_servings=None, steps=steps),
        meta=Metadata(
            parser_mode=result.parser_mode,
            llm_provider=result.llm_provider,
            replayed=False,
            mock=False,
            mock_source=None,
        ),
    )


def _api_quantity(
    mention: schema.IngredientMention,
    quantity_id: str,
    original: str,
    clarifications: dict[str, Clarification],
) -> Quantity:
    quantity = mention.quantity
    start = _item_start(mention, original)
    clarification = None
    if quantity is not None and quantity.clarification_ids:
        clarification = clarifications.get(quantity.clarification_ids[0])
    return Quantity(
        id=quantity_id,
        ingredient=mention.canonical,
        ingredient_class=_INGREDIENT_CLASS.get(mention.canonical),
        qty=quantity.qty if quantity is not None else None,
        qty_max=quantity.qty_max if quantity is not None else None,
        unit=quantity.unit if quantity is not None else None,
        raw_unit=quantity.raw_unit if quantity is not None else None,
        classifier=quantity.classifier if quantity is not None else None,
        kind=quantity.kind.value if quantity is not None else None,
        to_taste=quantity.to_taste if quantity is not None else False,
        raw_phrase=original[start : mention.orig_end],
        confidence=mention.confidence,
        source=quantity.source if quantity is not None else Source.rules,
        orig_start=start,
        orig_end=mention.orig_end,
        range=None,
        clarification=clarification,
    )


def _item_start(mention: schema.IngredientMention, original: str) -> int:
    """Start of the item wording (quantity + ingredient) in the transcript.

    The rules stage only attaches a quantity when it is immediately adjacent to
    the ingredient, so the quantity's exact ``raw_phrase`` ends the text just
    before the ingredient (whitespace aside).
    """
    if mention.quantity is None:
        return mention.orig_start
    prefix = original[: mention.orig_start].rstrip()
    raw = mention.quantity.raw_phrase
    if prefix.endswith(raw):
        return len(prefix) - len(raw)
    return mention.orig_start


def _api_duration(duration: schema.Duration) -> Duration:
    return Duration(
        raw_phrase=duration.raw_phrase,
        value=duration.value,
        value_max=duration.value_max,
        unit=duration.unit,
        kind=duration.kind.value,
        orig_start=duration.orig_start,
        orig_end=duration.orig_end,
    )
