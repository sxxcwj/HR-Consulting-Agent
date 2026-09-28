"""Tests for V0.8 public memory functions and strict tool schemas."""

from __future__ import annotations

import pytest

from src.memory import MEMORY_TOOLS, MemoryStore
from src.memory import tools as memory_tools


@pytest.fixture
def isolated_store(tmp_path, monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    store = MemoryStore(tmp_path / "state")
    monkeypatch.setattr(memory_tools, "_DEFAULT_STORE", store)
    return store


def test_all_seven_tools_are_registered() -> None:
    names = [tool["name"] for tool in MEMORY_TOOLS]
    assert names == [
        "save_memory",
        "list_memories",
        "get_memory",
        "search_memories",
        "update_memory",
        "archive_memory",
        "forget_memory",
    ]
    assert all(tool["strict"] is True for tool in MEMORY_TOOLS)


def test_public_functions_complete_memory_lifecycle(isolated_store) -> None:
    saved = memory_tools.save_memory("preference", "回答默认使用中文")
    memory_id = saved["memory"]["memory_id"]
    listed = memory_tools.list_memories(category=None, include_archived=False)
    searched = memory_tools.search_memories("中文", category=None, limit=5)
    updated = memory_tools.update_memory(
        memory_id, content="回答默认使用简洁中文"
    )
    fetched = memory_tools.get_memory(memory_id)
    archived = memory_tools.archive_memory(memory_id)
    forgotten = memory_tools.forget_memory(memory_id)

    assert listed["count"] == 1
    assert searched["memories"][0]["memory_id"] == memory_id
    assert updated["success"] is True
    assert fetched["memory"]["content"] == "回答默认使用简洁中文"
    assert archived["status"] == "archived"
    assert forgotten["deleted"] is True


def test_strict_schemas_require_all_properties() -> None:
    for tool in MEMORY_TOOLS:
        schema = tool["parameters"]
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])


def test_tool_descriptions_preserve_explicit_write_boundary() -> None:
    save = next(item for item in MEMORY_TOOLS if item["name"] == "save_memory")
    forget = next(item for item in MEMORY_TOOLS if item["name"] == "forget_memory")
    search = next(item for item in MEMORY_TOOLS if item["name"] == "search_memories")
    assert "明确" in save["description"]
    assert "唯一 memory_id" in forget["description"]
    assert "不是语义搜索" in search["description"]
