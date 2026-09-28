"""Agent orchestration tests for V0.6 RAG tools."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.agent import HRConsultant, REGISTERED_TOOLS

from .conftest import FakeClient


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


def _rag_result() -> dict[str, object]:
    return {
        "success": True,
        "query": "年度调薪什么时候",
        "top_k": 3,
        "result_count": 1,
        "results": [
            {
                "rank": 1,
                "score": 0.91,
                "chunk_id": "CHK-1",
                "document_id": "DOC-SALARY",
                "file_name": "02_薪酬管理制度.md",
                "start": 120,
                "end": 220,
                "text": "公司原则上每年七月组织年度调薪评审。",
                "source": "02_薪酬管理制度.md (DOC-SALARY, 字符 120-220)",
            }
        ],
        "potential_version_conflicts": [],
        "evidence_note": "相似度仅用于排序。",
    }


def test_cross_document_request_calls_rag_and_cites_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.agent.search_knowledge_base", lambda **kwargs: _rag_result())
    fake = FakeClient(
        [
            _call(
                "search_knowledge_base",
                "rag1",
                {"query": "年度调薪什么时候", "top_k": 3, "document_ids": None},
            ),
            (
                "RAG_ANSWER:根据《02_薪酬管理制度.md》，公司原则上每年七月组织年度调薪评审。"
                "来源：02_薪酬管理制度.md（DOC-SALARY，字符120-220）。文件规定不等于实际执行。"
            ),
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    answer = agent.ask("公司制度里年度调薪是什么时候？")
    assert agent.last_tool_calls == ["search_knowledge_base"]
    assert "每年七月" in answer
    assert "DOC-SALARY" in answer
    assert any(tool["name"] == "search_knowledge_base" for tool in REGISTERED_TOOLS)


def test_top_k_request_is_no_longer_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.agent.search_knowledge_base", lambda **kwargs: _rag_result())
    fake = FakeClient(
        [
            _call(
                "search_knowledge_base",
                "rag1",
                {"query": "薪酬内容", "top_k": 5, "document_ids": None},
            ),
            "RAG_ANSWER:已返回实际检索片段，并逐项标注来源。",
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    answer = agent.ask("在所有文件中找最相关的5段薪酬内容。")
    assert answer.startswith("已返回实际检索片段")
    assert agent.last_tool_calls == ["search_knowledge_base"]


def test_agent_can_build_then_retry_search(monkeypatch: pytest.MonkeyPatch) -> None:
    search_results = iter(
        [
            {
                "success": False,
                "error": {"code": "index_not_ready", "message": "请先构建。"},
            },
            _rag_result(),
        ]
    )
    monkeypatch.setattr("src.agent.search_knowledge_base", lambda **kwargs: next(search_results))
    monkeypatch.setattr(
        "src.agent.build_knowledge_index",
        lambda **kwargs: {"success": True, "status": "indexed", "chunk_count": 10},
    )
    fake = FakeClient(
        [
            _call(
                "search_knowledge_base",
                "search1",
                {"query": "奖金", "top_k": 3, "document_ids": None},
            ),
            _call(
                "build_knowledge_index",
                "build1",
                {"chunk_size": None, "overlap": None},
            ),
            _call(
                "search_knowledge_base",
                "search2",
                {"query": "奖金", "top_k": 3, "document_ids": None},
            ),
            "RAG_ANSWER:索引建立后已重新检索，并返回实际文件来源。",
        ]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]
    agent.ask("所有制度里关于奖金有什么规定？")
    assert agent.last_tool_calls == [
        "search_knowledge_base",
        "build_knowledge_index",
        "search_knowledge_base",
    ]


def test_no_evidence_answer_does_not_invent_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.agent.search_knowledge_base",
        lambda **kwargs: {
            "success": True,
            "query": "每年必须涨薪10%",
            "result_count": 1,
            "results": [{"text": "年度调薪不承诺固定比例。", "source": "制度.md 字符0-20"}],
        },
    )
    fake = FakeClient(
        [
            _call(
                "search_knowledge_base",
                "rag1",
                {"query": "每年必须涨薪10%", "top_k": 5, "document_ids": None},
            ),
            "RAG_ANSWER:当前检索结果没有支持“每年必须涨薪10%”的依据；来源制度明确不承诺固定比例。",
        ]
    )
    answer = HRConsultant(client=fake).ask("公司是不是规定每年必须涨薪10%？")  # type: ignore[arg-type]
    assert "没有支持" in answer


def test_rag_errors_are_returned_to_model_without_fake_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.agent.search_knowledge_base",
        lambda **kwargs: {
            "success": False,
            "error": {"code": "embedding_error", "message": "本地模型无法加载。"},
        },
    )
    fake = FakeClient(
        [
            _call(
                "search_knowledge_base",
                "rag1",
                {"query": "奖金", "top_k": 5, "document_ids": None},
            ),
            "RAG_ANSWER:本地模型无法加载，因此本轮没有完成检索，也不能据此回答公司奖金规定。",
        ]
    )
    answer = HRConsultant(client=fake).ask("公司奖金规定是什么？")  # type: ignore[arg-type]
    assert "没有完成检索" in answer
