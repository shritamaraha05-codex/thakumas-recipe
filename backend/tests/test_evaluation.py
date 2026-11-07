"""Tests for the M-11 evaluation harness.

Metric unit tests build tiny synthetic cases and internal ``parse.schema``
results so each metric can be checked in isolation. Dataset and runner tests use
the curated golden set and stay fully offline; no Gemini call is ever triggered.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest
from backend.app.models import Clarification, ParserMode, Source
from backend.app.parse import schema
from backend.app.parse.schema import QuantityKind
from backend.evaluation.loader import DatasetError, load_dataset
from backend.evaluation.metrics import evaluate_case, summarize
from backend.evaluation.report import render_comparison, render_markdown, write_reports
from backend.evaluation.runner import build_report, main, run_rules
from backend.evaluation.schema import (
    EvaluationCase,
    EvaluationReport,
    ExpectedClarification,
    ExpectedDuration,
    ExpectedIngredient,
    ExpectedQuantity,
    NegativeExpectation,
)

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _mention(text: str, canonical: str, surface: str, quantity=None, occurrence: int = 0):
    start = -1
    for _ in range(occurrence + 1):
        start = text.index(surface, start + 1)
    return schema.IngredientMention(
        canonical=canonical,
        surface=surface,
        orig_start=start,
        orig_end=start + len(surface),
        quantity=quantity,
    )


def _quantity(raw: str, qty=None, qty_max=None, unit=None, kind=QuantityKind.EXACT, to_taste=False):
    return schema.Quantity(
        raw_phrase=raw,
        qty=qty,
        qty_max=qty_max,
        unit=unit,
        kind=kind,
        to_taste=to_taste,
        source=Source.llm,
    )


def _duration(text: str, raw: str, value, unit):
    start = text.index(raw)
    return schema.Duration(
        raw_phrase=raw, value=value, unit=unit, orig_start=start, orig_end=start + len(raw)
    )


def _result(text: str, mentions=(), durations=(), clarifications=()):
    step = schema.RecipeStep(
        idx=1,
        text=text,
        orig_start=0,
        orig_end=len(text),
        durations=tuple(durations),
    )
    return schema.ParseResult(
        steps=(step,),
        ingredients=tuple(mentions),
        clarifications=tuple(clarifications),
        source=Source.llm,
        parser_mode=ParserMode.llm,
        llm_provider="gemini",
    )


def _case(text, *, case_id="t", ingredients=(), durations=(), clarifications=(), negatives=()):
    return EvaluationCase(
        id=case_id,
        text=text,
        script="roman",
        expected_ingredients=list(ingredients),
        expected_durations=list(durations),
        expected_clarifications=list(clarifications),
        negatives=list(negatives),
    )


def _expected(canonical, evidence, quantity=None):
    return ExpectedIngredient(canonical=canonical, evidence=evidence, quantity=quantity)


# --------------------------------------------------------------------------- #
# 1-3. Dataset loading and validation                                         #
# --------------------------------------------------------------------------- #


def test_curated_dataset_loads() -> None:
    cases = load_dataset()
    assert len(cases) == 21
    ids = [case.id for case in cases]
    assert len(ids) == len(set(ids))
    assert {case.script for case in cases} <= {"bengali", "roman", "mixed"}


def test_duplicate_case_ids_are_rejected(tmp_path: Path) -> None:
    line = json.dumps({"id": "dup", "text": "ek muthi chal", "script": "roman"})
    dataset = tmp_path / "dup.jsonl"
    dataset.write_text(f"{line}\n{line}\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="duplicate"):
        load_dataset(dataset)


def test_invalid_expected_facts_are_rejected(tmp_path: Path) -> None:
    bad = {
        "id": "bad",
        "text": "ektu tel",
        "script": "roman",
        "expected_ingredients": [
            {
                "canonical": "oil",
                "evidence": "ektu tel",
                "quantity": {"kind": "vague", "qty": 1},
            }
        ],
    }
    dataset = tmp_path / "bad.jsonl"
    dataset.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    with pytest.raises(DatasetError):
        load_dataset(dataset)


def test_invalid_range_is_rejected() -> None:
    with pytest.raises(ValueError):
        ExpectedQuantity(kind="range", qty=6, qty_max=5)


# --------------------------------------------------------------------------- #
# 4-6. Ingredient recognition                                                 #
# --------------------------------------------------------------------------- #


def test_exact_ingredient_and_quantity_match() -> None:
    text = "ek muthi chal"
    case = _case(
        text,
        ingredients=[
            _expected("rice", "ek muthi chal", ExpectedQuantity(kind="exact", qty=1, unit="muthi"))
        ],
    )
    result = _result(
        text, mentions=[_mention(text, "rice", "chal", _quantity("ek muthi", qty=1, unit="muthi"))]
    )
    evaluation = evaluate_case(case, result)
    assert (evaluation.ingredient_tp, evaluation.ingredient_fp, evaluation.ingredient_fn) == (
        1,
        0,
        0,
    )
    assert (evaluation.quantities_expected, evaluation.quantities_correct) == (1, 1)
    assert (evaluation.quantities_associated, evaluation.quantities_numeric_correct) == (1, 1)


def test_false_positive_ingredients_are_counted() -> None:
    text = "ek muthi chal ar chini"
    case = _case(text, ingredients=[_expected("rice", "ek muthi chal")])
    result = _result(
        text, mentions=[_mention(text, "rice", "chal"), _mention(text, "sugar", "chini")]
    )
    evaluation = evaluate_case(case, result)
    assert evaluation.ingredient_tp == 1
    assert evaluation.ingredient_fp == 1
    assert evaluation.unexpected_ingredients == ["sugar"]


def test_missing_ingredients_are_counted() -> None:
    text = "ek muthi chal"
    case = _case(text, ingredients=[_expected("rice", "ek muthi chal"), _expected("salt", "chal")])
    result = _result(text, mentions=[_mention(text, "rice", "chal")])
    evaluation = evaluate_case(case, result)
    assert evaluation.ingredient_fn == 1
    assert evaluation.missing_ingredients == ["salt"]


# --------------------------------------------------------------------------- #
# 7-10. Quantity extraction (incl. ranges, vague, taste)                      #
# --------------------------------------------------------------------------- #


def test_quantity_association_is_scored_separately_from_recognition() -> None:
    text = "ek muthi chal"
    case = _case(
        text,
        ingredients=[
            _expected("rice", "ek muthi chal", ExpectedQuantity(kind="exact", qty=1, unit="muthi"))
        ],
    )
    result = _result(text, mentions=[_mention(text, "rice", "chal")])  # no quantity
    evaluation = evaluate_case(case, result)
    assert evaluation.ingredient_tp == 1  # ingredient recognised
    assert evaluation.quantities_expected == 1
    assert evaluation.quantities_associated == 0  # but no association
    assert evaluation.quantities_correct == 0
    assert evaluation.quantity_mismatches


def test_explicit_range_is_evaluated() -> None:
    text = "tin-char muthi chal"
    case = _case(
        text,
        ingredients=[
            _expected(
                "rice",
                "tin-char muthi chal",
                ExpectedQuantity(kind="range", qty=3, qty_max=4, unit="muthi"),
            )
        ],
    )
    result = _result(
        text,
        mentions=[
            _mention(
                text,
                "rice",
                "chal",
                _quantity(
                    "tin-char muthi", qty=3, qty_max=4, unit="muthi", kind=QuantityKind.RANGE
                ),
            )
        ],
    )
    evaluation = evaluate_case(case, result)
    assert evaluation.quantities_range_expected == 1
    assert evaluation.quantities_range_correct == 1
    assert evaluation.quantities_correct == 1


def test_vague_quantity_is_not_treated_as_numeric() -> None:
    text = "ektu tel"
    case = _case(text, ingredients=[_expected("oil", "ektu tel", ExpectedQuantity(kind="vague"))])
    result = _result(
        text, mentions=[_mention(text, "oil", "tel", _quantity("ektu", kind=QuantityKind.VAGUE))]
    )
    evaluation = evaluate_case(case, result)
    assert evaluation.quantities_vague_expected == 1
    assert evaluation.quantities_vague_correct == 1
    assert evaluation.quantities_numeric_expected == 0
    assert evaluation.quantities_correct == 1


def test_taste_quantity_is_evaluated() -> None:
    text = "স্বাদমতো নুন"
    case = _case(
        text,
        ingredients=[_expected("salt", "স্বাদমতো নুন", ExpectedQuantity(kind="taste", to_taste=True))],
    )
    result = _result(
        text,
        mentions=[
            _mention(
                text, "salt", "নুন", _quantity("স্বাদমতো", kind=QuantityKind.TASTE, to_taste=True)
            )
        ],
    )
    evaluation = evaluate_case(case, result)
    assert evaluation.quantities_taste_expected == 1
    assert evaluation.quantities_taste_correct == 1
    assert evaluation.quantities_correct == 1


# --------------------------------------------------------------------------- #
# 11. Durations                                                               #
# --------------------------------------------------------------------------- #


def test_duration_extraction_is_scored_separately() -> None:
    text = "dosh minute ranna koro"
    case = _case(
        text,
        durations=[ExpectedDuration(value=10, unit="minute", evidence="dosh minute")],
    )
    result = _result(text, durations=[_duration(text, "dosh minute", 10, "minute")])
    evaluation = evaluate_case(case, result)
    assert evaluation.durations_expected == 1
    assert evaluation.durations_correct == 1
    assert evaluation.duration_ingredient_misattachments == 0


def test_duration_attached_to_ingredient_is_counted() -> None:
    text = "dosh minute ranna koro"
    case = _case(
        text, durations=[ExpectedDuration(value=10, unit="minute", evidence="dosh minute")]
    )
    result = _result(
        text,
        mentions=[_mention(text, "rice", "ranna", _quantity("dosh", qty=10, unit="minute"))],
        durations=[_duration(text, "dosh minute", 10, "minute")],
    )
    evaluation = evaluate_case(case, result)
    assert evaluation.duration_ingredient_misattachments == 1


# --------------------------------------------------------------------------- #
# 12. Ambiguity preservation                                                  #
# --------------------------------------------------------------------------- #


def test_expected_clarification_is_preserved() -> None:
    text = "ek chamoch tel"
    case = _case(
        text,
        clarifications=[ExpectedClarification(kind="unit_spoon", unit="spoon", evidence="chamoch")],
    )
    clarification = Clarification(
        id="unit_spoon_1", kind="unit_spoon", question="?", options=["tsp", "tbsp"]
    )
    result = _result(text, clarifications=[clarification])
    evaluation = evaluate_case(case, result)
    assert evaluation.clarifications_preserved == 1
    assert evaluation.ambiguity_violations == []


def test_forbidden_clarification_is_a_violation() -> None:
    text = "ek choto chamoch tel"
    case = _case(
        text,
        negatives=[NegativeExpectation(kind="clarification", value="unit_spoon")],
    )
    clarification = Clarification(id="unit_spoon_1", kind="unit_spoon", question="?")
    result = _result(text, clarifications=[clarification])
    evaluation = evaluate_case(case, result)
    assert evaluation.negative_violations
    assert evaluation.ambiguity_violations


# --------------------------------------------------------------------------- #
# 13-14. Evidence grounding and unsupported assertions                        #
# --------------------------------------------------------------------------- #


def test_unsupported_assertion_is_counted() -> None:
    text = "ek muthi chal"
    case = _case(text, ingredients=[_expected("rice", "ek muthi chal")])
    ghost = schema.IngredientMention(canonical="ghost", surface="ghost", orig_start=0, orig_end=5)
    result = _result(text, mentions=[ghost])
    evaluation = evaluate_case(case, result)
    assert evaluation.evidence_grounding_violations
    assert evaluation.unsupported_assertions
    assert evaluation.total_facts == 1


def test_evidence_must_occur_in_the_transcript(tmp_path: Path) -> None:
    bad = {
        "id": "bad-evidence",
        "text": "ek muthi chal",
        "script": "roman",
        "expected_ingredients": [{"canonical": "rice", "evidence": "not in the transcript"}],
    }
    dataset = tmp_path / "bad_evidence.jsonl"
    dataset.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="not a substring"):
        load_dataset(dataset)


def test_bad_spans_are_flagged() -> None:
    text = "ek muthi chal"
    case = _case(text, ingredients=[_expected("rice", "chal")])
    wrong_span = schema.IngredientMention(
        canonical="rice", surface="chal", orig_start=0, orig_end=len(text)
    )
    evaluation = evaluate_case(case, _result(text, mentions=[wrong_span]))
    assert evaluation.evidence_grounding_violations


# --------------------------------------------------------------------------- #
# 15-17. Runner behaviour: determinism, offline, no implicit Gemini           #
# --------------------------------------------------------------------------- #


def test_repeated_rules_evaluation_is_identical() -> None:
    cases = load_dataset()
    first = run_rules(cases)
    second = run_rules(cases)
    assert [result.model_dump() for result in first] == [result.model_dump() for result in second]
    assert summarize(first) == summarize(second)


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted during an offline evaluation")

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)


def test_rules_evaluation_makes_no_network_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _block_network(monkeypatch)
    assert main(["--provider", "rules", "--reports-dir", str(tmp_path)]) == 0
    assert (tmp_path / "latest.json").exists()
    assert (tmp_path / "latest.md").exists()


def test_gemini_is_never_triggered_without_confirmation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _block_network(monkeypatch)
    import backend.app.providers.gemini as gemini

    def _must_not_build(settings):
        raise AssertionError("Gemini provider must not be built without --confirm-live-api")

    monkeypatch.setattr(gemini, "build_provider", _must_not_build)
    with pytest.raises(SystemExit):
        main(["--provider", "gemini", "--reports-dir", str(tmp_path)])
    assert not (tmp_path / "latest.json").exists()


# --------------------------------------------------------------------------- #
# Reports                                                                     #
# --------------------------------------------------------------------------- #


def test_report_round_trips_and_renders(tmp_path: Path) -> None:
    cases = load_dataset()[:3]
    report = build_report(
        parser="rules",
        provider=None,
        model=None,
        results=run_rules(cases),
        cases_total=len(cases),
        evaluated_at="fixed",
    )
    json_path, markdown_path = write_reports(
        report, tmp_path, {case.id: case.text for case in cases}
    )
    loaded = EvaluationReport.model_validate_json(json_path.read_text(encoding="utf-8"))
    assert loaded.summary == report.summary
    assert loaded.dataset_version == report.dataset_version
    assert "# Parser evaluation report" in markdown_path.read_text(encoding="utf-8")
    assert "# Parser comparison" in render_comparison([report])
    assert "Metrics" in render_markdown(report)
