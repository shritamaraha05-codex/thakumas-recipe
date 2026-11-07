"""Load and validate the curated evaluation dataset (M-11).

The dataset is JSONL: one :class:`~backend.evaluation.schema.EvaluationCase` per
line. Loading fails loudly (``DatasetError``) on a malformed record, a duplicate
case id, or an evidence phrase that does not occur verbatim in the transcript, so
an annotation can never be invented or drift from the narration.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .schema import EvaluationCase

DEFAULT_DATASET = Path(__file__).resolve().parent / "dataset" / "recipes.jsonl"


class DatasetError(ValueError):
    """Raised when the dataset cannot be loaded or is internally inconsistent."""


def _evidence_phrases(case: EvaluationCase) -> list[tuple[str, str]]:
    """Every ``(label, evidence)`` pair a case asserts."""
    phrases: list[tuple[str, str]] = []
    for ingredient in case.expected_ingredients:
        phrases.append((f"ingredient '{ingredient.canonical}'", ingredient.evidence))
    for duration in case.expected_durations:
        phrases.append(("duration", duration.evidence))
    for clarification in case.expected_clarifications:
        phrases.append((f"clarification '{clarification.kind}'", clarification.evidence))
    return phrases


def validate_evidence(case: EvaluationCase) -> None:
    """Every expected fact must cite a phrase that occurs in the transcript."""
    for label, evidence in _evidence_phrases(case):
        if evidence not in case.text:
            raise DatasetError(
                f"case {case.id!r}: evidence for {label} ({evidence!r}) "
                "is not a substring of the transcript"
            )


def load_dataset(path: Path = DEFAULT_DATASET) -> list[EvaluationCase]:
    """Load, validate and de-duplicate every case in ``path``."""
    if not path.exists():
        raise DatasetError(f"dataset file not found: {path}")

    cases: list[EvaluationCase] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetError(f"{path.name}:{line_number}: invalid JSON ({exc.msg})") from exc
        try:
            case = EvaluationCase.model_validate(payload)
        except ValidationError as exc:
            raise DatasetError(f"{path.name}:{line_number}: invalid case ({exc})") from exc
        if case.id in seen:
            raise DatasetError(f"{path.name}:{line_number}: duplicate case id {case.id!r}")
        seen.add(case.id)
        validate_evidence(case)
        cases.append(case)

    return cases


__all__ = ["DEFAULT_DATASET", "DatasetError", "load_dataset", "validate_evidence"]
