"""JSON-backed registry for parsed V0.5 enterprise documents."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.config import APPLICATION_ROOT
from src.security import atomic_write_text, ensure_private_directory

from .document_loader import Document, load_document


DEFAULT_KNOWLEDGE_ROOT = APPLICATION_ROOT / "knowledge"


def _error(code: str, message: str, **details: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "error": {"code": code, "message": message},
    }
    result.update(details)
    return result


def _document_family(title: str) -> str:
    """Derive a filename-level family key only; this is not content search."""
    without_version = re.sub(r"(?:19|20)\d{2}(?:年|版)?", "", title)
    return re.sub(r"[\s_\-（）()]+", "", without_version).lower()


def _selection_key(value: str) -> str:
    """Normalize only filename decorations; never inspect document meaning."""
    stem = Path(value).stem
    without_order = re.sub(r"^\d+[\s_\-.、]*", "", stem)
    return re.sub(r"[\s_\-《》]+", "", without_order).lower()


class KnowledgeRegistry:
    """Persist document metadata and normalized text without a database."""

    def __init__(self, root: str | Path = DEFAULT_KNOWLEDGE_ROOT) -> None:
        self.root = Path(root).expanduser()
        self.documents_dir = self.root / "documents"
        self.parsed_dir = self.root / "parsed"
        self.index_path = self.root / "index.json"
        ensure_private_directory(self.root)
        ensure_private_directory(self.documents_dir)
        ensure_private_directory(self.parsed_dir)
        if not self.index_path.exists():
            self._write_index({"documents": []})

    def _read_index(self) -> dict[str, Any]:
        try:
            value = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"知识库索引无法读取：{type(exc).__name__}。") from exc
        if not isinstance(value, dict) or not isinstance(value.get("documents"), list):
            raise RuntimeError("知识库索引格式无效。")
        return value

    def _write_index(self, value: dict[str, Any]) -> None:
        atomic_write_text(
            self.index_path,
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        )

    @staticmethod
    def _metadata(document: Document) -> dict[str, Any]:
        return {
            "document_id": document.document_id,
            "file_name": document.file_name,
            "file_type": document.file_type,
            "title": document.title,
            "character_count": document.character_count,
            "created_at": document.created_at,
            "source_path": document.source_path,
            "metadata": document.metadata,
            "status": document.parse_status,
            "document_family": _document_family(document.title),
        }

    def register_document(self, document: Document | dict[str, Any]) -> dict[str, Any]:
        """Register one successfully parsed Document and persist its text."""
        if isinstance(document, dict):
            source = dict(document)
            source.pop("success", None)
            if source.get("parse_status") != "ready":
                return _error("document_not_ready", "只有成功解析的文档可以登记。")
            try:
                document = Document.from_dict(source)
            except (TypeError, KeyError) as exc:
                return _error("invalid_document", f"Document 结构无效：{type(exc).__name__}。")
        if document.parse_status != "ready" or not document.text.strip():
            return _error("document_not_ready", "只有包含可读文本的 ready 文档可以登记。")

        try:
            index = self._read_index()
        except RuntimeError as exc:
            return _error("registry_read_error", str(exc))
        existing = next(
            (
                item
                for item in index["documents"]
                if item.get("document_id") == document.document_id
            ),
            None,
        )
        if existing is not None:
            return {
                "success": True,
                "status": "already_registered",
                "document": existing,
                "potential_conflicts": self._potential_conflicts(index["documents"], existing),
            }

        metadata = self._metadata(document)
        candidates = [*index["documents"], metadata]
        try:
            parsed_path = self.parsed_dir / f"{document.document_id}.json"
            atomic_write_text(
                parsed_path,
                json.dumps(document.to_dict(), ensure_ascii=False, indent=2) + "\n",
            )
            self._write_index({"documents": candidates})
        except OSError as exc:
            return _error("registry_write_error", f"知识库登记失败：{type(exc).__name__}。")
        return {
            "success": True,
            "status": "registered",
            "document": metadata,
            "potential_conflicts": self._potential_conflicts(candidates, metadata),
        }

    def register_file(self, file_path: str) -> dict[str, Any]:
        loaded = load_document(file_path)
        if not loaded.get("success"):
            return loaded
        return self.register_document(loaded)

    @staticmethod
    def _potential_conflicts(
        documents: list[dict[str, Any]], selected: dict[str, Any]
    ) -> list[dict[str, Any]]:
        family = selected.get("document_family") or _document_family(str(selected.get("title", "")))
        return [
            {
                "document_id": item.get("document_id"),
                "file_name": item.get("file_name"),
                "title": item.get("title"),
                "created_at": item.get("created_at"),
                "modified_at": item.get("metadata", {}).get("modified_at"),
            }
            for item in documents
            if item.get("document_id") != selected.get("document_id")
            and (
                item.get("file_name") == selected.get("file_name")
                or item.get("title") == selected.get("title")
                or item.get("document_family") == family
            )
        ]

    def list_documents(self) -> dict[str, Any]:
        try:
            documents = self._read_index()["documents"]
        except RuntimeError as exc:
            return _error("registry_read_error", str(exc))
        public = [
            {
                "document_id": item.get("document_id"),
                "file_name": item.get("file_name"),
                "title": item.get("title"),
                "file_type": item.get("file_type"),
                "character_count": item.get("character_count"),
                "created_at": item.get("created_at"),
                "status": item.get("status"),
            }
            for item in documents
        ]
        families: dict[str, list[dict[str, Any]]] = {}
        for item in documents:
            families.setdefault(str(item.get("document_family", "")), []).append(item)
        conflicts = [
            [
                {"document_id": item.get("document_id"), "file_name": item.get("file_name")}
                for item in group
            ]
            for group in families.values()
            if len(group) > 1
        ]
        return {
            "success": True,
            "count": len(public),
            "documents": public,
            "potential_version_conflicts": conflicts,
        }

    def registry_records(self) -> list[dict[str, Any]]:
        """Return internal metadata needed to validate a local RAG index."""
        try:
            return list(self._read_index()["documents"])
        except RuntimeError as exc:
            raise RuntimeError(str(exc)) from exc

    def get_document_metadata(
        self, *, document_id: str | None = None, file_name: str | None = None
    ) -> dict[str, Any]:
        if bool(document_id) == bool(file_name):
            return _error("invalid_selector", "必须且只能提供 document_id 或 file_name。")
        try:
            documents = self._read_index()["documents"]
        except RuntimeError as exc:
            return _error("registry_read_error", str(exc))
        if document_id:
            matches = [item for item in documents if item.get("document_id") == document_id]
        else:
            requested_key = _selection_key(str(file_name))
            matches = [
                item
                for item in documents
                if item.get("file_name") == file_name
                or item.get("title") == file_name
                or _selection_key(str(item.get("file_name", ""))) == requested_key
                or _selection_key(str(item.get("title", ""))) == requested_key
            ]
        if not matches:
            return _error(
                "document_not_found",
                "知识库中没有找到指定文档。",
                available_documents=[item.get("file_name") for item in documents],
            )
        if len(matches) > 1:
            return _error(
                "ambiguous_document",
                "找到多个同名或同标题文档，请使用 document_id 指定版本。",
                candidates=[self._metadata_from_index(item) for item in matches],
            )
        selected = matches[0]
        return {
            "success": True,
            "document": self._metadata_from_index(selected),
            "potential_conflicts": self._potential_conflicts(documents, selected),
        }

    @staticmethod
    def _metadata_from_index(item: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in item.items() if key != "document_family"}

    def load_registered_document(self, document_id: str) -> dict[str, Any]:
        metadata = self.get_document_metadata(document_id=document_id)
        if not metadata.get("success"):
            return metadata
        parsed_path = self.parsed_dir / f"{document_id}.json"
        try:
            value = json.loads(parsed_path.read_text(encoding="utf-8"))
            document = Document.from_dict(value)
        except FileNotFoundError:
            return _error("parsed_document_missing", "登记记录存在，但解析文本文件缺失。")
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            return _error("parsed_document_error", f"解析文本无法读取：{type(exc).__name__}。")
        return {"success": True, "document": document}

    def remove_document_from_registry(self, document_id: str) -> dict[str, Any]:
        """Remove only the index entry; never delete the source document."""
        try:
            index = self._read_index()
        except RuntimeError as exc:
            return _error("registry_read_error", str(exc))
        retained = [
            item for item in index["documents"] if item.get("document_id") != document_id
        ]
        if len(retained) == len(index["documents"]):
            return _error("document_not_found", "知识库中没有找到指定 document_id。")
        try:
            self._write_index({"documents": retained})
        except OSError as exc:
            return _error("registry_write_error", f"登记记录移除失败：{type(exc).__name__}。")
        return {
            "success": True,
            "document_id": document_id,
            "source_file_deleted": False,
            "message": "已移除 Registry 记录，未删除用户原文件。",
        }


def list_documents() -> dict[str, Any]:
    return KnowledgeRegistry().list_documents()


def get_document_metadata(
    *, document_id: str | None = None, file_name: str | None = None
) -> dict[str, Any]:
    return KnowledgeRegistry().get_document_metadata(
        document_id=document_id, file_name=file_name
    )


def register_document(file_path: str) -> dict[str, Any]:
    return KnowledgeRegistry().register_file(file_path)


def remove_document_from_registry(document_id: str) -> dict[str, Any]:
    return KnowledgeRegistry().remove_document_from_registry(document_id)


REGISTER_KNOWLEDGE_DOCUMENT_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "register_knowledge_document",
    "description": (
        "当用户明确提供一个本地 .txt、.md、.docx 或 .pdf 文件路径并要求导入企业知识库时，"
        "读取、解析并登记该文件。不得用于 .xlsx；解析失败时不得声称登记成功。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "用户明确提供的本地企业文件路径。",
            }
        },
        "required": ["file_path"],
        "additionalProperties": False,
    },
}
