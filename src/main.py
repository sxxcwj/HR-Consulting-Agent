"""Terminal interface for HR Consultant V0.9."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

from .agent import AgentError, HRConsultant


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
    env_path = path or Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(dotenv_path=env_path, override=False)


def run(
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    agent_factory: Callable[[], HRConsultant] = HRConsultant,
) -> int:
    """Run a conversation without writing its history to disk."""
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

        try:
            answer = agent.ask(question)
        except KeyboardInterrupt:
            output_fn("会话已结束。")
            return 0
        except AgentError as exc:
            print(f"错误：{exc}", file=sys.stderr)
            continue
        except Exception:
            # Keep internal exception details and credentials out of user output.
            print("错误：发生未预期故障，本次问题未得到分析。", file=sys.stderr)
            return 1

        output_fn(answer)
        first_turn = False


if __name__ == "__main__":
    load_local_environment()
    raise SystemExit(run())
