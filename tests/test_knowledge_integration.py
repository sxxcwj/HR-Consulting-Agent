"""Agent integration tests for V0.5 file knowledge behavior."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.agent import REGISTERED_TOOLS, HRConsultant
from src.knowledge import KnowledgeRegistry

from .conftest import FakeClient


def _function_call(name: str, call_id: str, arguments: dict[str, object]) -> SimpleNamespace:
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


def _latest_tool_output(fake: FakeClient) -> dict:
    return json.loads(fake.responses.calls[-1]["input"][-1]["output"])


def test_case_a_lists_registered_knowledge_documents() -> None:
    fake = FakeClient(
        [
            _function_call("list_knowledge_documents", "call_list", {}),
            "KNOWLEDGE_ANSWER:知识库包含 5 份虚构 HR 文件。",
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    answer = agent.ask("知识库有哪些文件？")
    output = _latest_tool_output(fake)

    assert output["success"] is True
    assert output["count"] == 5
    assert agent.last_tool_calls == ["list_knowledge_documents"]
    assert answer == "知识库包含 5 份虚构 HR 文件。"
    assert fake.responses.calls[0]["tools"] == REGISTERED_TOOLS


def test_agent_can_import_an_explicit_supported_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "培训制度.md"
    source.write_text("# 培训制度\n本文件为虚构测试。", encoding="utf-8")
    registry = KnowledgeRegistry(tmp_path / "knowledge")
    monkeypatch.setattr(
        "src.agent.register_document", lambda file_path: registry.register_file(file_path)
    )
    fake = FakeClient(
        [
            _function_call(
                "register_knowledge_document",
                "call_register",
                {"file_path": str(source)},
            ),
            "KNOWLEDGE_ANSWER:文件已成功解析并登记。",
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    answer = agent.ask(f"请把 {source} 导入企业知识库。")
    output = _latest_tool_output(fake)

    assert output["success"] is True
    assert output["status"] == "registered"
    assert output["document"]["file_name"] == "培训制度.md"
    assert agent.last_tool_calls == ["register_knowledge_document"]
    assert "成功" in answer


def test_case_b_reads_real_compensation_policy_before_answering() -> None:
    fake = FakeClient(
        [
            _function_call(
                "get_document_metadata",
                "call_meta",
                {"document_id": None, "file_name": "薪酬管理制度"},
            ),
            _function_call(
                "read_knowledge_document",
                "call_read",
                {
                    "document_id": None,
                    "file_name": "薪酬管理制度",
                    "start": None,
                    "end": None,
                },
            ),
            "KNOWLEDGE_ANSWER:根据《02_薪酬管理制度.md》，公司原则上每年七月组织一次年度调薪评审；文件同时说明这不代表实际已经执行。",
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    answer = agent.ask("根据薪酬管理制度，调薪周期是什么？")
    output = _latest_tool_output(fake)

    assert agent.last_tool_calls == ["get_document_metadata", "read_knowledge_document"]
    assert output["success"] is True
    assert "每年七月" in output["text"]
    assert output["source"]["file_name"] == "02_薪酬管理制度.md"
    assert "02_薪酬管理制度.md" in answer
    assert "每年七月" in answer


def test_case_c_does_not_accept_unsupported_ten_percent_claim() -> None:
    fake = FakeClient(
        [
            _function_call(
                "read_knowledge_document",
                "call_read",
                {
                    "document_id": None,
                    "file_name": "薪酬管理制度",
                    "start": None,
                    "end": None,
                },
            ),
            "KNOWLEDGE_ANSWER:根据《02_薪酬管理制度.md》，当前文件明确没有“员工每年必须涨薪10%”的规定，因此不能认同该说法。",
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    answer = agent.ask("我们公司规定员工每年必须涨薪10%，对吗？")
    output = _latest_tool_output(fake)

    assert "没有“员工每年必须涨薪 10%”的规定" in output["text"]
    assert "不能认同" in answer
    assert agent.last_tool_calls == ["read_knowledge_document"]


def test_case_d_employee_handbook_does_not_invent_quarterly_requirement() -> None:
    fake = FakeClient(
        [
            _function_call(
                "read_knowledge_document",
                "call_read",
                {
                    "document_id": None,
                    "file_name": "员工手册",
                    "start": None,
                    "end": None,
                },
            ),
            "KNOWLEDGE_ANSWER:根据《01_员工手册.md》，员工手册本身不规定每季度必须绩效面谈，具体频率应查看《绩效管理制度》。",
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    answer = agent.ask("员工手册要求每季度绩效面谈吗？")
    output = _latest_tool_output(fake)

    assert "不另行规定“每季度必须进行一次绩效面谈”" in output["text"]
    assert "01_员工手册.md" in answer
    assert "不规定" in answer

