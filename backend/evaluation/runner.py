"""Evaluation runner for the M-11 harness.

Commands::

    python -m backend.evaluation.runner --provider rules
    python -m backend.evaluation.runner --provider gemini --confirm-live-api
    python -m backend.evaluation.runner --compare reports/rules.json reports/gemini.json

The rules run is fully offline. The Gemini run is never implicit: it requires
``--confirm-live-api`` and valid credentials, makes one live request per case,
does not retry, and reports per-case failures instead of substituting a rules
result. Nothing here changes the production provider chain.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend.app.parse.rules import parse_rules_text

from . import DATASET_VERSION
from .loader import DEFAULT_DATASET, load_dataset
from .metrics import evaluate_case, summarize
from .report import render_comparison, write_reports
from .schema import EvaluationCase, EvaluationReport, EvaluationResult

DEFAULT_REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def run_rules(cases: list[EvaluationCase]) -> list[EvaluationResult]:
    """Evaluate the deterministic rules parser offline."""
    return [evaluate_case(case, parse_rules_text(case.text)) for case in cases]


def run_with_provider(cases: list[EvaluationCase], provider: object) -> list[EvaluationResult]:
    """Evaluate a live provider; failures are reported, never replaced."""
    from backend.app.parse.llm import parse_llm
    from backend.app.parse.normalize import normalize
    from backend.app.providers import ProviderError

    results: list[EvaluationResult] = []
    for case in cases:
        try:
            internal = asyncio.run(parse_llm(normalize(case.text), provider))  # type: ignore[arg-type]
        except ProviderError as exc:
            results.append(
                EvaluationResult(
                    case_id=case.id,
                    script=case.script,
                    tags=list(case.tags),
                    evaluated=False,
                    error=str(exc),
                )
            )
            continue
        results.append(evaluate_case(case, internal))
    return results


def build_report(
    *,
    parser: str,
    provider: str | None,
    model: str | None,
    results: list[EvaluationResult],
    cases_total: int,
    evaluated_at: str | None = None,
) -> EvaluationReport:
    """Assemble a report; metrics cover only successfully evaluated cases."""
    evaluated = [result for result in results if result.evaluated]
    return EvaluationReport(
        dataset_version=DATASET_VERSION,
        evaluated_at=evaluated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        parser=parser,
        provider=provider,
        model=model,
        cases_total=cases_total,
        cases_successful=len(evaluated),
        cases_failed=cases_total - len(evaluated),
        cases_unevaluated=cases_total - len(evaluated),
        summary=summarize(evaluated),
        per_case=results,
    )


def _print_summary(report: EvaluationReport) -> None:
    summary = report.summary
    print(
        f"cases: {report.cases_total} "
        f"(evaluated {report.cases_successful}, not evaluated {report.cases_unevaluated})"
    )
    print(
        "ingredient P/R/F1: "
        f"{summary.ingredient_precision} {summary.ingredient_recall} {summary.ingredient_f1}"
    )
    print(
        f"quantity accuracy: {summary.quantity_accuracy}; "
        f"association: {summary.quantity_association_accuracy}"
    )
    print(
        f"duration recall: {summary.duration_recall}; "
        f"clarification accuracy: {summary.clarification_accuracy}"
    )
    print(f"unsupported assertions: {summary.unsupported_assertions}/{summary.total_facts}")


def _load_report(path: Path) -> EvaluationReport:
    return EvaluationReport.model_validate(json.loads(path.read_text(encoding="utf-8")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the Thakuma's Recipe parsers.")
    parser.add_argument("--provider", choices=["rules", "gemini"], help="parser to evaluate")
    parser.add_argument(
        "--confirm-live-api",
        action="store_true",
        help="required for --provider gemini; confirms live API calls will be made",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument(
        "--compare",
        type=Path,
        nargs="+",
        metavar="REPORT_JSON",
        help="compare existing report JSON files side by side",
    )
    args = parser.parse_args(argv)

    if args.compare:
        reports = [_load_report(path) for path in args.compare]
        markdown = render_comparison(reports)
        comparison_path = args.reports_dir / "comparison.md"
        comparison_path.parent.mkdir(parents=True, exist_ok=True)
        comparison_path.write_text(markdown, encoding="utf-8")
        print(markdown)
        print(f"wrote {comparison_path}")
        return 0

    if args.provider is None:
        parser.error("--provider is required unless --compare is used")

    cases = load_dataset(args.dataset)
    texts = {case.id: case.text for case in cases}

    if args.provider == "rules":
        report = build_report(
            parser="rules",
            provider=None,
            model=None,
            results=run_rules(cases),
            cases_total=len(cases),
        )
    else:
        if not args.confirm_live_api:
            parser.error("--provider gemini makes live API calls; pass --confirm-live-api")
        from backend.app.config import get_settings
        from backend.app.providers import ProviderError
        from backend.app.providers.gemini import build_provider

        try:
            provider = build_provider(get_settings())
        except ProviderError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        report = build_report(
            parser="gemini",
            provider="gemini",
            model=provider.model,
            results=run_with_provider(cases, provider),
            cases_total=len(cases),
        )

    json_path, markdown_path = write_reports(report, args.reports_dir, texts)
    _print_summary(report)
    print(f"wrote {json_path} and {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
