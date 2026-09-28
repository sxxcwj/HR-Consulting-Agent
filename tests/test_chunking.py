"""Tests for deterministic V0.6 document chunking."""

from __future__ import annotations

from src.knowledge.chunking import ChunkingError, chunk_document
from src.knowledge.document_loader import Document


def _document(text: str) -> Document:
    return Document(
        document_id="DOC-TEST",
        file_name="制度.md",
        file_type="md",
        title="制度",
        text=text,
        character_count=len(text),
        created_at="2026-01-01T00:00:00+00:00",
        source_path="/tmp/制度.md",
        metadata={"content_sha256": "abc"},
    )


def test_chunking_preserves_source_ranges_and_headings() -> None:
    text = "# 第一章\n" + "调薪规则。" * 80 + "\n\n# 第二章\n" + "奖金规则。" * 80
    chunks = chunk_document(_document(text), chunk_size=180, overlap=30)

    assert len(chunks) > 2
    assert all(text[item.start : item.end] == item.text for item in chunks)
    assert chunks[0].heading == "第一章"
    assert any(item.heading == "第二章" for item in chunks)


def test_chunk_ids_are_deterministic() -> None:
    document = _document("内容。" * 100)
    first = chunk_document(document, chunk_size=120, overlap=20)
    second = chunk_document(document, chunk_size=120, overlap=20)
    assert [item.chunk_id for item in first] == [item.chunk_id for item in second]


def test_chunk_overlap_keeps_progress() -> None:
    chunks = chunk_document(_document("甲乙丙丁戊。" * 100), chunk_size=100, overlap=99)
    assert chunks[-1].end == len(_document("甲乙丙丁戊。" * 100).text)
    assert len({item.chunk_id for item in chunks}) == len(chunks)


def test_chunking_rejects_invalid_settings() -> None:
    document = _document("有效文本。" * 30)
    for size, overlap in [(99, 0), (500, 500), (500, -1)]:
        try:
            chunk_document(document, chunk_size=size, overlap=overlap)
        except ChunkingError:
            pass
        else:
            raise AssertionError("invalid settings should fail")


def test_chunking_rejects_empty_document() -> None:
    try:
        chunk_document(_document("   "))
    except ChunkingError as exc:
        assert "可读文本" in str(exc)
    else:
        raise AssertionError("empty document should fail")
