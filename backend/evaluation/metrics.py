"""Metrics for the M-11 evaluation harness.

The evaluator compares a parser's internal ``parse.schema.ParseResult`` with the
manually curated expectations of one :class:`~backend.evaluation.schema.EvaluationCase`.

Matching rules (fixed and documented here so results are reproducible):

Ingredient recognition
    Per case, compare the *set* of canonical ingredients. ``tp = |expected ∩ actual|``,
    ``fp = |actual \\ expected|``, ``fn = |expected \\ actual|``. Duplicate mentions of the
    same canonical are not double-counted (documented limitation).

Quantity (scored separately from ingredient recognition)
    Only expected ingredients that carry an ``ExpectedQuantity`` are scored.
    ``associated`` means the ingredient got *some* quantity; ``correct`` means a
    mention of that canonical has a quantity equal in kind, value (``qty``/
    ``qty_max`` within ``1e-6``) and unit. Vague/taste/range are also counted on
    their own so a numeric-only view cannot hide a preserved vague quantity.

Duration
    Expected durations are matched to actual ones by value, ``value_max`` and unit.
    ``duration_ingredient_misattachments`` counts actual ingredient quantities whose
    unit is a time unit (should always be zero: durations are never ingredient
    quantities).

Ambiguity / negatives
    ``clarifications_preserved`` counts expected clarifications actually raised.
    Each negative expectation is checked; a failure is reported, never hidden.

Evidence grounding / hallucination
    Every actual ingredient surface and quantity/duration ``raw_phrase`` must be an
    exact substring of the transcript and every span must be valid. Failures are
    counted as *unsupported assertions* separately from precision/recall.
"""

from __future__ import annotations

from backend.app.parse import schema

from .schema import (
    EvaluationCase,
    EvaluationResult,
    ExpectedDuration,
    ExpectedIngredient,
    ExpectedQuantity,
    MetricSummary,
    NegativeExpectation,
)

_TOL = 1e-6
_NUMERIC_KINDS = ("exact", "range")
_DURATION_UNITS = frozenset({"minute", "hour", "second"})


