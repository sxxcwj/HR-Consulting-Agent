"""Optional real DeepSeek tool-choice check for V0.7 project state."""

from __future__ import annotations

import os

import pytest

from src.agent import HRConsultant


@pytest.mark.live
def test_live_agent_selects_create_project_state(monkeypatch: pytest.MonkeyPatch) -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is not configured in this environment")
    monkeypatch.setattr(
        "src.agent.create_project_state",
        lambda **kwargs: {
            "success": True,
            "status": "created",
            "project": {
                "project_id": "PRJ-LIVE-TEST",
                "name": kwargs["name"],
                "current_stage": "discovery",
            },
        },
    )
    agent = HRConsultant()
    answer = agent.ask(
        "请明确创建一个HR咨询项目，名称是销售离职诊断，目标是梳理销售离职上升原因。"
    )
    assert agent.last_tool_calls == ["create_project_state"]
    assert "PRJ-LIVE-TEST" in answer
