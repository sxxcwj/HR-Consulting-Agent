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
        "required_patterns": [r"问题.*判断"],
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


def test_source_and_delivery_boundaries_use_evidence_based_contracts() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    compensation_case = next(case for case in cases if case["id"] == "PILOT-05")
    rag_case = next(case for case in cases if case["id"] == "PILOT-09")
    delivery_case = next(case for case in cases if case["id"] == "PILOT-16")

    assert ["7566.75"] in compensation_case["required_any"]
    assert ["15268.75"] in compensation_case["required_any"]
    assert any("document_id" in group for group in rag_case["required_any"])
    assert delivery_case["required_any"] == [["Markdown"]]
    assert len(delivery_case["required_patterns"]) == 2


def test_boundary_patterns_accept_clear_refusal_without_fixed_wording() -> None:
    case = next(
        case
        for case in json.loads(CASES_PATH.read_text(encoding="utf-8"))
        if case["id"] == "PILOT-16"
    )
    answer = "我无法生成 Word，也无法自动把报告发送给管理层；只能生成 Markdown 草稿。"

    checks = _evaluate_case(
        case,
        answer=answer,
        tool_calls=[],
        stream_text=answer,
        error=None,
    )

    assert all(checks.values())
