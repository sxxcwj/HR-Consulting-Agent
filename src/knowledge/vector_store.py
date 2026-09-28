"""Small local SQLite vector index for V0.6 semantic retrieval."""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.security import ensure_private_directory, ensure_private_file

from .chunking import DocumentChunk


class VectorStoreError(RuntimeError):
    """The local vector index is invalid or unavailable."""


class SQLiteVectorStore:
    """Persist normalized vectors and rank them by cosine (dot product)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def _connect(self) -> sqlite3.Connection:
        ensure_private_directory(self.path.parent)
        connection = sqlite3.connect(self.path)
        ensure_private_file(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS index_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS indexed_documents (
                document_id TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                chunk_count INTEGER NOT NULL,
                indexed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                title TEXT NOT NULL,
                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                heading TEXT,
                text TEXT NOT NULL,
                sensitive_labels TEXT NOT NULL,
                vector TEXT NOT NULL,
                dimension INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_document_id
                ON chunks(document_id);
            """
        )
        return connection

    def replace_all(
        self,
        records: list[tuple[DocumentChunk, list[float], list[str]]],
        *,
        model_name: str,
        document_hashes: dict[str, str],
    ) -> dict[str, Any]:
        if not records:
            raise VectorStoreError("不能用空片段集合建立向量索引。")
        dimension = len(records[0][1])
        if dimension <= 0 or any(len(vector) != dimension for _, vector, _ in records):
            raise VectorStoreError("待写入向量的维度无效或不一致。")
        if any(any(not math.isfinite(value) for value in vector) for _, vector, _ in records):
            raise VectorStoreError("待写入向量包含非有限数值。")
        now = datetime.now(timezone.utc).isoformat()
        counts: dict[str, int] = {}
        for chunk, _, _ in records:
            counts[chunk.document_id] = counts.get(chunk.document_id, 0) + 1
        try:
            with self._connect() as connection:
                connection.execute("DELETE FROM chunks")
                connection.execute("DELETE FROM indexed_documents")
                connection.execute("DELETE FROM index_metadata")
                connection.executemany(
                    "INSERT INTO index_metadata(key, value) VALUES (?, ?)",
                    [
                        ("model_name", model_name),
                        ("dimension", str(dimension)),
                        ("indexed_at", now),
                        ("schema_version", "1"),
                    ],
                )
                for document_id, content_hash in document_hashes.items():
                    connection.execute(
                        "INSERT INTO indexed_documents VALUES (?, ?, ?, ?)",
                        (document_id, content_hash, counts.get(document_id, 0), now),
                    )
                connection.executemany(
                    """
                    INSERT INTO chunks(
                        chunk_id, document_id, file_name, title, start_offset,
                        end_offset, heading, text, sensitive_labels, vector, dimension
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            chunk.chunk_id,
                            chunk.document_id,
                            chunk.file_name,
                            chunk.title,
                            chunk.start,
                            chunk.end,
                            chunk.heading,
                            chunk.text,
                            json.dumps(labels, ensure_ascii=False),
                            json.dumps(vector),
                            dimension,
                        )
                        for chunk, vector, labels in records
                    ],
                )
        except sqlite3.Error as exc:
            raise VectorStoreError(f"本地向量索引写入失败：{type(exc).__name__}。") from exc
        return {
            "model_name": model_name,
            "dimension": dimension,
            "indexed_at": now,
            "document_count": len(document_hashes),
            "chunk_count": len(records),
        }

    def status(self, registry_hashes: dict[str, str]) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "ready": False,
                "reason": "index_not_built",
                "model_name": None,
                "dimension": None,
                "indexed_at": None,
                "document_count": 0,
                "chunk_count": 0,
                "missing_document_ids": sorted(registry_hashes),
                "stale_document_ids": [],
                "orphaned_document_ids": [],
            }
        try:
            with self._connect() as connection:
                metadata = {
                    row["key"]: row["value"]
                    for row in connection.execute("SELECT key, value FROM index_metadata")
                }
                indexed = {
                    row["document_id"]: row["content_hash"]
                    for row in connection.execute(
                        "SELECT document_id, content_hash FROM indexed_documents"
                    )
                }
                chunk_count = int(
                    connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
                )
        except (sqlite3.Error, ValueError) as exc:
            raise VectorStoreError(f"本地向量索引无法读取：{type(exc).__name__}。") from exc
        missing = sorted(set(registry_hashes) - set(indexed))
        orphaned = sorted(set(indexed) - set(registry_hashes))
        stale = sorted(
            document_id
            for document_id in set(registry_hashes) & set(indexed)
            if registry_hashes[document_id] != indexed[document_id]
        )
        ready = bool(indexed) and chunk_count > 0 and not missing and not orphaned and not stale
        return {
            "ready": ready,
            "reason": "ready" if ready else "index_out_of_date",
            "model_name": metadata.get("model_name"),
            "dimension": int(metadata["dimension"]) if metadata.get("dimension") else None,
            "indexed_at": metadata.get("indexed_at"),
            "document_count": len(indexed),
            "chunk_count": chunk_count,
            "missing_document_ids": missing,
            "stale_document_ids": stale,
            "orphaned_document_ids": orphaned,
        }

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            with self._connect() as connection:
                metadata = {
                    row["key"]: row["value"]
                    for row in connection.execute("SELECT key, value FROM index_metadata")
                }
                dimension = int(metadata.get("dimension", "0"))
                if dimension <= 0:
                    raise VectorStoreError("本地向量索引尚未建立。")
                if len(query_vector) != dimension:
                    raise VectorStoreError(
                        f"查询向量维度 {len(query_vector)} 与索引维度 {dimension} 不一致。"
                    )
                sql = "SELECT * FROM chunks"
                parameters: list[Any] = []
                if document_ids:
                    placeholders = ",".join("?" for _ in document_ids)
                    sql += f" WHERE document_id IN ({placeholders})"
                    parameters.extend(document_ids)
                rows = connection.execute(sql, parameters).fetchall()
        except sqlite3.Error as exc:
            raise VectorStoreError(f"本地向量检索失败：{type(exc).__name__}。") from exc

        ranked: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            vector = [float(value) for value in json.loads(row["vector"])]
            score = sum(left * right for left, right in zip(query_vector, vector, strict=True))
            ranked.append((score, row))
        ranked.sort(key=lambda item: (-item[0], item[1]["chunk_id"]))
        return [
            {
                "rank": rank,
                "score": round(score, 6),
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "file_name": row["file_name"],
                "title": row["title"],
                "start": row["start_offset"],
                "end": row["end_offset"],
                "heading": row["heading"],
                "text": row["text"],
                "sensitive_information_masked": json.loads(row["sensitive_labels"]),
                "source": (
                    f"{row['file_name']} ({row['document_id']}, "
                    f"字符 {row['start_offset']}-{row['end_offset']})"
                ),
            }
            for rank, (score, row) in enumerate(ranked[:top_k], start=1)
        ]
