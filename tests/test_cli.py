"""Terminal interaction with a fake Agent."""

from collections.abc import Iterator
import os
from pathlib import Path

from pytest import MonkeyPatch

from src.main import (
    AGENT_OUTPUT_COLOR,
    ANSI_RESET,
    INITIAL_PROMPT,
    USER_INPUT_COLOR,
    load_local_environment,
    run,
)


class StubAgent:
    def __init__(self) -> None:
        self.questions: list[str] = []

    def ask(self, question: str) -> str:
        self.questions.append(question)
        return "已分析"


def test_two_turns_and_exit() -> None:
    entries: Iterator[str] = iter(["绩效目标不清晰", "补充：没有书面目标", "退出"])
    prompts: list[str] = []
    outputs: list[str] = []
    stub = StubAgent()

    def input_fn(prompt: str) -> str:
        prompts.append(prompt)
        return next(entries)

    result = run(
        input_fn=input_fn,
        output_fn=outputs.append,
        agent_factory=lambda: stub,  # type: ignore[arg-type]
    )

    assert result == 0
    assert prompts[0] == INITIAL_PROMPT
    assert stub.questions == ["绩效目标不清晰", "补充：没有书面目标"]
    assert outputs == ["已分析", "已分析", "会话已结束。"]


def test_empty_input_is_retryable() -> None:
    entries = iter([" ", "exit"])
    outputs: list[str] = []

    result = run(
        input_fn=lambda _: next(entries),
        output_fn=outputs.append,
        agent_factory=StubAgent,  # type: ignore[arg-type]
    )

    assert result == 0
    assert "请输入具体的企业人力资源管理问题。" in outputs


def test_end_of_input_exits() -> None:
    outputs: list[str] = []

    def end(_: str) -> str:
        raise EOFError

    assert run(input_fn=end, output_fn=outputs.append, agent_factory=StubAgent) == 0  # type: ignore[arg-type]
    assert outputs == ["会话已结束。"]


def test_interrupt_during_agent_request_exits_cleanly() -> None:
    class InterruptedAgent:
        def ask(self, _: str) -> str:
            raise KeyboardInterrupt

    outputs: list[str] = []
    result = run(
        input_fn=lambda _: "绩效目标不清晰怎么办？",
        output_fn=outputs.append,
        agent_factory=InterruptedAgent,  # type: ignore[arg-type]
    )

    assert result == 0
    assert outputs == ["会话已结束。"]


def test_unexpected_factory_failure_is_reported_without_traceback(
    capsys,
) -> None:
    def failing_factory() -> StubAgent:
        raise RuntimeError("secret internal detail")

    result = run(
        input_fn=lambda _: "绩效目标不清晰怎么办？",
        agent_factory=failing_factory,  # type: ignore[arg-type]
    )

    assert result == 1
    error = capsys.readouterr().err
    assert "Agent 初始化失败" in error
    assert "secret internal detail" not in error


def test_greeting_does_not_require_api_client() -> None:
    entries = iter(["你好", "退出"])
    outputs: list[str] = []

    def forbidden_factory() -> StubAgent:
        raise AssertionError("greeting must not call the API")

    assert run(
        input_fn=lambda _: next(entries),
        output_fn=outputs.append,
        agent_factory=forbidden_factory,  # type: ignore[arg-type]
    ) == 0
    assert "HR Consultant" in outputs[0]


def test_terminal_colors_distinguish_user_input_and_agent_output() -> None:
    class StreamingStub:
        def ask_streamed(self, _: str, *, on_text_delta) -> str:
            on_text_delta("Agent回答")
            return "Agent回答"

    entries = iter(["用户问题", "退出"])
    prompts: list[str] = []
    rendered: list[str] = []
    lines: list[str] = []

    def input_fn(prompt: str) -> str:
        prompts.append(prompt)
        return next(entries)

    result = run(
        input_fn=input_fn,
        output_fn=lines.append,
        stream_output_fn=rendered.append,
        agent_factory=StreamingStub,  # type: ignore[arg-type]
        color_output=True,
    )

    assert result == 0
    assert prompts[0] == f"{USER_INPUT_COLOR}{INITIAL_PROMPT}"
    terminal_text = "".join(rendered)
    assert f"{AGENT_OUTPUT_COLOR}Agent回答{ANSI_RESET}" in terminal_text
    assert terminal_text.count(USER_INPUT_COLOR) == 0
    assert ANSI_RESET in terminal_text
    assert lines == ["", "会话已结束。"]


def test_local_env_loads_without_overriding_real_environment(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Keep the test isolated from the user's real .env and credentials.
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=test-only-key\n", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "already-set")

    load_local_environment(env_file)

    assert os.getenv("DEEPSEEK_API_KEY") == "already-set"


def test_local_env_provides_missing_key(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=test-only-key\n", encoding="utf-8")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    try:
        load_local_environment(env_file)
        assert os.getenv("DEEPSEEK_API_KEY") == "test-only-key"
    finally:
        os.environ.pop("DEEPSEEK_API_KEY", None)
