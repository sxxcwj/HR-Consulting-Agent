"""Conversation state and format recovery."""

import json
from types import SimpleNamespace

import pytest

from src.agent import HRConsultant, OUT_OF_SCOPE_MESSAGE, ResponseFormatError

from .conftest import FakeClient


def test_same_process_follow_up_reuses_only_successful_turns(valid_analysis: str) -> None:
    fake = FakeClient([valid_analysis, valid_analysis])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    agent.ask("公司绩效考核无效怎么办？")
    agent.ask("补充：各部门目标不一致。")

    second_input = fake.responses.calls[1]["input"]
    assert [item["role"] for item in second_input] == ["user", "assistant", "user"]
    assert second_input[-1]["content"] == "补充：各部门目标不一致。"


def test_one_format_repair_attempt(valid_analysis: str) -> None:
    fake = FakeClient(["结构不完整", valid_analysis])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    assert agent.ask("我们招聘困难怎么办？") == valid_analysis.strip()
    assert len(fake.responses.calls) == 2
    assert len(agent.history) == 2
    assert fake.responses.calls[1]["tools"] == []


def test_repeated_bad_format_is_not_committed() -> None:
    fake = FakeClient(["坏格式", "仍然坏格式"])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    with pytest.raises(ResponseFormatError):
        agent.ask("我们招聘困难怎么办？")
    assert agent.history == []


def test_out_of_scope_reply_is_brief_and_does_not_trigger_format_repair() -> None:
    fake = FakeClient([f"OUT_OF_SCOPE:{OUT_OF_SCOPE_MESSAGE}"])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    answer = agent.ask("讲个笑话")

    assert answer == OUT_OF_SCOPE_MESSAGE
    assert len(fake.responses.calls) == 1
    assert agent.history[-1] == {"role": "assistant", "content": answer}


def test_repair_keeps_original_tool_evidence(valid_analysis: str) -> None:
    call = {
        "type": "function_call",
        "name": "calculate_turnover_rate",
        "call_id": "call_evidence",
        "arguments": json.dumps({"leavers": 20, "average_headcount": 200}),
    }
    fake = FakeClient([SimpleNamespace(output=[call]), "坏格式", valid_analysis])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    assert agent.ask("20人离职，平均200人，离职率是多少？") == valid_analysis.strip()
    repair_input = fake.responses.calls[2]["input"]
    outputs = [item for item in repair_input if item.get("type") == "function_call_output"]
    assert len(outputs) == 1
    assert json.loads(outputs[0]["output"])["turnover_rate"] == 10
    assert fake.responses.calls[2]["tools"] == []
    assert agent.last_tool_calls == ["calculate_turnover_rate"]


def test_repair_cannot_execute_persistent_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    writes: list[object] = []
    monkeypatch.setattr("src.agent.create_project_state", lambda **kwargs: writes.append(kwargs))
    call = {
        "type": "function_call",
        "name": "create_project_state",
        "call_id": "call_write",
        "arguments": '{"name":"不应创建"}',
    }
    fake = FakeClient(["坏格式", SimpleNamespace(output=[call])])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    with pytest.raises(ResponseFormatError, match="格式修复阶段不允许调用工具"):
        agent.ask("人员流失怎么办？")
    assert writes == []
    assert agent.last_tool_calls == []
    assert agent.history == []
    assert agent.last_final_output is None


def test_repair_cannot_bypass_structure_with_routing_prefix() -> None:
    fake = FakeClient(["坏格式", "DATA_ANALYSIS:跳过五部分"])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    with pytest.raises(ResponseFormatError):
        agent.ask("人员流失怎么办？")
    assert agent.history == []
