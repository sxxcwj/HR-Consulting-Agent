"""Tests for the local SQLite vector index."""

from __future__ import annotations

import pytest

from src.knowledge.chunking import DocumentChunk
from src.knowledge.vector_store import SQLiteVectorStore, VectorStoreError


def _chunk(chunk_id: str, document_id: str, text: str) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        file_name=f"{document_id}.md",
        title=document_id,
        text=text,
        start=0,
        end=len(text),
        heading=None,
        character_count=len(text),
        metadata={"content_sha256": document_id},
    )


def test_vector_store_persists_and_ranks(tmp_path) -> None:
    path = tmp_path / "vectors.sqlite3"
    store = SQLiteVectorStore(path)
    records = [
        (_chunk("C1", "D1", "调薪七月"), [1.0, 0.0], []),
        (_chunk("C2", "D2", "绩效沟通"), [0.0, 1.0], []),
    ]
    summary = store.replace_all(
        records, model_name="fake", document_hashes={"D1": "h1", "D2": "h2"}
    )
    reopened = SQLiteVectorStore(path)
    results = reopened.search([1.0, 0.0], top_k=2)

    assert summary["chunk_count"] == 2
    assert results[0]["chunk_id"] == "C1"
    assert results[0]["score"] == 1.0
    assert "字符 0-4" in results[0]["source"]


def test_vector_store_filters_documents(tmp_path) -> None:
    store = SQLiteVectorStore(tmp_path / "vectors.sqlite3")
    store.replace_all(
        [
            (_chunk("C1", "D1", "a"), [1.0, 0.0], []),
            (_chunk("C2", "D2", "b"), [0.0, 1.0], []),
        ],
        model_name="fake",
        document_hashes={"D1": "h1", "D2": "h2"},
    )
    results = store.search([1.0, 0.0], top_k=2, document_ids=["D2"])
    assert [item["document_id"] for item in results] == ["D2"]


def test_status_detects_missing_stale_and_orphaned(tmp_path) -> None:
    store = SQLiteVectorStore(tmp_path / "vectors.sqlite3")
    store.replace_all(
        [(_chunk("C1", "D1", "a"), [1.0], [])],
        model_name="fake",
        document_hashes={"D1": "old", "D3": "orphan"},
    )
    status = store.status({"D1": "new", "D2": "h2"})
    assert status["ready"] is False
    assert status["stale_document_ids"] == ["D1"]
    assert status["missing_document_ids"] == ["D2"]
    assert status["orphaned_document_ids"] == ["D3"]


def test_unbuilt_status_is_explicit(tmp_path) -> None:
    status = SQLiteVectorStore(tmp_path / "missing.sqlite3").status({"D1": "h1"})
    assert status["ready"] is False
    assert status["reason"] == "index_not_built"


def test_dimension_mismatch_fails(tmp_path) -> None:
    store = SQLiteVectorStore(tmp_path / "vectors.sqlite3")
    store.replace_all(
        [(_chunk("C1", "D1", "a"), [1.0, 0.0], [])],
        model_name="fake",
        document_hashes={"D1": "h1"},
    )
    with pytest.raises(VectorStoreError, match="维度"):
        store.search([1.0], top_k=1)


def test_empty_index_write_fails(tmp_path) -> None:
    with pytest.raises(VectorStoreError, match="空片段"):
        SQLiteVectorStore(tmp_path / "vectors.sqlite3").replace_all(
            [], model_name="fake", document_hashes={}
        )
