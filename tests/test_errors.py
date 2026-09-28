"""Visible failures without leaking sensitive values."""

import httpx
import pytest
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from src.agent import AgentError, HRConsultant
from src.main import run

from .conftest import FakeClient


def _http_error(status: int) -> APIStatusError:
    request = httpx.Request("POST", "https://api.deepseek.com/responses")
    response = httpx.Response(status, request=request)
    if status == 401:
        return AuthenticationError("secret detail", response=response, body=None)
    if status == 429:
        return RateLimitError("secret detail", response=response, body=None)
    return APIStatusError("secret detail", response=response, body=None)


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (401, "认证失败"),
        (402, "余额不足"),
        (429, "请求受限"),
        (400, "DEEPSEEK_MODEL"),
        (422, "请求参数"),
        (500, "错误状态 500"),
    ],
)
def test_api_errors_are_mapped_to_safe_messages(status: int, message: str) -> None:
    agent = HRConsultant(client=FakeClient([_http_error(status)]))  # type: ignore[arg-type]
    with pytest.raises(AgentError, match=message) as captured:
        agent.ask("企业绩效如何改善？")
    assert "secret detail" not in str(captured.value)
    assert agent.history == []


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (APITimeoutError(request=httpx.Request("POST", "https://api.deepseek.com/responses")), "超时"),
        (
            APIConnectionError(
                message="secret detail",
                request=httpx.Request("POST", "https://api.deepseek.com/responses"),
            ),
            "无法连接",
        ),
    ],
)
def test_network_errors_are_mapped(error: Exception, message: str) -> None:
    agent = HRConsultant(client=FakeClient([error]))  # type: ignore[arg-type]
    with pytest.raises(AgentError, match=message) as captured:
        agent.ask("企业绩效如何改善？")
    assert "secret detail" not in str(captured.value)


def test_cli_recovers_after_agent_error(capsys: pytest.CaptureFixture[str]) -> None:
    class FailingOnce:
        def __init__(self) -> None:
            self.calls = 0

        def ask(self, _: str) -> str:
            self.calls += 1
            if self.calls == 1:
                raise AgentError("网络暂不可用")
            return "分析完成"

    entries = iter(["第一个问题", "第二个问题", "退出"])
    outputs: list[str] = []
    agent = FailingOnce()

    result = run(
        input_fn=lambda _: next(entries),
        output_fn=outputs.append,
        agent_factory=lambda: agent,  # type: ignore[arg-type]
    )

    assert result == 0
    assert "网络暂不可用" in capsys.readouterr().err
    assert outputs == ["分析完成", "会话已结束。"]
