"""Report rendering for the M-11 evaluation harness.

Writes a machine-readable ``latest.json`` and a readable ``latest.md``. A small
comparison renderer puts two parser reports side by side. Reports are honest by
construction: they show numerators and denominators next to every rate and state
that the dataset is small and curated, so a high score is never presented as
proof of general dialect coverage.
"""

from __future__ import annotations

from pathlib import Path

from .schema import EvaluationReport, EvaluationResult, MetricSummary

CAVEAT = (
    "This is a small, manually curated golden set. A high score here shows that "
    "the documented cases are handled; it does not prove that every Bengali "
    "dialect, spelling variant or cooking style is supported."
)


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _ratio(numerator: int, denominator: int) -> str:
    return f"{numerator}/{denominator}"


def _metric_rows(summary: MetricSummary) -> list[tuple[str, str]]:
    return [
        ("Ingredient precision", _pct(summary.ingredient_precision)),
        ("Ingredient recall", _pct(summary.ingredient_recall)),
        ("Ingredient F1", _pct(summary.ingredient_f1)),
        (
            "Ingredient TP / FP / FN",
            f"{summary.ingredient_tp} / {summary.ingredient_fp} / {summary.ingredient_fn}",
        ),
        (
            "Quantity accuracy (full match)",
            f"{_ratio(summary.quantities_correct, summary.quantities_expected)} "
            f"({_pct(summary.quantity_accuracy)})",
        ),
        (
            "Quantity association accuracy",
            f"{_ratio(summary.quantities_associated, summary.quantities_expected)} "
            f"({_pct(summary.quantity_association_accuracy)})",
        ),
        (
            "Numeric quantity correct",
            _ratio(summary.quantities_numeric_correct, summary.quantities_numeric_expected),
        ),
        (
            "Explicit range correct",
            _ratio(summary.quantities_range_correct, summary.quantities_range_expected),
        ),
        ("Unit correct", _ratio(summary.quantities_unit_correct, summary.quantities_expected)),
        (
            "Vague quantity preserved",
            _ratio(summary.quantities_vague_correct, summary.quantities_vague_expected),
        ),
        (
            "Taste quantity preserved",
            _ratio(summary.quantities_taste_correct, summary.quantities_taste_expected),
        ),
        (
            "Duration recall (value + unit)",
            f"{_ratio(summary.durations_correct, summary.durations_expected)} "
            f"({_pct(summary.duration_recall)})",
        ),
        (
            "Duration value correct",
            _ratio(summary.durations_value_correct, summary.durations_value_expected),
        ),
        (
            "Duration unit correct",
            _ratio(summary.durations_unit_correct, summary.durations_unit_expected),
        ),
        (
            "Durations wrongly attached to ingredients",
            str(summary.duration_ingredient_misattachments),
        ),
        (
            "Clarifications preserved",
            f"{_ratio(summary.clarifications_preserved, summary.clarifications_expected)} "
            f"({_pct(summary.clarification_accuracy)})",
        ),
        ("Ambiguity violations", str(summary.ambiguity_violations)),
        (
            "Negative expectations preserved",
            f"{_ratio(summary.negative_checks - summary.negative_violations, summary.negative_checks)} "
            f"({_pct(summary.negative_preservation_accuracy)})",
        ),
        (
            "Evidence grounding",
            f"{_ratio(summary.evidence_grounding_checks - summary.evidence_grounding_violations, summary.evidence_grounding_checks)} "
            f"({_pct(summary.evidence_grounding_rate)})",
        ),
        (
            "Unsupported assertions",
            f"{summary.unsupported_assertions}/{summary.total_facts} "
            f"({_pct(summary.unsupported_assertion_rate)})",
        ),
    ]


def _case_failed(result: EvaluationResult) -> bool:
    return bool(
        not result.evaluated
        or result.error
        or result.missing_ingredients
        or result.unexpected_ingredients
        or result.quantity_mismatches
        or result.duration_mismatches
        or result.negative_violations
        or result.ambiguity_violations
        or result.evidence_grounding_violations
        or result.unsupported_assertions
        or result.step_count_ok is False
    )


