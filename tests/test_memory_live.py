"""Optional real DeepSeek tool-choice check for V0.8 Memory."""

from __future__ import annotations

import os

import pytest

from src.agent import HRConsultant


@pytest.mark.live
def test_live_agent_selects_save_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is not configured in this environment")
    monkeypatch.setattr(
        "src.agent.save_memory",
        lambda **kwargs: {
            "success": True,
            "status": "saved",
            "memory": {
                "memory_id": "MEM-LIVE-TEST",
                "category": kwargs["category"],
                "content": kwargs["content"],
                "updated_at": "2026-09-28T00:00:00+00:00",
            },
        },
    )
    agent = HRConsultant()
    answer = agent.ask("请明确长期记住：我的偏好是HR分析默认使用中文。")
    assert agent.last_tool_calls == ["save_memory"]
    assert "MEM-LIVE-TEST" in answer
