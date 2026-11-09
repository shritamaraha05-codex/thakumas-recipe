"""Evaluation schema (M-11).

Two kinds of model live here:

* **expectations** - the manually curated ground truth for one :class:`EvaluationCase`
  (expected ingredients, quantities, durations, clarifications and negative
  expectations). Each expected fact must cite the exact original phrase that
  supports it (``evidence``); the loader checks that the phrase occurs verbatim
  in the transcript, so an annotation cannot be invented.
* **results** - the per-case :class:`EvaluationResult`, the aggregate
  :class:`MetricSummary` and the top-level :class:`EvaluationReport` written by
  the runner.

The schema is independent of ``backend.app.models`` (the public API contract).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

QuantityKind = Literal["exact", "range", "vague", "taste", "unresolved"]
Script = Literal["bengali", "roman", "mixed"]
NegativeKind = Literal[
    "ingredient",
    "ingredient_any",
    "quantity_unit",
    "quantity_for_ingredient",
    "clarification",
]

_NUMERIC_KINDS = ("exact", "range")


# --------------------------------------------------------------------------- #
# Expectations (ground truth)                                                 #
# --------------------------------------------------------------------------- #


class ExpectedQuantity(BaseModel):
    """The quantity a human expects for one ingredient, as spoken."""

    kind: QuantityKind
    qty: float | None = None
    qty_max: float | None = None
    unit: str | None = None
    to_taste: bool = False

    @model_validator(mode="after")
    def _check_consistency(self) -> ExpectedQuantity:
        if self.kind in ("vague", "taste") and (self.qty is not None or self.qty_max is not None):
            raise ValueError(f"a {self.kind} quantity must not carry a number")
        if self.kind == "taste" and not self.to_taste:
            raise ValueError("a taste quantity must set to_taste=True")
        if self.kind == "range":
            if self.qty is None or self.qty_max is None:
                raise ValueError("a range quantity needs both qty and qty_max")
            if self.qty_max < self.qty:
                raise ValueError("qty_max must be >= qty")
        return self


class ExpectedIngredient(BaseModel):
    """One ingredient that must appear, with optional expected quantity."""

    canonical: str = Field(min_length=1)
    surface: str | None = None
    quantity: ExpectedQuantity | None = None
    evidence: str = Field(min_length=1)


class ExpectedDuration(BaseModel):
    """One spoken cooking duration and its supporting phrase."""

    value: float | None = None
    value_max: float | None = None
    unit: str | None = None
    kind: QuantityKind = "exact"
    evidence: str = Field(min_length=1)


class ExpectedClarification(BaseModel):
    """An ambiguity that must be raised instead of silently resolved."""

    kind: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    evidence: str = Field(min_length=1)


class NegativeExpectation(BaseModel):
    """An interpretation that must not occur (e.g. মুইঠা as a handful)."""

    kind: NegativeKind
    value: str | None = None
    note: str = ""

    @model_validator(mode="after")
    def _check_value(self) -> NegativeExpectation:
        if self.kind in ("ingredient", "quantity_unit", "quantity_for_ingredient", "clarification"):
            if not self.value:
                raise ValueError(f"negative expectation '{self.kind}' needs a value")
        return self


class EvaluationCase(BaseModel):
    """One curated dataset record."""

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    script: Script
    tags: list[str] = Field(default_factory=list)
    expected_ingredients: list[ExpectedIngredient] = Field(default_factory=list)
    expected_durations: list[ExpectedDuration] = Field(default_factory=list)
    expected_clarifications: list[ExpectedClarification] = Field(default_factory=list)
    expected_step_count: int | None = None
    negatives: list[NegativeExpectation] = Field(default_factory=list)
    notes: str = ""


# --------------------------------------------------------------------------- #
# Results                                                                     #
# --------------------------------------------------------------------------- #


class EvaluationResult(BaseModel):
    """Per-case comparison of actual parser output with the expectations."""

    case_id: str
    script: str
    tags: list[str] = Field(default_factory=list)
    evaluated: bool = True
    error: str | None = None

    step_count_expected: int | None = None
    step_count_actual: int | None = None
    step_count_ok: bool | None = None

    ingredients_expected: list[str] = Field(default_factory=list)
    ingredients_actual: list[str] = Field(default_factory=list)
    ingredient_tp: int = 0
    ingredient_fp: int = 0
    ingredient_fn: int = 0
    missing_ingredients: list[str] = Field(default_factory=list)
    unexpected_ingredients: list[str] = Field(default_factory=list)

    quantities_expected: int = 0
    quantities_correct: int = 0
    quantities_associated: int = 0
    quantities_numeric_expected: int = 0
    quantities_numeric_correct: int = 0
    quantities_range_expected: int = 0
    quantities_range_correct: int = 0
    quantities_unit_correct: int = 0
    quantities_vague_expected: int = 0
    quantities_vague_correct: int = 0
    quantities_taste_expected: int = 0
    quantities_taste_correct: int = 0
    quantity_mismatches: list[str] = Field(default_factory=list)

    durations_expected: int = 0
    durations_found: int = 0
    durations_correct: int = 0
    durations_value_expected: int = 0
    durations_value_correct: int = 0
    durations_unit_expected: int = 0
    durations_unit_correct: int = 0
    duration_ingredient_misattachments: int = 0
    duration_mismatches: list[str] = Field(default_factory=list)

    clarifications_expected: int = 0
    clarifications_preserved: int = 0
    ambiguity_violations: list[str] = Field(default_factory=list)

    negative_checks: int = 0
    negative_violations: list[str] = Field(default_factory=list)

    evidence_grounding_checks: int = 0
    evidence_grounding_violations: list[str] = Field(default_factory=list)

    total_facts: int = 0
    unsupported_assertions: list[str] = Field(default_factory=list)


class MetricSummary(BaseModel):
    """Aggregate metrics over all evaluated cases."""

    ingredient_tp: int = 0
    ingredient_fp: int = 0
    ingredient_fn: int = 0
    ingredient_precision: float = 0.0
    ingredient_recall: float = 0.0
    ingredient_f1: float = 0.0

    quantities_expected: int = 0
    quantities_correct: int = 0
    quantity_accuracy: float = 0.0
    quantities_associated: int = 0
    quantity_association_accuracy: float = 0.0
    quantities_numeric_expected: int = 0
    quantities_numeric_correct: int = 0
    quantities_range_expected: int = 0
    quantities_range_correct: int = 0
    quantities_unit_correct: int = 0
    quantities_vague_expected: int = 0
    quantities_vague_correct: int = 0
    quantities_taste_expected: int = 0
    quantities_taste_correct: int = 0

    durations_expected: int = 0
    durations_found: int = 0
    durations_correct: int = 0
    durations_value_expected: int = 0
    durations_value_correct: int = 0
    durations_unit_expected: int = 0
    durations_unit_correct: int = 0
    duration_recall: float = 0.0
    duration_value_accuracy: float = 0.0
    duration_unit_accuracy: float = 0.0
    duration_ingredient_misattachments: int = 0

    clarifications_expected: int = 0
    clarifications_preserved: int = 0
    clarification_accuracy: float = 0.0
    ambiguity_violations: int = 0

    negative_checks: int = 0
    negative_violations: int = 0
    negative_preservation_accuracy: float = 0.0

    evidence_grounding_checks: int = 0
    evidence_grounding_violations: int = 0
    evidence_grounding_rate: float = 0.0

    total_facts: int = 0
    unsupported_assertions: int = 0
    unsupported_assertion_rate: float = 0.0


class EvaluationReport(BaseModel):
    """Machine-readable report written by the runner."""

    dataset_version: str
    evaluated_at: str
    parser: str
    provider: str | None = None
    model: str | None = None
    cases_total: int = 0
    cases_successful: int = 0
    cases_failed: int = 0
    cases_unevaluated: int = 0
    summary: MetricSummary
    per_case: list[EvaluationResult] = Field(default_factory=list)


__all__ = [
    "EvaluationCase",
    "EvaluationReport",
    "EvaluationResult",
    "ExpectedClarification",
    "ExpectedDuration",
    "ExpectedIngredient",
    "ExpectedQuantity",
    "MetricSummary",
    "NegativeExpectation",
]
