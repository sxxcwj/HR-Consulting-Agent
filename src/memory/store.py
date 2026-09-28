"""Atomic JSON persistence for user-authorized long-term memory."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.config import APPLICATION_ROOT
from src.security import atomic_write_text, detect_sensitive_labels

from .models import (
    MEMORY_CATEGORIES,
    MEMORY_SOURCE,
    MemoryEntry,
    MemoryValidationError,
    validate_category,
    validate_text,
)


DEFAULT_MEMORY_ROOT = APPLICATION_ROOT / "state"
MEMORY_SCHEMA_VERSION = 1


class MemoryStoreError(RuntimeError):
    """The memory file could not be safely read or written."""


def _error(code: str, message: str, **details: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "error": {"code": code, "message": message},
    }
    result.update(details)
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _search_terms(query: str) -> list[str]:
    normalized = query.casefold().strip()
    terms = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", normalized)
    expanded: list[str] = []
    for term in terms:
        if re.fullmatch(r"[\u4e00-\u9fff]{2,}", term) and len(term) > 2:
            expanded.extend(term[index : index + 2] for index in range(len(term) - 1))
        expanded.append(term)
    return list(dict.fromkeys(item for item in expanded if item))


class MemoryStore:
    """Persist only user-authorized stable context, never chat transcripts."""

    def __init__(self, root: str | Path = DEFAULT_MEMORY_ROOT) -> None:
        self.root = Path(root).expanduser()
        self.path = self.root / "memories.json"

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"schema_version": MEMORY_SCHEMA_VERSION, "memories": []}

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MemoryStoreError(
                f"Memory 文件无法读取：{type(exc).__name__}。"
            ) from exc
        if not isinstance(value, dict):
            raise MemoryStoreError("Memory 文件格式无效。")
        if value.get("schema_version") != MEMORY_SCHEMA_VERSION:
            raise MemoryStoreError("Memory schema_version 不受支持。")
        if not isinstance(value.get("memories"), list):
            raise MemoryStoreError("Memory 的 memories 必须是列表。")
        try:
            memories = [MemoryEntry.from_dict(item).to_dict() for item in value["memories"]]
        except (MemoryValidationError, TypeError) as exc:
            raise MemoryStoreError(f"Memory 内容无效：{exc}") from exc
        ids = [item["memory_id"] for item in memories]
        if len(ids) != len(set(ids)):
            raise MemoryStoreError("Memory 存在重复 memory_id。")
        return {"schema_version": MEMORY_SCHEMA_VERSION, "memories": memories}

    def _write(self, value: dict[str, Any]) -> None:
        try:
            atomic_write_text(
                self.path,
                json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            )
        except OSError as exc:
            raise MemoryStoreError(f"Memory 写入失败：{type(exc).__name__}。") from exc

    @staticmethod
    def _find(value: dict[str, Any], memory_id: str) -> dict[str, Any]:
        normalized_id = validate_text(memory_id, "memory_id", required=True)
        entry = next(
            (item for item in value["memories"] if item["memory_id"] == normalized_id),
            None,
        )
        if entry is None:
            raise MemoryValidationError("没有找到指定 memory_id。")
        return entry

    def save_memory(self, *, category: str, content: str) -> dict[str, Any]:
        try:
            normalized_category = validate_category(category)
            normalized_content = validate_text(content, "content", required=True)
        except MemoryValidationError as exc:
            return _error("invalid_memory", str(exc))
        labels = detect_sensitive_labels(normalized_content)
        if labels:
            return _error(
                "sensitive_memory_content",
                "Memory 不保存密钥或员工级敏感信息，请先删除或匿名化。",
                detected_sensitive_types=labels,
            )
        try:
            data = self._read()
            duplicate = next(
                (
                    item
                    for item in data["memories"]
                    if item["status"] == "active"
                    and item["category"] == normalized_category
                    and item["content"].casefold() == normalized_content.casefold()
                ),
                None,
            )
            if duplicate:
                return _error(
                    "duplicate_memory",
                    "已存在内容相同的 active Memory。",
                    existing_memory_id=duplicate["memory_id"],
                )
            now = _now()
            entry = MemoryEntry(
                memory_id=f"MEM-{uuid4().hex[:12].upper()}",
                category=normalized_category,
                content=normalized_content,
                status="active",
                source=MEMORY_SOURCE,
                created_at=now,
                updated_at=now,
            )
            data["memories"].append(entry.to_dict())
            self._write(data)
        except MemoryStoreError as exc:
            return _error("memory_store_error", str(exc))
        return {"success": True, "status": "saved", "memory": entry.to_dict()}

    def list_memories(
        self,
        *,
        category: str | None = None,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(include_archived, bool):
            return _error("invalid_arguments", "include_archived 必须是布尔值。")
        try:
            normalized_category = None if category is None else validate_category(category)
            data = self._read()
        except MemoryValidationError as exc:
            return _error("invalid_category", str(exc))
        except MemoryStoreError as exc:
            return _error("memory_store_error", str(exc))
        memories = [
            item
            for item in data["memories"]
            if (include_archived or item["status"] == "active")
            and (normalized_category is None or item["category"] == normalized_category)
        ]
        memories.sort(key=lambda item: item["updated_at"], reverse=True)
        return {"success": True, "count": len(memories), "memories": memories}

    def get_memory(self, *, memory_id: str) -> dict[str, Any]:
        try:
            entry = self._find(self._read(), memory_id)
        except MemoryStoreError as exc:
            return _error("memory_store_error", str(exc))
        except MemoryValidationError as exc:
            return _error("memory_not_found", str(exc))
        return {
            "success": True,
            "memory": entry,
            "evidence_note": "Memory 是用户明确保存的 MEMORY_CONTEXT，不等于当前外部核验事实。",
        }

    def search_memories(
        self,
        *,
        query: str,
        category: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        try:
            normalized_query = validate_text(query, "query", required=True, maximum=500)
            normalized_category = None if category is None else validate_category(category)
        except MemoryValidationError as exc:
            return _error("invalid_search", str(exc))
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
            return _error("invalid_search", "limit 必须是 1 到 20 的整数。")
        terms = _search_terms(normalized_query)
        try:
            data = self._read()
        except MemoryStoreError as exc:
            return _error("memory_store_error", str(exc))
        matches: list[dict[str, Any]] = []
        query_folded = normalized_query.casefold()
        for item in data["memories"]:
            if item["status"] != "active":
                continue
            if normalized_category is not None and item["category"] != normalized_category:
                continue
            content = item["content"].casefold()
            score = 10 if query_folded in content else 0
            score += sum(1 for term in terms if term in content)
            if score:
                matches.append({**item, "match_score": score})
        matches.sort(
            key=lambda item: (item["match_score"], item["updated_at"]), reverse=True
        )
        selected = matches[:limit]
        return {
            "success": True,
            "query": normalized_query,
            "search_method": "keyword",
            "count": len(selected),
            "memories": selected,
        }

    def update_memory(
        self,
        *,
        memory_id: str,
        category: str | None = None,
        content: str | None = None,
    ) -> dict[str, Any]:
        if category is None and content is None:
            return _error("no_changes", "没有提供任何 Memory 变更。")
        try:
            data = self._read()
            current = self._find(data, memory_id)
            if current["status"] == "archived":
                return _error("memory_archived", "归档 Memory 不能更新。")
            updated = dict(current)
            if category is not None:
                updated["category"] = validate_category(category)
            if content is not None:
                normalized_content = validate_text(content, "content", required=True)
                labels = detect_sensitive_labels(normalized_content)
                if labels:
                    return _error(
                        "sensitive_memory_content",
                        "Memory 不保存密钥或员工级敏感信息，请先删除或匿名化。",
                        detected_sensitive_types=labels,
                    )
                updated["content"] = normalized_content
            updated["updated_at"] = _now()
            validated = MemoryEntry.from_dict(updated).to_dict()
            data["memories"] = [
                validated if item["memory_id"] == validated["memory_id"] else item
                for item in data["memories"]
            ]
            self._write(data)
        except MemoryStoreError as exc:
            return _error("memory_store_error", str(exc))
        except MemoryValidationError as exc:
            return _error("invalid_update", str(exc))
        return {"success": True, "status": "updated", "memory": validated}

    def archive_memory(self, *, memory_id: str) -> dict[str, Any]:
        try:
            data = self._read()
            current = self._find(data, memory_id)
            if current["status"] == "archived":
                return _error("memory_archived", "Memory 已经归档。")
            archived = {**current, "status": "archived", "updated_at": _now()}
            data["memories"] = [
                archived if item["memory_id"] == current["memory_id"] else item
                for item in data["memories"]
            ]
            self._write(data)
        except MemoryStoreError as exc:
            return _error("memory_store_error", str(exc))
        except MemoryValidationError as exc:
            return _error("memory_not_found", str(exc))
        return {"success": True, "status": "archived", "memory": archived}

    def forget_memory(self, *, memory_id: str) -> dict[str, Any]:
        try:
            data = self._read()
            current = self._find(data, memory_id)
            data["memories"] = [
                item for item in data["memories"] if item["memory_id"] != current["memory_id"]
            ]
            self._write(data)
        except MemoryStoreError as exc:
            return _error("memory_store_error", str(exc))
        except MemoryValidationError as exc:
            return _error("memory_not_found", str(exc))
        return {
            "success": True,
            "status": "forgotten",
            "memory_id": current["memory_id"],
            "deleted": True,
        }
