"""Responses API function-calling integration without network access."""

import json
from types import SimpleNamespace
from typing import Any

from src.agent import REGISTERED_TOOLS, HRConsultant

from .conftest import FakeClient


def _function_call(arguments: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        output_text="",
        output=[
            {
                "type": "function_call",
                "name": "calculate_turnover_rate",
                "call_id": "call_turnover_1",
                "arguments": json.dumps(arguments),
            }
        ],
    )


def test_case_a_executes_tool_and_returns_result_to_model(valid_analysis: str) -> None:
    fake = FakeClient(
        [
            _function_call(
                {
                    "leavers": 30,
                    "average_headcount": None,
                    "starting_headcount": 200,
                    "ending_headcount": 180,
                }
            ),
            valid_analysis,
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    answer = agent.ask("公司年初200人，年末180人，全年离职30人，离职率是多少？")

    assert answer == valid_analysis.strip()
    assert len(fake.responses.calls) == 2
    assert fake.responses.calls[0]["tools"] == REGISTERED_TOOLS
    tool_output = fake.responses.calls[1]["input"][-1]
    assert tool_output["type"] == "function_call_output"
    result = json.loads(tool_output["output"])
    assert result["average_headcount"] == 190
    assert result["turnover_rate"] == 15.79


def test_case_b_does_not_execute_tool_without_calculation_request(
    valid_analysis: str,
) -> None:
    fake = FakeClient([valid_analysis])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    agent.ask("我们公司最近人员流失严重，你认为可能是什么原因？")

    assert len(fake.responses.calls) == 1
    assert not any(
        isinstance(item, dict) and item.get("type") == "function_call_output"
        for item in fake.responses.calls[0]["input"]
    )


def test_case_c_missing_headcount_is_explained_without_tool_call() -> None:
    missing_information_answer = """# 问题判断

目前只知道今年离职30人，缺少计算离职率所需的员工人数基数，因此不能得出离职率。

# 可能原因

本问题是数据口径缺失，不涉及对流失原因的判断。

# 需要补充的信息

请提供平均员工人数，或者同时提供期初和期末员工人数。

# 建议措施

先确认统计期间和人数口径，再进行计算，不使用估算人数。

# 下一步行动

1. 由 HR 提供同一统计期间的平均员工人数，或期初、期末人数。
"""
    fake = FakeClient([missing_information_answer])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    answer = agent.ask("今年离职30人，离职率是多少？")

    assert len(fake.responses.calls) == 1
    assert "平均员工人数" in answer
    assert "期初和期末员工人数" in answer
    assert "30人，缺少" in answer


def test_tool_validation_error_is_returned_to_model(valid_analysis: str) -> None:
    fake = FakeClient(
        [
            _function_call(
                {
                    "leavers": 30,
                    "average_headcount": None,
                    "starting_headcount": None,
                    "ending_headcount": None,
                }
            ),
            valid_analysis,
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    agent.ask("今年离职30人，离职率是多少？")

    tool_output = fake.responses.calls[1]["input"][-1]
    assert "缺少必要人数" in json.loads(tool_output["output"])["error"]
