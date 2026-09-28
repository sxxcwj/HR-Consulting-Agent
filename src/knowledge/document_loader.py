"""Validate and standardize enterprise documents before registration."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .document_parser import SUPPORTED_DOCUMENT_TYPES, parse_document


@dataclass(frozen=True)
class Document:
    """Normalized V0.5 enterprise document object."""

    document_id: str
    file_name: str
    file_type: str
    title: str
    text: str
    character_count: int
    created_at: str
    source_path: str
    metadata: dict[str, Any] = field(default_factory=dict)
    parse_status: str = "ready"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Document":
        return cls(**value)


def _error(code: str, message: str, *, file_name: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "parse_status": code,
        "error": {"code": code, "message": message},
    }
    if file_name is not None:
        result["file_name"] = file_name
    return result


def load_document(file_path: str) -> dict[str, Any]:
    """Validate a path, parse its content, and return a normalized document."""
    path = Path(file_path).expanduser()
    file_name = path.name
    if not path.exists() or not path.is_file():
        return _error("file_not_found", f"文件不存在：{file_path}", file_name=file_name)
    if path.suffix.lower() not in SUPPORTED_DOCUMENT_TYPES:
        return _error(
            "unsupported_file_type",
            "仅支持 .txt、.md、.docx 和 .pdf；.xlsx 仍由 Excel Reader 处理。",
            file_name=file_name,
        )

    try:
        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        file_size = path.stat().st_size
    except OSError as exc:
        return _error("file_read_error", f"文件无法读取：{type(exc).__name__}。", file_name=file_name)

    parsed = parse_document(path)
    if not parsed.get("success"):
        return {**parsed, "file_name": file_name, "file_type": path.suffix.lower().lstrip(".")}

    document = Document(
        document_id=f"DOC-{content_hash[:12].upper()}",
        file_name=file_name,
        file_type=path.suffix.lower().lstrip("."),
        title=path.stem,
        text=parsed["text"],
        character_count=len(parsed["text"]),
        created_at=datetime.now(timezone.utc).isoformat(),
        source_path=str(path.resolve()),
        metadata={
            "file_size": file_size,
            "content_sha256": content_hash,
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            **parsed.get("metadata", {}),
        },
        parse_status="ready",
    )
    return {"success": True, **document.to_dict()}

