"""API setup and request behavior without network calls."""

import pytest

from src.agent import (
    DEFAULT_MODEL,
    DEEPSEEK_BASE_URL,
    REGISTERED_TOOLS,
    AgentError,
    HRConsultant,
)

from .conftest import FakeClient


def test_key_is_required_without_injected_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "other-provider-placeholder")
    with pytest.raises(AgentError, match="DEEPSEEK_API_KEY"):
        HRConsultant()


def test_deepseek_client_uses_dedicated_key_and_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-key")
    agent = HRConsultant()

    assert agent.model == DEFAULT_MODEL
    assert str(agent.client.base_url).rstrip("/") == DEEPSEEK_BASE_URL


def test_request_uses_official_responses_shape(valid_analysis: str) -> None:
    fake = FakeClient([valid_analysis])
    agent = HRConsultant(client=fake, model="deepseek-flash")  # type: ignore[arg-type]

    answer = agent.ask("绩效目标不清晰怎么办？")

    assert answer == valid_analysis.strip()
    call = fake.responses.calls[0]
    assert call["model"] == "deepseek-flash"
    assert "store" not in call
    assert call["input"] == [{"role": "user", "content": "绩效目标不清晰怎么办？"}]
    assert "HR Consultant" in call["instructions"]
    assert call["tools"] == REGISTERED_TOOLS


def test_failed_request_does_not_pollute_history(valid_analysis: str) -> None:
    fake = FakeClient([RuntimeError("unexpected"), valid_analysis])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError):
        agent.ask("第一个问题")
    assert agent.history == []

    agent.ask("第二个问题")
    assert fake.responses.calls[1]["input"] == [
        {"role": "user", "content": "第二个问题"}
    ]
