"""Deterministic, source-traceable chunking for registered documents."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any

from .document_loader import Document


DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 80
MIN_CHUNK_SIZE = 100
MAX_CHUNK_SIZE = 4000


class ChunkingError(ValueError):
    """Raised when a document cannot be split with the requested settings."""


@dataclass(frozen=True)
class DocumentChunk:
    """One text passage with an exact range in the normalized document."""

    chunk_id: str
    document_id: str
    file_name: str
    title: str
    text: str
    start: int
    end: int
    heading: str | None
    character_count: int
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_settings(chunk_size: int, overlap: int) -> None:
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
        raise ChunkingError("chunk_size 必须是整数。")
    if not MIN_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE:
        raise ChunkingError(
            f"chunk_size 必须在 {MIN_CHUNK_SIZE} 到 {MAX_CHUNK_SIZE} 之间。"
        )
    if isinstance(overlap, bool) or not isinstance(overlap, int) or overlap < 0:
        raise ChunkingError("overlap 必须是大于或等于 0 的整数。")
    if overlap >= chunk_size:
        raise ChunkingError("overlap 必须小于 chunk_size。")


def _preferred_end(text: str, start: int, desired_end: int) -> int:
    if desired_end >= len(text):
        return len(text)
    search_start = start + (desired_end - start) // 2
    window = text[search_start:desired_end]
    boundaries = [match.end() for match in re.finditer(r"\n\s*\n|[。！？；!?;]\s*|\n", window)]
    if boundaries:
        return search_start + boundaries[-1]
    return desired_end


def _heading_before(text: str, position: int) -> str | None:
    heading: str | None = None
    for match in re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", text[: position + 1]):
        heading = match.group(1).strip()
    return heading


def chunk_document(
    document: Document,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    """Split normalized text while preserving stable ids and source offsets."""
    _validate_settings(chunk_size, overlap)
    if document.parse_status != "ready" or not document.text.strip():
        raise ChunkingError("只能分块包含可读文本的 ready 文档。")

    chunks: list[DocumentChunk] = []
    cursor = 0
    text = document.text
    while cursor < len(text):
        desired_end = min(len(text), cursor + chunk_size)
        end = _preferred_end(text, cursor, desired_end)
        raw = text[cursor:end]
        leading = len(raw) - len(raw.lstrip())
        trailing = len(raw) - len(raw.rstrip())
        actual_start = cursor + leading
        actual_end = end - trailing
        passage = text[actual_start:actual_end]
        if passage:
            digest = hashlib.sha256(
                f"{document.document_id}:{actual_start}:{actual_end}:{passage}".encode("utf-8")
            ).hexdigest()[:16].upper()
            chunks.append(
                DocumentChunk(
                    chunk_id=f"CHK-{digest}",
                    document_id=document.document_id,
                    file_name=document.file_name,
                    title=document.title,
                    text=passage,
                    start=actual_start,
                    end=actual_end,
                    heading=_heading_before(text, actual_end),
                    character_count=len(passage),
                    metadata={
                        "content_sha256": document.metadata.get("content_sha256"),
                        "modified_at": document.metadata.get("modified_at"),
                    },
                )
            )
        if end >= len(text):
            break
        next_cursor = end - overlap
        cursor = next_cursor if next_cursor > cursor else end

    if not chunks:
        raise ChunkingError("文档分块后没有可用文本。")
    return chunks
