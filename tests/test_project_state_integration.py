"""Agent orchestration tests for explicit V0.7 project state."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.agent import HRConsultant, REGISTERED_TOOLS

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


def _update_arguments(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "project_id": None,
        "name": None,
        "objective": None,
        "current_stage": None,
        "organization_context": None,
        "add_confirmed_facts": None,
        "add_open_questions": None,
        "resolve_open_questions": None,
        "add_decisions": None,
        "selected_document_ids": None,
        "selected_data_files": None,
    }
    value.update(updates)
    return value


def test_agent_creates_project_only_after_explicit_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.agent.create_project_state",
        lambda **kwargs: {
            "success": True,
            "status": "created",
            "project": {
                "project_id": "PRJ-TEST",
                "name": kwargs["name"],
                "current_stage": "discovery",
            },
        },
    )
    fake = FakeClient(
        [
            _call(
                "create_project_state",
                "create1",
                {
                    "name": "销售离职诊断",
                    "objective": "分析销售离职增加",
                    "organization_context": {
                        "industry": None,
                        "employee_count": 200,
                        "location": None,
                        "development_stage": None,
                    },
                },
            ),
            "PROJECT_STATE:已创建并选中项目“销售离职诊断”（PRJ-TEST），当前阶段为 discovery。",
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    answer = agent.ask("请创建一个项目，叫销售离职诊断，目标是分析销售离职增加，公司200人。")

    assert agent.last_tool_calls == ["create_project_state"]
    assert "PRJ-TEST" in answer
    assert any(tool["name"] == "create_project_state" for tool in REGISTERED_TOOLS)


def test_agent_reads_current_project_before_continuing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.agent.get_project_state",
        lambda **kwargs: {
            "success": True,
            "project": {
                "project_id": "PRJ-TEST",
                "name": "销售离职诊断",
                "confirmed_facts": ["公司约200人"],
                "open_questions": ["销售平均人数"],
            },
            "evidence_note": "PROJECT_CONTEXT，不等于外部核验事实。",
        },
    )
    fake = FakeClient(
        [
            _call("get_project_state", "get1", {"project_id": None}),
            "PROJECT_STATE:当前项目为“销售离职诊断”（PRJ-TEST）。已确认项目输入：公司约200人；待补信息：销售平均人数。",
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    answer = agent.ask("继续当前项目，告诉我现在的状态。")
    assert agent.last_tool_calls == ["get_project_state"]
    assert "销售平均人数" in answer


def test_agent_updates_only_user_confirmed_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _update(**kwargs):
        captured.update(kwargs)
        return {"success": True, "status": "updated", "project": {"project_id": "PRJ-TEST"}}

    monkeypatch.setattr("src.agent.update_project_state", _update)
    fake = FakeClient(
        [
            _call(
                "update_project_state",
                "update1",
                _update_arguments(
                    add_confirmed_facts=["最近销售离职人数明显增加"],
                    add_open_questions=["统计期间平均销售人数是多少？"],
                ),
            ),
            "PROJECT_STATE:已保存用户确认的事实和待补问题，未保存任何原因假设。",
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    agent.ask("把“最近销售离职人数明显增加”保存为项目事实，并记录待补平均销售人数。")
    assert captured["add_confirmed_facts"] == ["最近销售离职人数明显增加"]
    assert agent.last_tool_calls == ["update_project_state"]


def test_normal_hr_question_does_not_write_state() -> None:
    fake = FakeClient([VALID_ANALYSIS])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    agent.ask("销售人员离职增加可能有哪些原因？")
    assert agent.last_tool_calls == []


def test_state_reference_does_not_fake_document_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.agent.get_project_state",
        lambda **kwargs: {
            "success": True,
            "project": {
                "project_id": "PRJ-TEST",
                "selected_document_ids": ["DOC-ABC"],
                "selected_data_files": [],
            },
        },
    )
    fake = FakeClient(
        [
            _call("get_project_state", "get1", {"project_id": None}),
            "PROJECT_STATE:当前项目引用了 DOC-ABC，但本轮尚未读取该文件，因此不能陈述文件内容。",
        ]
    )
    answer = HRConsultant(client=fake).ask("当前项目选了哪些制度？它写了什么？")  # type: ignore[arg-type]
    assert "尚未读取" in answer


def test_state_tool_error_is_not_reported_as_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.agent.update_project_state",
        lambda **kwargs: {
            "success": False,
            "error": {
                "code": "sensitive_state_content",
                "message": "项目 State 不保存员工级敏感信息，请先匿名化。",
            },
        },
    )
    fake = FakeClient(
        [
            _call(
                "update_project_state",
                "update1",
                _update_arguments(add_confirmed_facts=["员工手机号：13812345678"]),
            ),
            "PROJECT_STATE:未保存该内容，因为其中包含员工级敏感信息；请先匿名化。",
        ]
    )
    answer = HRConsultant(client=fake).ask("把员工手机号13812345678保存到当前项目。")  # type: ignore[arg-type]
    assert "未保存" in answer
