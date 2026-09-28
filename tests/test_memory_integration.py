"""Agent orchestration tests for explicit V0.8 Memory."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.agent import HRConsultant, REGISTERED_TOOLS
from src.prompts import AGENT_INSTRUCTIONS

from .conftest import FakeClient, VALID_ANALYSIS


def _call(name: str, call_id: str, arguments: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        output_text="",
        output=[
            {
                "type": "function_call",
                "name": name,
                "call_id": call_id,
                "arguments": json.dumps(arguments, ensure_ascii=False),
            }
        ],
    )


def test_agent_saves_memory_only_after_explicit_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.agent.save_memory",
        lambda **kwargs: {
            "success": True,
            "status": "saved",
            "memory": {
                "memory_id": "MEM-TEST",
                "category": kwargs["category"],
                "content": kwargs["content"],
                "updated_at": "2026-09-28T00:00:00+00:00",
            },
        },
    )
    fake = FakeClient(
        [
            _call(
                "save_memory",
                "save1",
                {"category": "preference", "content": "回答默认使用中文"},
            ),
            "MEMORY:已保存长期偏好 MEM-TEST：回答默认使用中文。",
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    answer = agent.ask("请记住：回答默认使用中文。")

    assert agent.last_tool_calls == ["save_memory"]
    assert "MEM-TEST" in answer
    assert any(tool["name"] == "save_memory" for tool in REGISTERED_TOOLS)


def test_agent_searches_before_claiming_it_remembers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.agent.search_memories",
        lambda **kwargs: {
            "success": True,
            "search_method": "keyword",
            "count": 1,
            "memories": [
                {
                    "memory_id": "MEM-CALENDAR",
                    "category": "organization",
                    "content": "公司考勤周期按自然月计算",
                    "status": "active",
                    "updated_at": "2026-09-20T00:00:00+00:00",
                    "match_score": 2,
                }
            ],
        },
    )
    fake = FakeClient(
        [
            _call(
                "search_memories",
                "search1",
                {"query": "考勤口径", "category": None, "limit": 5},
            ),
            (
                "MEMORY:MEMORY_CONTEXT：此前保存的考勤口径为按自然月计算"
                "（MEM-CALENDAR，更新于2026-09-20）。该口径可能变化，请确认目前仍有效。"
            ),
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    answer = agent.ask("你记得我们公司的考勤口径吗？")

    assert agent.last_tool_calls == ["search_memories"]
    assert "MEMORY_CONTEXT" in answer
    assert "MEM-CALENDAR" in answer
    assert "仍有效" in answer


def test_normal_hr_question_does_not_write_or_read_memory() -> None:
    agent = HRConsultant(client=FakeClient([VALID_ANALYSIS]))  # type: ignore[arg-type]
    agent.ask("销售人员离职增加可能有哪些原因？")
    assert agent.last_tool_calls == []


def test_memory_search_no_result_is_not_fabricated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.agent.search_memories",
        lambda **kwargs: {
            "success": True,
            "search_method": "keyword",
            "count": 0,
            "memories": [],
        },
    )
    fake = FakeClient(
        [
            _call(
                "search_memories",
                "search1",
                {"query": "晋升周期", "category": None, "limit": 5},
            ),
            "MEMORY:没有找到与“晋升周期”匹配的已保存 Memory，我不能凭印象补写。",
        ]
    )
    answer = HRConsultant(client=fake).ask("你记得我们的晋升周期吗？")  # type: ignore[arg-type]
    assert "没有找到" in answer
    assert "不能凭印象" in answer


def test_memory_tool_error_is_not_reported_as_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.agent.save_memory",
        lambda **kwargs: {
            "success": False,
            "error": {
                "code": "sensitive_memory_content",
                "message": "Memory 不保存密钥或员工级敏感信息，请先删除或匿名化。",
            },
        },
    )
    fake = FakeClient(
        [
            _call(
                "save_memory",
                "save1",
                {"category": "organization", "content": "员工手机号：13812345678"},
            ),
            "MEMORY:未保存该内容，因为包含员工级敏感信息；请先匿名化。",
        ]
    )
    answer = HRConsultant(client=fake).ask("请记住员工手机号13812345678。")  # type: ignore[arg-type]
    assert "未保存" in answer


def test_agent_forgets_only_explicit_memory_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.agent.forget_memory",
        lambda **kwargs: {
            "success": True,
            "status": "forgotten",
            "memory_id": kwargs["memory_id"],
            "deleted": True,
        },
    )
    fake = FakeClient(
        [
            _call("forget_memory", "forget1", {"memory_id": "MEM-TEST"}),
            "MEMORY:已彻底遗忘 MEM-TEST，该记录已从本地 Memory 删除。",
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    answer = agent.ask("请彻底忘记记忆 MEM-TEST。")
    assert agent.last_tool_calls == ["forget_memory"]
    assert "已彻底遗忘" in answer


def test_memory_instructions_are_explicit_source_aware_and_private() -> None:
    assert "普通 HR 问答、项目 State、Excel、文件读取和 RAG 绝对不能自动生成 Memory" in AGENT_INSTRUCTIONS
    assert "MEMORY_CONTEXT" in AGENT_INSTRUCTIONS
    assert "memory_id 和 updated_at" in AGENT_INSTRUCTIONS
    assert "关键词检索不是语义搜索" in AGENT_INSTRUCTIONS
    assert "API Key、密码、令牌" in AGENT_INSTRUCTIONS
