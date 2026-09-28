"""Agent orchestration tests for V0.9 report generation."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.agent import HRConsultant, REGISTERED_TOOLS
from src.prompts import AGENT_INSTRUCTIONS

from .conftest import FakeClient, VALID_ANALYSIS
from .test_report_generator import _draft


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


def test_agent_generates_report_only_after_explicit_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.agent.generate_hr_report",
        lambda **kwargs: {
            "success": True,
            "status": "generated",
            "report_id": "RPT-TEST",
            "file_path": "/tmp/RPT-TEST.md",
            "format": "markdown",
            "draft": True,
        },
    )
    fake = FakeClient(
        [
            _call("generate_hr_report", "report1", _draft()),
            "REPORT:报告草稿已生成：RPT-TEST，Markdown 文件位于 /tmp/RPT-TEST.md。",
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    answer = agent.ask("请根据我刚才提供的销售离职情况生成一份报告。")

    assert agent.last_tool_calls == ["generate_hr_report"]
    assert "RPT-TEST" in answer
    assert any(tool["name"] == "generate_hr_report" for tool in REGISTERED_TOOLS)


def test_normal_hr_question_does_not_generate_report() -> None:
    agent = HRConsultant(client=FakeClient([VALID_ANALYSIS]))  # type: ignore[arg-type]
    agent.ask("销售人员离职增加可能有哪些原因？")
    assert "generate_hr_report" not in agent.last_tool_calls


def test_agent_reads_project_before_generating_project_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.agent.get_project_state",
        lambda **kwargs: {
            "success": True,
            "project": {
                "project_id": "PRJ-TEST",
                "name": "销售离职诊断",
                "confirmed_facts": ["销售离职人数近期增加"],
                "open_questions": ["平均销售人数是多少"],
            },
        },
    )
    monkeypatch.setattr(
        "src.agent.generate_hr_report",
        lambda **kwargs: {
            "success": True,
            "status": "generated",
            "report_id": "RPT-PROJECT",
            "file_path": "/tmp/RPT-PROJECT.md",
            "format": "markdown",
            "draft": True,
        },
    )
    draft = _draft(
        evidence=["PROJECT_CONTEXT：销售离职人数近期增加。"],
        source_references=[
            {
                "source_type": "project_state",
                "source_id": "PRJ-TEST",
                "description": "当前项目中用户明确保存的事实与待补信息",
            }
        ],
    )
    fake = FakeClient(
        [
            _call("get_project_state", "state1", {"project_id": None}),
            _call("generate_hr_report", "report1", draft),
            "REPORT:已基于实际读取的项目状态生成 RPT-PROJECT：/tmp/RPT-PROJECT.md。",
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    answer = agent.ask("请基于当前项目生成报告。")

    assert agent.last_tool_calls == ["get_project_state", "generate_hr_report"]
    assert "RPT-PROJECT" in answer


def test_report_tool_error_is_not_reported_as_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.agent.generate_hr_report",
        lambda **kwargs: {
            "success": False,
            "error": {
                "code": "sensitive_report_content",
                "message": "报告不保存密钥或员工级敏感信息，请先删除或匿名化。",
            },
        },
    )
    fake = FakeClient(
        [
            _call("generate_hr_report", "report1", _draft()),
            "REPORT:报告未生成：内容包含敏感信息，请先匿名化；当前没有可用文件路径。",
        ]
    )
    answer = HRConsultant(client=fake).ask("请生成报告。")  # type: ignore[arg-type]
    assert "未生成" in answer
    assert "没有可用文件路径" in answer


def test_report_instructions_preserve_evidence_and_format_boundaries() -> None:
    assert "只有用户明确要求“生成报告”" in AGENT_INSTRUCTIONS
    assert "只校验、排版和保存 Markdown 草稿" in AGENT_INSTRUCTIONS
    assert "已知事实必须对应 source_references" in AGENT_INSTRUCTIONS
    assert "不自动写回 State 或 Memory" in AGENT_INSTRUCTIONS
    assert "不声称生成 Word、PDF、HTML、PPT" in AGENT_INSTRUCTIONS
