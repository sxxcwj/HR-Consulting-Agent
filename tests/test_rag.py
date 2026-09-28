"""Service tests for registry-to-retrieval behavior."""

from __future__ import annotations

import math

from src.knowledge import KnowledgeRegistry
from src.knowledge.rag import RAGService
from src.knowledge.vector_store import SQLiteVectorStore


class KeywordEmbedder:
    model_name = "keyword-test"

    @staticmethod
    def _vector(text: str) -> list[float]:
        raw = [
            float(text.count("调薪") + text.count("薪酬") + text.count("奖金")),
            float(text.count("绩效") + text.count("面谈")),
            float(text.count("招聘") + text.count("录用")),
            0.1,
        ]
        norm = math.sqrt(sum(value * value for value in raw))
        return [value / norm for value in raw]

    def embed_documents(self, texts):
        return [self._vector(text) for text in texts]

    def embed_query(self, text):
        return self._vector(text)


def _service(tmp_path, text: str = "# 调薪\n公司每年七月进行年度调薪评审。") -> RAGService:
    source = tmp_path / "薪酬管理制度.md"
    source.write_text(text, encoding="utf-8")
    registry = KnowledgeRegistry(tmp_path / "knowledge")
    assert registry.register_file(str(source))["success"] is True
    return RAGService(
        registry=registry,
        embedder=KeywordEmbedder(),
        vector_store=SQLiteVectorStore(tmp_path / "knowledge" / "vectors.sqlite3"),
    )


def test_build_and_search_returns_traceable_source(tmp_path) -> None:
    service = _service(tmp_path)
    built = service.build_index(chunk_size=100, overlap=20)
    result = service.search("年度调薪什么时候？", top_k=1)
    assert built["success"] is True
    assert result["success"] is True
    assert "每年七月" in result["results"][0]["text"]
    assert result["results"][0]["document_id"].startswith("DOC-")
    assert "字符" in result["results"][0]["source"]


def test_search_requires_ready_index(tmp_path) -> None:
    result = _service(tmp_path).search("调薪", top_k=1)
    assert result["success"] is False
    assert result["error"]["code"] == "index_not_ready"


def test_search_validates_query_top_k_and_document_ids(tmp_path) -> None:
    service = _service(tmp_path)
    service.build_index(chunk_size=100, overlap=20)
    assert service.search("", top_k=1)["error"]["code"] == "invalid_query"
    assert service.search("调薪", top_k=11)["error"]["code"] == "invalid_top_k"
    result = service.search("调薪", top_k=1, document_ids=["DOC-NOT-FOUND"])
    assert result["error"]["code"] == "document_not_found"


def test_sensitive_content_is_masked_before_indexing(tmp_path) -> None:
    service = _service(tmp_path, "# 联系人\n手机号：13812345678。薪酬制度。")
    service.build_index(chunk_size=100, overlap=10)
    result = service.search("薪酬联系人", top_k=1)
    assert "13812345678" not in result["results"][0]["text"]
    assert "手机号" in result["results"][0]["sensitive_information_masked"]


def test_status_detects_registry_change(tmp_path) -> None:
    service = _service(tmp_path)
    service.build_index(chunk_size=100, overlap=20)
    second = tmp_path / "绩效管理制度.md"
    second.write_text("# 绩效\n每半年进行一次绩效面谈。", encoding="utf-8")
    service.registry.register_file(str(second))
    status = service.get_status()
    assert status["ready"] is False
    assert len(status["missing_document_ids"]) == 1


def test_status_detects_embedding_model_change(tmp_path) -> None:
    service = _service(tmp_path)
    service.build_index(chunk_size=100, overlap=20)

    class OtherEmbedder(KeywordEmbedder):
        model_name = "other-model"

    changed = RAGService(
        registry=service.registry,
        embedder=OtherEmbedder(),
        vector_store=service.vector_store,
    ).get_status()
    assert changed["ready"] is False
    assert changed["reason"] == "embedding_model_changed"
    assert changed["model_mismatch"] is True


def test_build_rejects_invalid_chunk_settings(tmp_path) -> None:
    result = _service(tmp_path).build_index(chunk_size=100, overlap=100)
    assert result["success"] is False
    assert result["error"]["code"] == "chunking_error"


def test_retrieval_flags_potential_version_conflict_even_if_top_one(tmp_path) -> None:
    registry = KnowledgeRegistry(tmp_path / "knowledge")
    first = tmp_path / "薪酬制度2024.md"
    second = tmp_path / "薪酬制度2026.md"
    first.write_text("年度调薪在四月进行。", encoding="utf-8")
    second.write_text("年度调薪在七月进行。", encoding="utf-8")
    registry.register_file(str(first))
    registry.register_file(str(second))
    service = RAGService(
        registry=registry,
        embedder=KeywordEmbedder(),
        vector_store=SQLiteVectorStore(tmp_path / "knowledge" / "vectors.sqlite3"),
    )
    service.build_index(chunk_size=100, overlap=10)
    result = service.search("年度调薪时间", top_k=1)
    assert result["success"] is True
    assert len(result["potential_version_conflicts"]) == 1
    assert len(result["potential_version_conflicts"][0]) == 2
