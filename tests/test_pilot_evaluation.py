"""Deterministic checks for the anonymous pilot harness."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from evals.pilot_runner import _evaluate_case

from .conftest import VALID_ANALYSIS


CASES_PATH = Path(__file__).resolve().parents[1] / "evals" / "pilot_cases.json"


def test_pilot_case_set_has_two_cases_in_each_planned_category() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    assert len(cases) == 16
    assert len({case["id"] for case in cases}) == 16
    assert set(Counter(case["category"] for case in cases).values()) == {2}
    assert {case["response_contract"] for case in cases} >= {
        "five_sections",
        "tool_result",
        "boundary",
    }


def test_pilot_evaluator_checks_tools_contract_stream_and_privacy() -> None:
    case = {
        "question": "请计算匿名化员工样例的离职率。",
        "expected_tools": ["calculate_turnover_rate"],
        "forbidden_tools": ["save_memory"],
        "required_any": [["问题判断"], ["下一步行动"]],
        "forbidden_text": ["真实员工姓名"],
        "response_contract": "five_sections",
    }

    passed = _evaluate_case(
        case,
        answer=VALID_ANALYSIS.strip(),
        tool_calls=["calculate_turnover_rate"],
        stream_text=VALID_ANALYSIS.strip(),
        error=None,
    )
    failed = _evaluate_case(
        case,
        answer=VALID_ANALYSIS.strip(),
        tool_calls=["save_memory"],
        stream_text="不一致",
        error=None,
    )

    assert all(passed.values())
    assert failed["expected_tools_called"] is False
    assert failed["forbidden_tools_not_called"] is False
    assert failed["stream_matches_final"] is False
