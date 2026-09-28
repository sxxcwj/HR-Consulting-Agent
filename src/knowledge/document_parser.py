"""Format-specific text extraction for the V0.5 file knowledge base."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from docx import Document as DocxDocument
from docx.document import Document as DocxDocumentType
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from pypdf import PdfReader


SUPPORTED_DOCUMENT_TYPES = {".txt", ".md", ".docx", ".pdf"}


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "parse_status": code,
        "error": {"code": code, "message": message},
    }


def _normalize_text(text: str) -> str:
    """Normalize line endings and trailing whitespace without rewriting content."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    normalized: list[str] = []
    blank = False
    for line in lines:
        if line:
            normalized.append(line)
            blank = False
        elif not blank:
            normalized.append("")
            blank = True
    return "\n".join(normalized).strip()


def _iter_docx_blocks(document: DocxDocumentType) -> Iterator[Paragraph | Table]:
    """Yield paragraphs and tables in their XML body order."""
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _parse_text(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return _error("text_decode_error", "文本文件不是可读取的 UTF-8 编码。")
    normalized = _normalize_text(text)
    if not normalized:
        return _error("empty_document", "文件为空或不包含可读取文本。")
    return {
        "success": True,
        "parse_status": "ready",
        "text": normalized,
        "metadata": {"parser": "utf-8-text"},
    }


def _parse_docx(path: Path) -> dict[str, Any]:
    try:
        document = DocxDocument(path)
        parts: list[str] = []
        paragraph_count = 0
        table_count = 0
        for block in _iter_docx_blocks(document):
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if not text:
                    continue
                paragraph_count += 1
                style_name = block.style.name if block.style is not None else ""
                if style_name.lower().startswith("heading"):
                    level_text = style_name.removeprefix("Heading").strip()
                    level = int(level_text) if level_text.isdigit() else 1
                    parts.append(f"{'#' * min(max(level, 1), 6)} {text}")
                else:
                    parts.append(text)
            else:
                table_count += 1
                for row in block.rows:
                    cells = [_normalize_text(cell.text).replace("\n", " / ") for cell in row.cells]
                    if any(cells):
                        parts.append(" | ".join(cells))
        normalized = _normalize_text("\n\n".join(parts))
    except Exception as exc:
        return _error("docx_parse_error", f"DOCX 无法正常解析：{type(exc).__name__}。")
    if not normalized:
        return _error("empty_document", "DOCX 为空或不包含可读取文本。")
    return {
        "success": True,
        "parse_status": "ready",
        "text": normalized,
        "metadata": {
            "parser": "python-docx",
            "paragraph_count": paragraph_count,
            "table_count": table_count,
        },
    }


def _parse_pdf(path: Path) -> dict[str, Any]:
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            try:
                if reader.decrypt("") == 0:
                    return _error("encrypted_pdf", "PDF 已加密，无法读取文本。")
            except Exception:
                return _error("encrypted_pdf", "PDF 已加密，无法读取文本。")
        page_texts: list[str] = []
        for page in reader.pages:
            extracted = page.extract_text() or ""
            page_texts.append(_normalize_text(extracted))
        normalized = _normalize_text("\n\n".join(page_texts))
    except Exception as exc:
        return _error("pdf_parse_error", f"PDF 无法正常解析：{type(exc).__name__}。")
    if not normalized:
        return _error(
            "scanned_or_unreadable_pdf",
            "PDF 未提取到机器可读文本，可能是扫描件或文本层不可读；V0.5 不提供 OCR。",
        )
    return {
        "success": True,
        "parse_status": "ready",
        "text": normalized,
        "metadata": {"parser": "pypdf", "page_count": len(reader.pages)},
    }


def parse_document(file_path: str | Path) -> dict[str, Any]:
    """Extract normalized text from one supported enterprise document."""
    path = Path(file_path).expanduser()
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_DOCUMENT_TYPES:
        return _error(
            "unsupported_file_type",
            "仅支持 .txt、.md、.docx 和 .pdf；.xlsx 仍由 Excel Reader 处理。",
        )
    if suffix in {".txt", ".md"}:
        return _parse_text(path)
    if suffix == ".docx":
        return _parse_docx(path)
    return _parse_pdf(path)

