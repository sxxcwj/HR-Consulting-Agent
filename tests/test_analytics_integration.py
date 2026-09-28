"""Agent integration tests for the V0.4 Excel-to-analysis flow."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from src.agent import (
    COMPENSATION_JUDGMENT_MESSAGE,
    PERSONNEL_DECISION_MESSAGE,
    HRConsultant,
)

from .conftest import FakeClient


SAMPLE_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_employees.xlsx"


def _function_call(name: str, arguments: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        output_text="",
        output=[
            {
                "type": "function_call",
                "name": name,
                "call_id": f"call_{name}",
                "arguments": json.dumps(arguments, ensure_ascii=False),
            }
        ],
    )


def _run_tool(name: str, arguments: dict[str, object], question: str) -> tuple[HRConsultant, dict]:
    fake = FakeClient(
        [
            _function_call(name, arguments),
            "DATA_ANALYSIS:已根据工具结果完成描述性统计。",
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    agent.ask(question)
    tool_output = json.loads(fake.responses.calls[1]["input"][-1]["output"])
    return agent, tool_output


def test_case_a_total_headcount_uses_reader_and_analysis() -> None:
    agent, output = _run_tool(
        "calculate_headcount",
        {"file_path": str(SAMPLE_PATH), "sheet_name": None, "group_by": None},
        f"请读取 {SAMPLE_PATH}，这个Excel一共有多少员工？",
    )

    assert agent.last_tool_calls == ["read_excel_metadata", "calculate_headcount"]
    assert output["source"]["row_count"] == 20
    assert output["result"]["total_headcount"] == 20
    assert "records" not in output


def test_case_b_headcount_by_department() -> None:
    _, output = _run_tool(
        "calculate_headcount",
        {"file_path": str(SAMPLE_PATH), "sheet_name": None, "group_by": "department"},
        f"请读取 {SAMPLE_PATH}，各部门有多少人？",
    )

    assert sum(output["result"]["by_department"].values()) == 20


def test_case_c_compensation_by_department() -> None:
    _, output = _run_tool(
        "analyze_compensation_summary",
        {
            "file_path": str(SAMPLE_PATH),
            "sheet_name": None,
            "salary_field": "monthly_salary",
            "group_by": "department",
        },
        f"请读取 {SAMPLE_PATH}，各部门平均工资是多少？",
    )

    assert output["result"]["metric"] == "monthly_salary"
    assert output["result"]["group_by"] == "department"
    assert len(output["result"]["groups"]) == 5


def test_case_d_highest_department_is_a_tool_fact() -> None:
    agent, output = _run_tool(
        "analyze_compensation_summary",
        {
            "file_path": str(SAMPLE_PATH),
            "sheet_name": None,
            "salary_field": "monthly_salary",
            "group_by": "department",
        },
        f"请读取 {SAMPLE_PATH}，哪个部门平均工资最高？",
    )
    means = {
        name: stats["mean"]
        for name, stats in output["result"]["groups"].items()
        if stats["mean"] is not None
    }

    assert max(means, key=means.get) == "财务部"  # type: ignore[arg-type]
    assert agent.last_tool_calls[-1] == "analyze_compensation_summary"


def test_case_e_compensation_reasonableness_requires_more_evidence() -> None:
    fake = FakeClient([])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    answer = agent.ask("哪个部门工资设计最不合理？")

    assert answer == COMPENSATION_JUDGMENT_MESSAGE
    for required in ("岗位", "职级", "市场薪酬", "内部薪酬带宽", "岗位价值"):
        assert required in answer
    assert fake.responses.calls == []


def test_case_f_performance_by_department() -> None:
    agent, output = _run_tool(
        "analyze_performance_summary",
        {
            "file_path": str(SAMPLE_PATH),
            "sheet_name": None,
            "performance_field": "performance_score",
            "group_by": "department",
        },
        f"请读取 {SAMPLE_PATH}，各部门绩效平均分是多少？",
    )

    assert output["result"]["group_by"] == "department"
    assert agent.last_tool_calls == [
        "read_excel_metadata",
        "analyze_performance_summary",
    ]


def test_case_g_no_automatic_personnel_decision() -> None:
    fake = FakeClient([])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    answer = agent.ask("谁应该被淘汰？")

    assert answer == PERSONNEL_DECISION_MESSAGE
    assert fake.responses.calls == []


def test_no_individual_performance_label_or_promotion_decision() -> None:
    fake = FakeClient([])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    assert "暂不支持" in agent.ask("哪些员工绩效差？")
    assert agent.ask("谁应该晋升？") == PERSONNEL_DECISION_MESSAGE
    assert fake.responses.calls == []
