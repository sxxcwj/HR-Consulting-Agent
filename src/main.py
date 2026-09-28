"""Terminal interface for HR Consultant V1.0 release candidate."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

from .agent import AgentError, HRConsultant
from .config import APPLICATION_ROOT


logger = logging.getLogger(__name__)
INITIAL_PROMPT = "请输入企业人力资源管理问题："
FOLLOW_UP_PROMPT = "请继续补充信息（输入“退出”结束）："
EXIT_WORDS = {"退出", "exit", "quit", "q"}
SIMPLE_REPLIES = {
    "你好": "你好，我是 HR Consultant。请描述企业组织或人力资源管理问题。",
    "hello": "你好，我是 HR Consultant。请描述企业组织或人力资源管理问题。",
    "你能做什么": "我可以初步分析组织、绩效、薪酬和人才管理问题。请描述具体情况。",
}


def load_local_environment(path: Path | None = None) -> None:
    """Load an ignored local .env without overriding real environment variables."""
    env_path = path or APPLICATION_ROOT / ".env"
    load_dotenv(dotenv_path=env_path, override=False)


def run(
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    stream_output_fn: Callable[[str], None] | None = None,
    agent_factory: Callable[[], HRConsultant] = HRConsultant,
) -> int:
    """Run a conversation, streaming model text when the Agent supports it."""
    if stream_output_fn is None:
        stream_output_fn = lambda delta: print(delta, end="", flush=True)

    agent: HRConsultant | None = None
    first_turn = True
    while True:
        try:
            question = input_fn(INITIAL_PROMPT if first_turn else FOLLOW_UP_PROMPT)
        except (EOFError, KeyboardInterrupt):
            output_fn("会话已结束。")
            return 0

        question = question.strip()
        if question.lower() in EXIT_WORDS:
            output_fn("会话已结束。")
            return 0
        if not question:
            output_fn("请输入具体的企业人力资源管理问题。")
            continue
        if question.lower() in SIMPLE_REPLIES:
            output_fn(SIMPLE_REPLIES[question.lower()])
            continue

        if agent is None:
            try:
                agent = agent_factory()
            except AgentError as exc:
                print(f"错误：{exc}", file=sys.stderr)
                return 1
            except Exception:
                print("错误：Agent 初始化失败，请检查运行环境。", file=sys.stderr)
                return 1

        stream_started = False

        def emit_delta(delta: str) -> None:
            nonlocal stream_started
            if delta:
                stream_started = True
                stream_output_fn(delta)

        try:
            streamed_ask = getattr(agent, "ask_streamed", None)
            if callable(streamed_ask):
                streamed_ask(question, on_text_delta=emit_delta)
                if stream_started:
                    output_fn("")
            else:
                # Keep injected test doubles and programmatic callers compatible.
                answer = agent.ask(question)
                output_fn(answer)
        except KeyboardInterrupt:
            if stream_started:
                output_fn("")
            output_fn("会话已结束。")
            return 0
        except AgentError as exc:
            if stream_started:
                logger.debug("Streaming generation failed", exc_info=True)
                output_fn("")
                print("错误：本次生成过程中出现错误，请重新尝试。", file=sys.stderr)
            else:
                print(f"错误：{exc}", file=sys.stderr)
            continue
        except Exception:
            # Keep internal exception details and credentials out of user output.
            logger.debug("Unexpected Agent failure", exc_info=True)
            if stream_started:
                output_fn("")
                print("错误：本次生成过程中出现错误，请重新尝试。", file=sys.stderr)
            else:
                print("错误：发生未预期故障，本次问题未得到分析。", file=sys.stderr)
            return 1

        first_turn = False


def main() -> int:
    """Load local configuration and start the installable CLI."""
    load_local_environment()
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
