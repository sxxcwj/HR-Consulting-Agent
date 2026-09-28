"""Optional end-to-end RAG tool selection with the real DeepSeek API."""

from __future__ import annotations

import os

import pytest

from src.agent import AgentError, HRConsultant
from src.knowledge import get_knowledge_index_status


@pytest.mark.live
def test_live_agent_uses_rag_and_cites_real_source() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is not configured in this environment")
    status = get_knowledge_index_status()
    if not status.get("success") or not status.get("ready"):
        pytest.skip("local knowledge index is not ready")

    try:
        agent = HRConsultant()
        answer = agent.ask("公司制度里年度调薪是什么时候进行？请说明实际文件来源。")
    except AgentError as exc:
        pytest.fail(str(exc), pytrace=False)

    assert "search_knowledge_base" in agent.last_tool_calls
    assert "每年七月" in answer
    assert "02_薪酬管理制度.md" in answer
    assert "DOC-718E7FF3DE1E" in answer
    assert "字符" in answer