def _case_lines(result: EvaluationResult, texts: dict[str, str] | None) -> list[str]:
    lines = [f"### {result.case_id} ({result.script})"]
    if texts and result.case_id in texts:
        lines.append(f"- Transcript: {texts[result.case_id]}")
    if not result.evaluated:
        lines.append(f"- NOT EVALUATED: {result.error}")
        return lines
    if result.error:
        lines.append(f"- Error: {result.error}")
    if result.step_count_ok is False:
        lines.append(
            f"- Step count: expected {result.step_count_expected}, got {result.step_count_actual}"
        )
    lines.append(f"- Expected ingredients: {', '.join(result.ingredients_expected) or '(none)'}")
    lines.append(f"- Actual ingredients: {', '.join(result.ingredients_actual) or '(none)'}")
    if result.missing_ingredients:
        lines.append(f"- Missing ingredients: {', '.join(result.missing_ingredients)}")
    if result.unexpected_ingredients:
        lines.append(f"- Unexpected ingredients: {', '.join(result.unexpected_ingredients)}")
    for mismatch in result.quantity_mismatches:
        lines.append(f"- Quantity: {mismatch}")
    for mismatch in result.duration_mismatches:
        lines.append(f"- Duration: {mismatch}")
    for violation in result.ambiguity_violations:
        lines.append(f"- Ambiguity: {violation}")
    for violation in result.negative_violations:
        lines.append(f"- Negative: {violation}")
    for violation in result.evidence_grounding_violations:
        lines.append(f"- Evidence: {violation}")
    for assertion in result.unsupported_assertions:
        lines.append(f"- Unsupported: {assertion}")
    return lines


def render_markdown(report: EvaluationReport, texts: dict[str, str] | None = None) -> str:
    """Render the readable report for one parser/provider run."""
    model = report.model or "n/a"
    lines = [
        "# Parser evaluation report (M-11)",
        "",
        f"- Dataset version: {report.dataset_version}",
        f"- Evaluated at: {report.evaluated_at}",
        f"- Parser: {report.parser}",
        f"- Provider: {report.provider or 'n/a'}",
        f"- Model: {model}",
        f"- Cases: {report.cases_total} total, {report.cases_successful} evaluated, "
        f"{report.cases_unevaluated} not evaluated",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for name, value in _metric_rows(report.summary):
        lines.append(f"| {name} | {value} |")

    lines.extend(["", "## Per-case failures", ""])
    failures = [result for result in report.per_case if _case_failed(result)]
    if not failures:
        lines.append(
            "No cases failed. (Ingredient recognition only compares sets; see known limitations.)"
        )
    else:
        for result in failures:
            lines.extend(_case_lines(result, texts))
            lines.append("")

    lines.extend(["", "## Reading this report", "", CAVEAT, ""])
    return "\n".join(lines)


def write_reports(
    report: EvaluationReport,
    out_dir: Path,
    texts: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    """Write ``latest.json`` and ``latest.md`` into ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "latest.json"
    markdown_path = out_dir / "latest.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report, texts), encoding="utf-8")
    return json_path, markdown_path


def render_comparison(reports: list[EvaluationReport]) -> str:
    """Put the same metrics side by side for two or more parser reports."""
    if not reports:
        return "No reports to compare."
    labels = [report.provider or report.parser for report in reports]
    lines = [
        "# Parser comparison (M-11)",
        "",
        "| Metric | " + " | ".join(labels) + " |",
        "|---|" + "---|" * len(reports),
    ]
    rows_by_report = [_metric_rows(report.summary) for report in reports]
    for name, _ in _metric_rows(reports[0].summary):
        values = [_lookup(rows, name) for rows in rows_by_report]
        lines.append(f"| {name} | " + " | ".join(values) + " |")
    lines.extend(["", CAVEAT, ""])
    return "\n".join(lines)


def _lookup(rows: list[tuple[str, str]], name: str) -> str:
    for metric_name, value in rows:
        if metric_name == name:
            return value
    return "n/a"


__all__ = ["render_comparison", "render_markdown", "write_reports"]
