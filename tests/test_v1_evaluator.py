"""Contract tests for the V1.0 cross-version evaluation set."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from evals.evaluator import evaluate_case, evaluate_results


CASES_PATH = Path(__file__).resolve().parents[1] / "evals" / "v1_capability_cases.json"


def _cases() -> list[dict[str, object]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def test_capability_dataset_has_three_cases_for_every_added_version() -> None:
    cases = _cases()
    assert len(cases) == 24
    assert len({case["id"] for case in cases}) == 24
    assert Counter(case["version"] for case in cases) == {
        f"V0.{version}": 3 for version in range(2, 10)
    }


def test_evaluate_case_checks_tools_and_text() -> None:
    case = {
        "id": "example",
        "expected_tools": ["required_tool"],
        "forbidden_tools": ["forbidden_tool"],
        "required_text": ["依据"],
        "forbidden_text": ["编造"],
    }

    assert evaluate_case(case, answer="有依据", tool_calls=["required_tool"])["passed"]
    assert not evaluate_case(case, answer="有依据", tool_calls=[])["passed"]
    assert not evaluate_case(
        case,
        answer="有依据但编造",
        tool_calls=["required_tool", "forbidden_tool"],
    )["passed"]


def test_evaluate_results_marks_missing_records_as_failed() -> None:
    cases = _cases()[:2]
    summary = evaluate_results(cases, [])

    assert summary["total"] == 2
    assert summary["passed"] == 0
    assert summary["failed"] == 2
    assert summary["cases"][0]["checks"] == {"result_recorded": False}
