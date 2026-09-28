"""Acceptance case set integrity checks."""

import json
from collections import Counter
from pathlib import Path


CASE_PATH = Path(__file__).resolve().parents[1] / "evals" / "acceptance_cases.json"
CATEGORIES = {
    "complete_single",
    "missing_information",
    "multi_module",
    "subjective_claim",
    "high_risk",
    "follow_up_revision",
}


def test_fixed_case_set_has_six_categories_of_two() -> None:
    cases = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    assert len(cases) == 12
    assert len({case["id"] for case in cases}) == 12
    assert Counter(case["category"] for case in cases) == {
        category: 2 for category in CATEGORIES
    }


def test_cases_include_review_points_and_follow_up_turns() -> None:
    cases = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    for case in cases:
        assert case["turns"] and all(turn.strip() for turn in case["turns"])
        assert case["checks"] and case["forbidden"]
        expected_turns = 2 if case["category"] == "follow_up_revision" else 1
        assert len(case["turns"]) == expected_turns
