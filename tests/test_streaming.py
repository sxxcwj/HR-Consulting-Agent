"""Streaming Responses API behavior without real network calls."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from types import SimpleNamespace
from typing import Any

import pytest
from openai.types.responses import ResponseTextDeltaEvent

from src.agent import (
    AgentError,
    HRConsultant,
    REGISTERED_TOOLS,
    ResponseFormatError,
    STREAMING_PARSE_FALLBACK_TOOLS,
)
from src.main import run

from .conftest import FakeClient, VALID_ANALYSIS


def _delta(text: str, sequence_number: int) -> ResponseTextDeltaEvent:
    return ResponseTextDeltaEvent(
        content_index=0,
        delta=text,
        item_id="msg_stream",
        logprobs=[],
        output_index=0,
        sequence_number=sequence_number,
        type="response.output_text.delta",
    )


def _text_stream(text: str) -> tuple[list[Any], SimpleNamespace]:
    split = max(1, len(text) // 4)
    chunks = [text[index : index + split] for index in range(0, len(text), split)]
    events: list[Any] = [SimpleNamespace(type="response.created")]
    events.extend(_delta(chunk, index + 1) for index, chunk in enumerate(chunks))
    events.append(SimpleNamespace(type="response.completed"))
    return events, SimpleNamespace(output_text=text, output=[])


class _FakeResponseStream:
    def __init__(self, events: Sequence[Any], final_response: Any) -> None:
        self.events = list(events)
        self.final_response = final_response
        self.consumed = 0

    def __iter__(self) -> Iterator[Any]:
        for event in self.events:
            self.consumed += 1
            yield event

    def get_final_response(self) -> Any:
        assert self.consumed == len(self.events), "stream must be fully consumed"
        return self.final_response


class _FakeStreamManager:
    def __init__(self, stream: _FakeResponseStream) -> None:
        self.stream = stream

    def __enter__(self) -> _FakeResponseStream:
        return self.stream

    def __exit__(self, *_: object) -> None:
        return None


class _FakeStreamingResponses:
    def __init__(
        self,
        streams: Sequence[tuple[Sequence[Any], Any] | Exception],
    ) -> None:
        self.streams = list(streams)
        self.calls: list[dict[str, Any]] = []

    def stream(self, **kwargs: Any) -> _FakeStreamManager:
        self.calls.append(kwargs)
        if not self.streams:
            raise AssertionError("unexpected streaming API call")
        item = self.streams.pop(0)
        if isinstance(item, Exception):
            raise item
        events, final_response = item
        return _FakeStreamManager(_FakeResponseStream(events, final_response))


class _FakeStreamingClient:
    def __init__(self, streams: Sequence[tuple[Sequence[Any], Any] | Exception]) -> None:
        self.responses = _FakeStreamingResponses(streams)


def _function_call(arguments: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        output_text="",
        output=[
            {
                "type": "function_call",
                "name": "calculate_turnover_rate",
                "call_id": "call_turnover_stream",
                "arguments": json.dumps(arguments),
            }
        ],
    )


def test_stream_repair_keeps_evidence_without_reexecuting_tools() -> None:
    tool_response = _function_call({"leavers": 20, "average_headcount": 200})
    client = _FakeStreamingClient(
        [([], tool_response), _text_stream("坏格式"), _text_stream(VALID_ANALYSIS)]
    )
    agent = HRConsultant(client=client)  # type: ignore[arg-type]
    chunks: list[str] = []
    answer = agent.ask_streamed(
        "平均200人，离职20人，请计算离职率", on_text_delta=chunks.append
    )
    assert answer == VALID_ANALYSIS.strip()
    repair = client.responses.calls[2]
    assert repair["tools"] == []
    outputs = [
        item for item in repair["input"] if item.get("type") == "function_call_output"
    ]
    assert json.loads(outputs[0]["output"])["turnover_rate"] == 10
    assert agent.last_tool_calls == ["calculate_turnover_rate"]
    assert "".join(chunks) == agent.last_final_output


def test_stream_repair_rejects_persistent_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    writes: list[object] = []
    monkeypatch.setattr("src.agent.save_memory", lambda **kwargs: writes.append(kwargs))
    call = {
        "type": "function_call",
        "name": "save_memory",
        "call_id": "call_write",
        "arguments": '{"category":"preference","content":"不应保存"}',
    }
    client = _FakeStreamingClient(
        [_text_stream("坏格式"), ([], SimpleNamespace(output=[call]))]
    )
    agent = HRConsultant(client=client)  # type: ignore[arg-type]
    chunks: list[str] = []
    with pytest.raises(ResponseFormatError, match="格式修复阶段不允许调用工具"):
        agent.ask_streamed("人员流失怎么办？", on_text_delta=chunks.append)
    assert writes == []
    assert chunks == []
    assert agent.history == []
    assert agent.last_final_output is None


def test_stream_json_fallback_exhaustion_is_safe_and_retryable() -> None:
    client = _FakeStreamingClient(
        [
            json.JSONDecodeError("private malformed payload", "{", 1),
            json.JSONDecodeError("private malformed payload", "{", 1),
            _text_stream(VALID_ANALYSIS),
        ]
    )
    agent = HRConsultant(client=client)  # type: ignore[arg-type]
    chunks: list[str] = []
    with pytest.raises(AgentError, match="无法解析") as captured:
        agent.ask_streamed("绩效目标不清晰怎么办？", on_text_delta=chunks.append)
    assert "private" not in str(captured.value)
    assert chunks == []
    assert agent.history == []
    answer = agent.ask_streamed("重试", on_text_delta=chunks.append)
    assert answer == VALID_ANALYSIS.strip()


def test_stream_repair_json_fallback_never_reenables_tools() -> None:
    client = _FakeStreamingClient(
        [
            _text_stream("坏格式"), json.JSONDecodeError("bad json", "{", 1),
            _text_stream(VALID_ANALYSIS),
        ]
    )
    agent = HRConsultant(client=client)  # type: ignore[arg-type]
    answer = agent.ask_streamed("绩效目标不清晰怎么办？", on_text_delta=lambda _: None)
    assert answer == VALID_ANALYSIS.strip()
    assert all(call["tools"] == [] for call in client.responses.calls[1:])


def test_ordinary_hr_question_streams_only_text_deltas() -> None:
    events, final_response = _text_stream(VALID_ANALYSIS)
    client = _FakeStreamingClient([(events, final_response)])
    agent = HRConsultant(client=client)  # type: ignore[arg-type]
    chunks: list[str] = []

    answer = agent.ask_streamed(
        "绩效目标不清晰怎么办？",
        on_text_delta=chunks.append,
    )

    assert "".join(chunks) == VALID_ANALYSIS.strip()
    assert answer == VALID_ANALYSIS.strip()
    assert not any("response." in chunk for chunk in chunks)
    assert agent.last_tool_calls == []


def test_streaming_tool_call_completes_and_hides_tool_events() -> None:
    tool_response = _function_call(
        {
            "leavers": 30,
            "average_headcount": None,
            "starting_headcount": 200,
            "ending_headcount": 180,
        }
    )
    events, final_response = _text_stream(VALID_ANALYSIS)
    client = _FakeStreamingClient([([], tool_response), (events, final_response)])
    agent = HRConsultant(client=client)  # type: ignore[arg-type]
    chunks: list[str] = []

    answer = agent.ask_streamed(
        "公司年初200人，年末180人，全年离职30人，离职率是多少？",
        on_text_delta=chunks.append,
    )

    assert answer == VALID_ANALYSIS.strip()
    assert "".join(chunks) == answer
    assert agent.last_tool_calls == ["calculate_turnover_rate"]
    tool_result = json.loads(client.responses.calls[1]["input"][-1]["output"])
    assert tool_result["turnover_rate"] == 15.79
    assert "call_turnover_stream" not in "".join(chunks)


def test_tool_round_planning_text_is_consumed_but_not_emitted() -> None:
    planning_text = "我先调用工具核实人数，再给出最终分析。"
    planning_events, _ = _text_stream(planning_text)
    tool_response = _function_call(
        {
            "leavers": 30,
            "average_headcount": None,
            "starting_headcount": 200,
            "ending_headcount": 180,
        }
    )
    tool_response.output_text = planning_text
    final_events, final_response = _text_stream(VALID_ANALYSIS)
    client = _FakeStreamingClient(
        [(planning_events, tool_response), (final_events, final_response)]
    )
    agent = HRConsultant(client=client)  # type: ignore[arg-type]
    chunks: list[str] = []

    answer = agent.ask_streamed(
        "公司年初200人，年末180人，全年离职30人，离职率是多少？",
        on_text_delta=chunks.append,
    )

    assert answer == VALID_ANALYSIS.strip()
    assert "".join(chunks) == answer
    assert planning_text not in "".join(chunks)
    assert agent.last_tool_calls == ["calculate_turnover_rate"]


def test_malformed_stream_is_repaired_before_any_text_is_emitted() -> None:
    malformed = "DATA FACT：工具结果如下。\n\n- 多余前言。\n\n" + VALID_ANALYSIS
    malformed_events, malformed_response = _text_stream(malformed)
    repaired_events, repaired_response = _text_stream(VALID_ANALYSIS)
    client = _FakeStreamingClient(
        [
            (malformed_events, malformed_response),
            (repaired_events, repaired_response),
        ]
    )
    agent = HRConsultant(client=client)  # type: ignore[arg-type]
    chunks: list[str] = []

    answer = agent.ask_streamed("离职率是多少？", on_text_delta=chunks.append)

    assert answer == VALID_ANALYSIS.strip()
    assert "".join(chunks) == answer
    assert "多余前言" not in "".join(chunks)
    assert len(client.responses.calls) == 2
    assert agent.last_response is repaired_response
    assert agent.history[-1]["content"] == answer
    assert client.responses.calls[1]["tools"] == []


def test_repeated_malformed_stream_is_not_emitted_or_committed() -> None:
    first_events, first_response = _text_stream("第一次坏格式")
    second_events, second_response = _text_stream("第二次仍然坏格式")
    client = _FakeStreamingClient(
        [(first_events, first_response), (second_events, second_response)]
    )
    agent = HRConsultant(client=client)  # type: ignore[arg-type]
    chunks: list[str] = []

    with pytest.raises(ResponseFormatError):
        agent.ask_streamed("招聘困难怎么办？", on_text_delta=chunks.append)

    assert chunks == []
    assert agent.history == []


def test_strict_stream_argument_parse_error_retries_with_manual_validation() -> None:
    events, final_response = _text_stream(VALID_ANALYSIS)
    client = _FakeStreamingClient(
        [json.JSONDecodeError("bad tool json", "{", 1), (events, final_response)]
    )
    agent = HRConsultant(client=client)  # type: ignore[arg-type]
    chunks: list[str] = []

    answer = agent.ask_streamed("招聘困难怎么办？", on_text_delta=chunks.append)

    assert answer == VALID_ANALYSIS.strip()
    assert "".join(chunks) == answer
    assert client.responses.calls[0]["tools"] == REGISTERED_TOOLS
    assert client.responses.calls[1]["tools"] == STREAMING_PARSE_FALLBACK_TOOLS
    assert all(tool["strict"] is False for tool in client.responses.calls[1]["tools"])


def test_tool_validation_error_is_returned_to_model_without_breaking_stream() -> None:
    tool_response = _function_call(
        {
            "leavers": 30,
            "average_headcount": None,
            "starting_headcount": None,
            "ending_headcount": None,
        }
    )
    events, final_response = _text_stream(VALID_ANALYSIS)
    client = _FakeStreamingClient([([], tool_response), (events, final_response)])
    agent = HRConsultant(client=client)  # type: ignore[arg-type]

    answer = agent.ask_streamed("今年离职30人，离职率是多少？", on_text_delta=lambda _: None)

    tool_result = json.loads(client.responses.calls[1]["input"][-1]["output"])
    assert "缺少必要人数" in tool_result["error"]
    assert answer == VALID_ANALYSIS.strip()


def test_streamed_and_non_streamed_final_content_match() -> None:
    non_streamed = HRConsultant(client=FakeClient([VALID_ANALYSIS]))  # type: ignore[arg-type]
    expected = non_streamed.ask("招聘困难怎么办？")
    events, final_response = _text_stream(VALID_ANALYSIS)
    streamed = HRConsultant(client=_FakeStreamingClient([(events, final_response)]))  # type: ignore[arg-type]

    actual = streamed.ask_streamed("招聘困难怎么办？", on_text_delta=lambda _: None)

    assert actual == expected


def test_final_response_and_final_output_remain_available_after_stream() -> None:
    events, final_response = _text_stream(VALID_ANALYSIS)
    agent = HRConsultant(client=_FakeStreamingClient([(events, final_response)]))  # type: ignore[arg-type]

    answer = agent.ask_streamed("员工关系如何改善？", on_text_delta=lambda _: None)

    assert agent.last_response is final_response
    assert agent.last_final_output == answer
    assert agent.history[-1]["content"] == answer


def test_internal_output_prefix_is_not_shown_to_terminal() -> None:
    raw = "DATA_ANALYSIS:已根据工具结果完成描述性统计。"
    events, final_response = _text_stream(raw)
    agent = HRConsultant(client=_FakeStreamingClient([(events, final_response)]))  # type: ignore[arg-type]
    chunks: list[str] = []

    answer = agent.ask_streamed("请统计员工人数。", on_text_delta=chunks.append)

    assert answer == "已根据工具结果完成描述性统计。"
    assert "".join(chunks) == answer
    assert "DATA_ANALYSIS" not in "".join(chunks)


def test_cli_reports_stream_failure_without_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FailingStreamingAgent:
        def ask_streamed(self, _: str, *, on_text_delta) -> str:
            on_text_delta("# 问题判断")
            raise AgentError("secret stream detail")

    entries = iter(["员工迟到怎么办？", "退出"])
    lines: list[str] = []
    chunks: list[str] = []

    result = run(
        input_fn=lambda _: next(entries),
        output_fn=lines.append,
        stream_output_fn=chunks.append,
        agent_factory=FailingStreamingAgent,  # type: ignore[arg-type]
    )

    assert result == 0
    assert chunks == ["# 问题判断"]
    assert lines == ["", "会话已结束。"]
    error = capsys.readouterr().err
    assert "本次生成过程中出现错误" in error
    assert "secret stream detail" not in error
    assert "Traceback" not in error
