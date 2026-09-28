"""Public V0.8 memory functions and Responses API tool schemas."""

from __future__ import annotations

from typing import Any

from .models import MEMORY_CATEGORIES
from .store import MemoryStore


_DEFAULT_STORE: MemoryStore | None = None
CATEGORY_SCHEMA = {"type": ["string", "null"], "enum": [*MEMORY_CATEGORIES, None]}


def _store() -> MemoryStore:
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = MemoryStore()
    return _DEFAULT_STORE


def save_memory(category: str, content: str) -> dict[str, Any]:
    return _store().save_memory(category=category, content=content)


def list_memories(
    *, category: str | None = None, include_archived: bool = False
) -> dict[str, Any]:
    return _store().list_memories(
        category=category, include_archived=include_archived
    )


def get_memory(memory_id: str) -> dict[str, Any]:
    return _store().get_memory(memory_id=memory_id)


def search_memories(
    query: str, *, category: str | None = None, limit: int = 5
) -> dict[str, Any]:
    return _store().search_memories(query=query, category=category, limit=limit)


def update_memory(
    memory_id: str,
    *,
    category: str | None = None,
    content: str | None = None,
) -> dict[str, Any]:
    return _store().update_memory(
        memory_id=memory_id, category=category, content=content
    )


def archive_memory(memory_id: str) -> dict[str, Any]:
    return _store().archive_memory(memory_id=memory_id)


def forget_memory(memory_id: str) -> dict[str, Any]:
    return _store().forget_memory(memory_id=memory_id)


SAVE_MEMORY_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "save_memory",
    "description": (
        "仅当用户明确要求长期记住一项稳定偏好、组织背景、术语或长期约束时使用。"
        "不要自动保存普通对话、项目过程、模型推断、工具结果或敏感信息。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": list(MEMORY_CATEGORIES)},
            "content": {"type": "string"},
        },
        "required": ["category", "content"],
        "additionalProperties": False,
    },
}

LIST_MEMORIES_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "list_memories",
    "description": "列出用户明确保存的长期 Memory；默认只列出 active 记录。",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "category": CATEGORY_SCHEMA,
            "include_archived": {"type": "boolean"},
        },
        "required": ["category", "include_archived"],
        "additionalProperties": False,
    },
}

GET_MEMORY_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "get_memory",
    "description": "根据唯一 memory_id 精确读取一条已保存的 Memory。",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {"memory_id": {"type": "string"}},
        "required": ["memory_id"],
        "additionalProperties": False,
    },
}

SEARCH_MEMORIES_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "search_memories",
    "description": (
        "当用户明确引用以前记住的内容但未提供 memory_id 时，用简单关键词查找 active Memory。"
        "这不是语义搜索，找不到时不要猜测。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "category": CATEGORY_SCHEMA,
            "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        },
        "required": ["query", "category", "limit"],
        "additionalProperties": False,
    },
}

UPDATE_MEMORY_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "update_memory",
    "description": (
        "仅当用户明确要求更正一条唯一 memory_id 的 Memory 时使用。"
        "category 与 content 至少提供一项，不得根据模糊描述猜测目标。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "memory_id": {"type": "string"},
            "category": CATEGORY_SCHEMA,
            "content": {"type": ["string", "null"]},
        },
        "required": ["memory_id", "category", "content"],
        "additionalProperties": False,
    },
}

ARCHIVE_MEMORY_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "archive_memory",
    "description": "仅当用户明确要求归档唯一 memory_id 时使用；归档不是物理删除。",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {"memory_id": {"type": "string"}},
        "required": ["memory_id"],
        "additionalProperties": False,
    },
}

FORGET_MEMORY_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "forget_memory",
    "description": (
        "仅当用户明确要求彻底遗忘并给出唯一 memory_id 时物理删除该条 Memory。"
        "不得按模糊描述或批量猜测删除。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {"memory_id": {"type": "string"}},
        "required": ["memory_id"],
        "additionalProperties": False,
    },
}

MEMORY_TOOLS = [
    SAVE_MEMORY_TOOL,
    LIST_MEMORIES_TOOL,
    GET_MEMORY_TOOL,
    SEARCH_MEMORIES_TOOL,
    UPDATE_MEMORY_TOOL,
    ARCHIVE_MEMORY_TOOL,
    FORGET_MEMORY_TOOL,
]
