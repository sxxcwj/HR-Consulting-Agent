"""Optional real DeepSeek tool-choice check for V0.9 report generation."""

from __future__ import annotations

import os

import pytest

from src.agent import HRConsultant


@pytest.mark.live
def test_live_agent_selects_generate_hr_report(monkeypatch: pytest.MonkeyPatch) -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is not configured in this environment")
    monkeypatch.setattr(
        "src.agent.generate_hr_report",
        lambda **kwargs: {
            "success": True,
            "status": "generated",
            "report_id": "RPT-LIVE-TEST",
            "file_path": "/tmp/RPT-LIVE-TEST.md",
            "format": "markdown",
            "draft": True,
        },
    )
    agent = HRConsultant()
    answer = agent.ask(
        "请根据以下已知信息生成一份HR报告：公司约200人，管理层观察到销售人员离职增加；"
        "目前没有准确离职率，也尚未验证薪酬是否为原因。"
    )
    assert agent.last_tool_calls == ["generate_hr_report"]
    assert "RPT-LIVE-TEST" in answer
