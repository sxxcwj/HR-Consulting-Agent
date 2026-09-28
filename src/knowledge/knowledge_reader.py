"""Controlled reading of one explicitly selected registered document."""

from __future__ import annotations

import re
from typing import Any

from .knowledge_registry import KnowledgeRegistry
from .knowledge_registry import REGISTER_KNOWLEDGE_DOCUMENT_TOOL


DEFAULT_READ_LIMIT = 4000
MAX_READ_LIMIT = 6000


def _error(code: str, message: str, **details: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "error": {"code": code, "message": message},
    }
    result.update(details)
    return result


def redact_sensitive_text(text: str) -> tuple[str, list[str]]:
    """Apply minimum-necessary masking before document text reaches the model."""
    detected: list[str] = []
    patterns = (
        ("身份证号", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "[身份证号已脱敏]"),
        ("手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[手机号已脱敏]"),
        (
            "邮箱",
            re.compile(r"(?<![\w.])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.])"),
            "[邮箱已脱敏]",
        ),
        (
            "姓名",
            re.compile(r"(?P<label>(?:员工)?姓名\s*[：:])\s*[\u4e00-\u9fff·]{2,12}"),
            r"\g<label>[姓名已脱敏]",
        ),
        (
            "地址",
            re.compile(r"(?P<label>(?:家庭|居住|联系)?地址\s*[：:])[^\n，,；;]{4,100}"),
            r"\g<label>[地址已脱敏]",
        ),
        (
            "高度敏感记录",
            re.compile(
                r"(?P<label>(?:医疗信息|个人薪酬|处分记录|投诉记录)\s*[：:])[^\n]{1,300}"
            ),
            r"\g<label>[敏感内容已脱敏]",
        ),
    )
    result = text
    for label, pattern, replacement in patterns:
        result, count = pattern.subn(replacement, result)
        if count:
            detected.append(label)
    return result, detected


def read_document(
    *,
    document_id: str | None = None,
    file_name: str | None = None,
    start: int | None = None,
    end: int | None = None,
    registry: KnowledgeRegistry | None = None,
) -> dict[str, Any]:
    """Read a bounded character range from one exact registry selection."""
    active_registry = registry or KnowledgeRegistry()
    metadata = active_registry.get_document_metadata(
        document_id=document_id, file_name=file_name
    )
    if not metadata.get("success"):
        return metadata
    selected_id = metadata["document"]["document_id"]
    loaded = active_registry.load_registered_document(selected_id)
    if not loaded.get("success"):
        return loaded
    document = loaded["document"]

    if start is not None and (isinstance(start, bool) or not isinstance(start, int) or start < 0):
        return _error("invalid_range", "start 必须是大于或等于 0 的整数。")
    if end is not None and (isinstance(end, bool) or not isinstance(end, int) or end < 0):
        return _error("invalid_range", "end 必须是大于或等于 0 的整数。")

    resolved_start = 0 if start is None else start
    if resolved_start >= document.character_count and document.character_count > 0:
        return _error(
            "range_out_of_bounds",
            "start 超出文档文本范围。",
            character_count=document.character_count,
        )
    if end is None:
        resolved_end = min(document.character_count, resolved_start + DEFAULT_READ_LIMIT)
    else:
        resolved_end = min(end, document.character_count)
    if resolved_end <= resolved_start:
        return _error("invalid_range", "end 必须大于 start。")
    if resolved_end - resolved_start > MAX_READ_LIMIT:
        return _error(
            "range_too_large",
            f"单次最多读取 {MAX_READ_LIMIT} 个字符，请缩小 start/end 范围。",
        )

    text, detected = redact_sensitive_text(document.text[resolved_start:resolved_end])
    return {
        "success": True,
        "document_id": document.document_id,
        "file_name": document.file_name,
        "title": document.title,
        "file_type": document.file_type,
        "character_count": document.character_count,
        "returned_range": {"start": resolved_start, "end": resolved_end},
        "available_range": {"start": 0, "end": document.character_count},
        "truncated": resolved_end < document.character_count,
        "next_start": resolved_end if resolved_end < document.character_count else None,
        "text": text,
        "sensitive_information_masked": detected,
        "source": {"document_id": document.document_id, "file_name": document.file_name},
        "potential_conflicts": metadata.get("potential_conflicts", []),
    }


def read_knowledge_document(
    *,
    document_id: str | None = None,
    file_name: str | None = None,
    start: int | None = None,
    end: int | None = None,
) -> dict[str, Any]:
    return read_document(
        document_id=document_id,
        file_name=file_name,
        start=start,
        end=end,
    )


LIST_KNOWLEDGE_DOCUMENTS_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "list_knowledge_documents",
    "description": (
        "列出 V0.5 本地企业文件知识库已经登记的文件名、标题、类型和 document_id。"
        "仅查看 Registry，不搜索文档正文。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
}


GET_DOCUMENT_METADATA_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "get_document_metadata",
    "description": (
        "根据精确的 document_id、文件名或标题取得一个已登记文件的 metadata。"
        "用于确认文件身份和潜在版本冲突，不读取正文，也不做语义搜索。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "document_id": {"type": ["string", "null"], "description": "精确 document_id。"},
            "file_name": {"type": ["string", "null"], "description": "精确文件名或标题。"},
        },
        "required": ["document_id", "file_name"],
        "additionalProperties": False,
    },
}


READ_KNOWLEDGE_DOCUMENT_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "read_knowledge_document",
    "description": (
        "读取一个已登记且由 document_id、文件名或标题明确指定的企业文件。"
        "可按字符 start/end 分段读取。不得用此工具进行跨文档语义搜索或 Top-K 召回。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "document_id": {"type": ["string", "null"], "description": "精确 document_id。"},
            "file_name": {"type": ["string", "null"], "description": "精确文件名或标题。"},
            "start": {"type": ["integer", "null"], "minimum": 0, "description": "起始字符位置。"},
            "end": {"type": ["integer", "null"], "minimum": 0, "description": "结束字符位置。"},
        },
        "required": ["document_id", "file_name", "start", "end"],
        "additionalProperties": False,
    },
}


KNOWLEDGE_TOOLS = [
    REGISTER_KNOWLEDGE_DOCUMENT_TOOL,
    LIST_KNOWLEDGE_DOCUMENTS_TOOL,
    GET_DOCUMENT_METADATA_TOOL,
    READ_KNOWLEDGE_DOCUMENT_TOOL,
]
