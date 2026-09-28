"""Optional live checks for model tool-choice behavior."""

import os
from typing import Any

import pytest

from src.agent import HRConsultant, validate_analysis


class RecordingResponses:
    def __init__(self, wrapped: Any) -> None:
        self.wrapped = wrapped
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.wrapped.create(**kwargs)


def _run_live_case(question: str) -> tuple[str, bool]:
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is not configured in this environment")

    agent = HRConsultant()
    recorder = RecordingResponses(agent.client.responses)
    agent.client.responses = recorder  # type: ignore[assignment]
    answer = agent.ask(question)
    validate_analysis(answer)
    used_tool = any(
        isinstance(item, dict) and item.get("type") == "function_call_output"
        for call in recorder.calls
        for item in call.get("input", [])
    )
    return answer, used_tool


@pytest.mark.live
def test_live_case_a_calls_turnover_tool() -> None:
    answer, used_tool = _run_live_case(
        "公司年初200人，年末180人，全年离职30人，离职率是多少？"
    )

    assert used_tool
    assert "190" in answer
    assert "15.79" in answer


@pytest.mark.live
def test_live_case_b_does_not_call_tool_for_cause_analysis() -> None:
    _, used_tool = _run_live_case(
        "我们公司最近人员流失严重，你认为可能是什么原因？"
    )

    assert not used_tool


@pytest.mark.live
def test_live_case_c_does_not_guess_missing_headcount() -> None:
    answer, used_tool = _run_live_case("今年离职30人，离职率是多少？")

    assert not used_tool
    assert "平均员工人数" in answer
    assert "期初" in answer
    assert "期末" in answer
