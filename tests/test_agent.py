"""Conversation state and format recovery."""

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
