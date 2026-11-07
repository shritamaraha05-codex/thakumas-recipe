"""Internal deterministic parser schema (M-08).

These dataclasses are the *internal* output of the rules parser in
``parse/rules.py``. They are deliberately distinct from the public API models in
``backend/app/models.py``:

* the API model ``ParseResult`` is a wrapper ``{recipe, meta}`` shaped for the
  browser and the frozen ``docs/04_API.md`` contract;
* this internal ``ParseResult`` is the flat, provenance-rich result the rules
  stage produces, which M-09 evaluation and a later API integration can consume.

Where a type is already the right shape it is reused rather than duplicated:
``Clarification`` comes from ``models`` and ``source``/``parser_mode`` reuse the
``Source`` and ``ParserMode`` enums. The parser never invents a value: a
``Quantity`` may honestly have ``qty is None`` and a ``kind`` that says *why*
(vague, taste, or unresolved).

Deliberate scope limits (M-08)
    * no grams/millilitres, no unit conversion, no recipe scaling;
    * no yield, servings or total-food inference;
    * no cooking-time inference: a spoken duration is recorded in the unit the
      cook used (minute/hour/second) and is never converted to seconds here;
    * a quantity is only attached to an ingredient when the wording gives
      direct, adjacent evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.app.models import Clarification, ParserMode, Source


class QuantityKind(StrEnum):
    """Why a quantity has (or lacks) a number.

    EXACT      a stated single value (``দুই মুঠো``)
    RANGE      an explicitly stated range (``তিন-চার মুঠো``, ``৫-৬ মিনিট``)
    VAGUE      a vague expression with no number (``একটু``, ``পরিমাণমতো``)
    TASTE      a to-taste instruction (``স্বাদমতো``)
    UNRESOLVED a measurement was spoken but its number is missing (``মুঠো``)
    """

    EXACT = "exact"
    RANGE = "range"
    VAGUE = "vague"
    TASTE = "taste"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class Quantity:
    """What the cook said, with provenance and no invented precision.

    ``raw_phrase`` is always an exact substring of the original transcript.
    ``unit`` is the canonical recognised unit, or ``None`` when no unit (or no
    resolved unit) was spoken; ``raw_unit`` keeps the spoken unit wording.
    """

    raw_phrase: str
    qty: float | None = None
    qty_max: float | None = None
    unit: str | None = None
    raw_unit: str | None = None
    classifier: str | None = None
    to_taste: bool = False
    source: Source = Source.rules
    confidence: float = 1.0
    kind: QuantityKind = QuantityKind.EXACT
    clarification_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Duration:
    """A spoken cooking duration, kept in the unit the cook used.

    ``unit`` is ``minute``/``hour``/``second`` (or ``None`` for a vague phrase
    such as ``কিছুক্ষণ``). This stage never converts it to seconds.
    """

    raw_phrase: str
    value: float | None = None
    value_max: float | None = None
    unit: str | None = None
    kind: QuantityKind = QuantityKind.EXACT
    orig_start: int = 0
    orig_end: int = 0


@dataclass(frozen=True, slots=True)
class IngredientMention:
    """One spoken ingredient occurrence with its surface form and span.

    ``surface`` is her actual wording, never the canonical label. ``quantity``
    is attached only when the nearby wording gives direct evidence.
    """

    canonical: str
    surface: str
    orig_start: int
    orig_end: int
    quantity: Quantity | None = None
    confidence: float = 1.0
    ambiguous: bool = False
    clarification_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RecipeStep:
    """One ordered instruction from an M-06 ``Segment``.

    ``text`` is the original transcript wording (golden rule 5). ``connector``
    and ``conditional`` are the metadata M-06 already supplied.
    """

    idx: int
    text: str
    orig_start: int
    orig_end: int
    ingredients: tuple[IngredientMention, ...] = ()
    durations: tuple[Duration, ...] = ()
    connector: str | None = None
    conditional: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ParseResult:
    """The parser result: ordered steps, all mentions, clarifications.

    ``ingredients`` flattens the per-step mentions in order, so a caller can
    inspect every mention without walking the steps.

    ``source``/``parser_mode`` record which stage produced the result and
    ``llm_provider`` names the provider when an LLM produced the relationships
    (``None`` for the deterministic rules parser). The field is additive and
    defaults to ``None``, so the M-08 rules output is unchanged.
    """

    steps: tuple[RecipeStep, ...] = ()
    ingredients: tuple[IngredientMention, ...] = ()
    clarifications: tuple[Clarification, ...] = ()
    source: Source = Source.rules
    parser_mode: ParserMode = ParserMode.rules
    llm_provider: str | None = None