def _approx(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return left is right
    return abs(left - right) < _TOL


# --------------------------------------------------------------------------- #
# Matching helpers                                                            #
# --------------------------------------------------------------------------- #


def _quantity_matches(actual: schema.Quantity | None, expected: ExpectedQuantity) -> bool:
    """Full match: same kind, values and unit."""
    if actual is None:
        return False
    if expected.kind == "vague":
        return actual.kind is schema.QuantityKind.VAGUE and actual.qty is None
    if expected.kind == "taste":
        return actual.to_taste and actual.kind is schema.QuantityKind.TASTE
    if expected.kind == "unresolved":
        return actual.kind is schema.QuantityKind.UNRESOLVED and actual.qty is None
    if actual.qty is None or not _approx(actual.qty, expected.qty):
        return False
    if expected.kind == "range":
        if actual.qty_max is None or not _approx(actual.qty_max, expected.qty_max):
            return False
    elif actual.qty_max is not None:
        return False
    return actual.unit == expected.unit


def _numeric_matches(actual: schema.Quantity | None, expected: ExpectedQuantity) -> bool:
    return actual is not None and _approx(actual.qty, expected.qty)


def _range_matches(actual: schema.Quantity | None, expected: ExpectedQuantity) -> bool:
    return (
        actual is not None
        and _approx(actual.qty, expected.qty)
        and _approx(actual.qty_max, expected.qty_max)
    )


def _unit_matches(actual: schema.Quantity | None, expected: ExpectedQuantity) -> bool:
    return actual is not None and actual.unit == expected.unit


def _duration_value_matches(actual: schema.Duration, expected: ExpectedDuration) -> bool:
    return _approx(actual.value, expected.value) and _approx(actual.value_max, expected.value_max)


def _duration_unit_matches(actual: schema.Duration, expected: ExpectedDuration) -> bool:
    return actual.unit == expected.unit


# --------------------------------------------------------------------------- #
# Description helpers (for the per-case failure report)                       #
# --------------------------------------------------------------------------- #


def _describe_quantity(quantity: schema.Quantity | None) -> str:
    if quantity is None:
        return "no-quantity"
    return (
        f"kind={quantity.kind.value} qty={quantity.qty} "
        f"qty_max={quantity.qty_max} unit={quantity.unit}"
    )


def _quantity_expectation(
    expected: ExpectedIngredient, mentions: list[schema.IngredientMention]
) -> str:
    observed = "; ".join(_describe_quantity(m.quantity) for m in mentions) or "no mention"
    wanted = expected.quantity
    assert wanted is not None
    return (
        f"{expected.canonical}: expected kind={wanted.kind} qty={wanted.qty} "
        f"qty_max={wanted.qty_max} unit={wanted.unit}; observed {observed}"
    )


# --------------------------------------------------------------------------- #
# Case evaluation                                                             #
# --------------------------------------------------------------------------- #


def _check_negative(
    negative: NegativeExpectation,
    mentions: list[schema.IngredientMention],
    result: schema.ParseResult,
) -> str | None:
    """Return a violation description, or ``None`` when the negative holds."""
    value = negative.value
    if negative.kind == "ingredient":
        if any(mention.canonical == value for mention in mentions):
            return f"forbidden ingredient {value!r} was extracted"
    elif negative.kind == "ingredient_any":
        if mentions:
            found = sorted({mention.canonical for mention in mentions})
            return f"no ingredient expected but extracted {found}"
    elif negative.kind == "quantity_unit":
        if any(m.quantity is not None and m.quantity.unit == value for m in mentions):
            return f"forbidden unit {value!r} was attached to a quantity"
    elif negative.kind == "quantity_for_ingredient":
        if any(
            m.canonical == value and m.quantity is not None and m.quantity.qty is not None
            for m in mentions
        ):
            return f"ingredient {value!r} was given a numeric quantity"
    elif negative.kind == "clarification":
        if any(c.kind == value for c in result.clarifications):
            return f"forbidden clarification {value!r} was raised"
    return None


def _valid_span(original: str, start: int | None, end: int | None) -> bool:
    if start is None or end is None:
        return False
    return 0 <= start < end <= len(original)


def evaluate_case(case: EvaluationCase, result: schema.ParseResult) -> EvaluationResult:
    """Compare one parser result against one curated case."""
    original = case.text
    mentions = list(result.ingredients)
    durations = [duration for step in result.steps for duration in step.durations]

    actual_set = {mention.canonical for mention in mentions}
    expected_set = {ingredient.canonical for ingredient in case.expected_ingredients}

    evaluation = EvaluationResult(
        case_id=case.id,
        script=case.script,
        tags=list(case.tags),
        step_count_expected=case.expected_step_count,
        step_count_actual=len(result.steps),
        ingredients_expected=sorted(expected_set),
        ingredients_actual=sorted(actual_set),
        ingredient_tp=len(expected_set & actual_set),
        ingredient_fp=len(actual_set - expected_set),
        ingredient_fn=len(expected_set - actual_set),
        missing_ingredients=sorted(expected_set - actual_set),
        unexpected_ingredients=sorted(actual_set - expected_set),
        durations_expected=len(case.expected_durations),
        durations_found=len(durations),
    )
    if case.expected_step_count is not None:
        evaluation.step_count_ok = len(result.steps) == case.expected_step_count

    _score_quantities(case, mentions, evaluation)
    _score_durations(case, durations, evaluation)

    evaluation.duration_ingredient_misattachments = sum(
        1 for m in mentions if m.quantity is not None and m.quantity.unit in _DURATION_UNITS
    )

    actual_clarification_kinds = {clarification.kind for clarification in result.clarifications}
    evaluation.clarifications_expected = len(case.expected_clarifications)
    for clarification in case.expected_clarifications:
        if clarification.kind in actual_clarification_kinds:
            evaluation.clarifications_preserved += 1
        else:
            evaluation.ambiguity_violations.append(
                f"missing clarification {clarification.kind!r} (expected from {clarification.evidence!r})"
            )

    evaluation.negative_checks = len(case.negatives)
    for negative in case.negatives:
        violation = _check_negative(negative, mentions, result)
        if violation is not None:
            evaluation.negative_violations.append(violation)
            if negative.kind == "clarification":
                evaluation.ambiguity_violations.append(violation)

    _score_grounding(original, mentions, durations, evaluation)
    return evaluation


def _score_quantities(
    case: EvaluationCase,
    mentions: list[schema.IngredientMention],
    evaluation: EvaluationResult,
) -> None:
    for ingredient in case.expected_ingredients:
        expected = ingredient.quantity
        if expected is None:
            continue
        evaluation.quantities_expected += 1
        candidates = [m for m in mentions if m.canonical == ingredient.canonical]

        if any(m.quantity is not None for m in candidates):
            evaluation.quantities_associated += 1
        if any(_quantity_matches(m.quantity, expected) for m in candidates):
            evaluation.quantities_correct += 1
        else:
            evaluation.quantity_mismatches.append(_quantity_expectation(ingredient, candidates))

        if expected.kind in _NUMERIC_KINDS:
            evaluation.quantities_numeric_expected += 1
            if any(_numeric_matches(m.quantity, expected) for m in candidates):
                evaluation.quantities_numeric_correct += 1
        if expected.kind == "range":
            evaluation.quantities_range_expected += 1
            if any(_range_matches(m.quantity, expected) for m in candidates):
                evaluation.quantities_range_correct += 1
        if any(_unit_matches(m.quantity, expected) for m in candidates):
            evaluation.quantities_unit_correct += 1
        if expected.kind == "vague":
            evaluation.quantities_vague_expected += 1
            if any(
                m.quantity is not None
                and m.quantity.kind is schema.QuantityKind.VAGUE
                and m.quantity.qty is None
                for m in candidates
            ):
                evaluation.quantities_vague_correct += 1
        if expected.kind == "taste":
            evaluation.quantities_taste_expected += 1
            if any(m.quantity is not None and m.quantity.to_taste for m in candidates):
                evaluation.quantities_taste_correct += 1


def _score_durations(
    case: EvaluationCase,
    durations: list[schema.Duration],
    evaluation: EvaluationResult,
) -> None:
    for expected in case.expected_durations:
        if expected.value is not None or expected.value_max is not None:
            evaluation.durations_value_expected += 1
        if expected.unit is not None:
            evaluation.durations_unit_expected += 1

        value_ok = any(_duration_value_matches(d, expected) for d in durations)
        unit_ok = any(_duration_unit_matches(d, expected) for d in durations)
        if value_ok:
            evaluation.durations_value_correct += 1
        if unit_ok:
            evaluation.durations_unit_correct += 1
        if value_ok and unit_ok:
            evaluation.durations_correct += 1
        else:
            observed = "; ".join(f"{d.value}/{d.value_max} {d.unit}" for d in durations) or "none"
            evaluation.duration_mismatches.append(
                f"expected {expected.value}/{expected.value_max} {expected.unit} "
                f"from {expected.evidence!r}; observed {observed}"
            )


def _score_grounding(
    original: str,
    mentions: list[schema.IngredientMention],
    durations: list[schema.Duration],
    evaluation: EvaluationResult,
) -> None:
    unsupported: list[str] = []

    for mention in mentions:
        evaluation.evidence_grounding_checks += 1
        if mention.surface not in original:
            message = f"ingredient surface {mention.surface!r} is not in the transcript"
            evaluation.evidence_grounding_violations.append(message)
            unsupported.append(message)
        elif original[mention.orig_start : mention.orig_end] != mention.surface:
            message = f"ingredient span does not slice {mention.surface!r}"
            evaluation.evidence_grounding_violations.append(message)
            unsupported.append(message)

        quantity = mention.quantity
        if quantity is not None:
            evaluation.evidence_grounding_checks += 1
            if quantity.raw_phrase not in original:
                message = f"quantity raw_phrase {quantity.raw_phrase!r} is not in the transcript"
                evaluation.evidence_grounding_violations.append(message)
                unsupported.append(message)

    for duration in durations:
        evaluation.evidence_grounding_checks += 1
        if duration.raw_phrase not in original:
            message = f"duration raw_phrase {duration.raw_phrase!r} is not in the transcript"
            evaluation.evidence_grounding_violations.append(message)
            unsupported.append(message)
        if not _valid_span(original, duration.orig_start, duration.orig_end):
            message = f"duration span ({duration.orig_start}, {duration.orig_end}) is invalid"
            evaluation.evidence_grounding_violations.append(message)
            unsupported.append(message)

    evaluation.total_facts = len(mentions) + len(durations)
    evaluation.unsupported_assertions = list(dict.fromkeys(unsupported))


# --------------------------------------------------------------------------- #
# Aggregation                                                                 #
# --------------------------------------------------------------------------- #


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def summarize(results: list[EvaluationResult]) -> MetricSummary:
    """Aggregate per-case results into a metric summary (micro-averaged)."""

    def total(field: str) -> int:
        return sum(getattr(result, field) for result in results)

    tp = total("ingredient_tp")
    fp = total("ingredient_fp")
    fn = total("ingredient_fn")
    precision = _rate(tp, tp + fp)
    recall = _rate(tp, tp + fn)
    f1 = round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0

    q_expected = total("quantities_expected")
    q_correct = total("quantities_correct")
    q_associated = total("quantities_associated")

    d_expected = total("durations_expected")
    d_correct = total("durations_correct")
    d_value_expected = total("durations_value_expected")
    d_value_correct = total("durations_value_correct")
    d_unit_expected = total("durations_unit_expected")
    d_unit_correct = total("durations_unit_correct")

    neg_checks = total("negative_checks")
    neg_violations = sum(len(result.negative_violations) for result in results)

    grounding_checks = total("evidence_grounding_checks")
    grounding_violations = sum(len(result.evidence_grounding_violations) for result in results)

    total_facts = total("total_facts")
    unsupported = sum(len(result.unsupported_assertions) for result in results)

    return MetricSummary(
        ingredient_tp=tp,
        ingredient_fp=fp,
        ingredient_fn=fn,
        ingredient_precision=precision,
        ingredient_recall=recall,
        ingredient_f1=f1,
        quantities_expected=q_expected,
        quantities_correct=q_correct,
        quantity_accuracy=_rate(q_correct, q_expected),
        quantities_associated=q_associated,
        quantity_association_accuracy=_rate(q_associated, q_expected),
        quantities_numeric_expected=total("quantities_numeric_expected"),
        quantities_numeric_correct=total("quantities_numeric_correct"),
        quantities_range_expected=total("quantities_range_expected"),
        quantities_range_correct=total("quantities_range_correct"),
        quantities_unit_correct=total("quantities_unit_correct"),
        quantities_vague_expected=total("quantities_vague_expected"),
        quantities_vague_correct=total("quantities_vague_correct"),
        quantities_taste_expected=total("quantities_taste_expected"),
        quantities_taste_correct=total("quantities_taste_correct"),
        durations_expected=d_expected,
        durations_found=total("durations_found"),
        durations_correct=d_correct,
        durations_value_expected=d_value_expected,
        durations_value_correct=d_value_correct,
        durations_unit_expected=d_unit_expected,
        durations_unit_correct=d_unit_correct,
        duration_recall=_rate(d_correct, d_expected),
        duration_value_accuracy=_rate(d_value_correct, d_value_expected),
        duration_unit_accuracy=_rate(d_unit_correct, d_unit_expected),
        duration_ingredient_misattachments=total("duration_ingredient_misattachments"),
        clarifications_expected=total("clarifications_expected"),
        clarifications_preserved=total("clarifications_preserved"),
        clarification_accuracy=_rate(
            total("clarifications_preserved"), total("clarifications_expected")
        ),
        ambiguity_violations=sum(len(result.ambiguity_violations) for result in results),
        negative_checks=neg_checks,
        negative_violations=neg_violations,
        negative_preservation_accuracy=_rate(neg_checks - neg_violations, neg_checks),
        evidence_grounding_checks=grounding_checks,
        evidence_grounding_violations=grounding_violations,
        evidence_grounding_rate=_rate(grounding_checks - grounding_violations, grounding_checks),
        total_facts=total_facts,
        unsupported_assertions=unsupported,
        unsupported_assertion_rate=_rate(unsupported, total_facts),
    )


__all__ = ["evaluate_case", "summarize"]
