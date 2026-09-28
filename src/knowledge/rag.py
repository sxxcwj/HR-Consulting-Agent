"""V0.6 RAG orchestration: registry to chunks, vectors, and retrieval."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    ChunkingError,
    DocumentChunk,
    chunk_document,
)
from .embeddings import (
    EmbeddingError,
    EmbeddingProvider,
    LocalBGEEmbedder,
    validate_vectors,
)
from .knowledge_reader import redact_sensitive_text
from .knowledge_registry import DEFAULT_KNOWLEDGE_ROOT, KnowledgeRegistry
from .vector_store import SQLiteVectorStore, VectorStoreError


DEFAULT_VECTOR_INDEX_PATH = DEFAULT_KNOWLEDGE_ROOT / "vector_index.sqlite3"


def _error(code: str, message: str, **details: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "error": {"code": code, "message": message},
    }
    result.update(details)
    return result


class RAGService:
    """Coordinate existing V0.5 documents with local semantic retrieval."""

    def __init__(
        self,
        *,
        registry: KnowledgeRegistry | None = None,
        embedder: EmbeddingProvider | None = None,
        vector_store: SQLiteVectorStore | None = None,
        vector_index_path: str | Path = DEFAULT_VECTOR_INDEX_PATH,
    ) -> None:
        self.registry = registry or KnowledgeRegistry()
        self.embedder = embedder or LocalBGEEmbedder()
        self.vector_store = vector_store or SQLiteVectorStore(vector_index_path)

    def _registry_hashes(self) -> dict[str, str]:
        return {
            str(item["document_id"]): str(item.get("metadata", {}).get("content_sha256", ""))
            for item in self.registry.registry_records()
            if item.get("status") == "ready"
        }

    def get_status(self) -> dict[str, Any]:
        try:
            status = self.vector_store.status(self._registry_hashes())
        except (RuntimeError, VectorStoreError) as exc:
            return _error("index_status_error", str(exc))
        model_mismatch = bool(
            status.get("model_name")
            and status.get("model_name") != self.embedder.model_name
        )
        if model_mismatch:
            status["ready"] = False
            status["reason"] = "embedding_model_changed"
        status["configured_model_name"] = self.embedder.model_name
        status["model_mismatch"] = model_mismatch
        return {"success": True, **status}

    def build_index(
        self,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> dict[str, Any]:
        try:
            registry_records = self.registry.registry_records()
        except RuntimeError as exc:
            return _error("registry_read_error", str(exc))
        ready_records = [item for item in registry_records if item.get("status") == "ready"]
        if not ready_records:
            return _error("empty_registry", "知识库没有可建立索引的 ready 文档。")

        chunks: list[DocumentChunk] = []
        labels_by_chunk: dict[str, list[str]] = {}
        document_hashes: dict[str, str] = {}
        try:
            for metadata in ready_records:
                document_id = str(metadata["document_id"])
                loaded = self.registry.load_registered_document(document_id)
                if not loaded.get("success"):
                    return _error(
                        "document_load_error",
                        loaded.get("error", {}).get("message", "登记文档无法读取。"),
                        document_id=document_id,
                    )
                document = loaded["document"]
                document_hashes[document_id] = str(
                    document.metadata.get("content_sha256", "")
                )
                for chunk in chunk_document(
                    document, chunk_size=chunk_size, overlap=overlap
                ):
                    redacted, labels = redact_sensitive_text(chunk.text)
                    safe_chunk = DocumentChunk(
                        **{**chunk.to_dict(), "text": redacted}
                    )
                    chunks.append(safe_chunk)
                    labels_by_chunk[safe_chunk.chunk_id] = labels
            vectors = self.embedder.embed_documents([chunk.text for chunk in chunks])
            vectors, _ = validate_vectors(vectors, expected_count=len(chunks))
            summary = self.vector_store.replace_all(
                [
                    (chunk, vector, labels_by_chunk[chunk.chunk_id])
                    for chunk, vector in zip(chunks, vectors, strict=True)
                ],
                model_name=self.embedder.model_name,
                document_hashes=document_hashes,
            )
        except ChunkingError as exc:
            return _error("chunking_error", str(exc))
        except EmbeddingError as exc:
            return _error("embedding_error", str(exc))
        except VectorStoreError as exc:
            return _error("vector_store_error", str(exc))
        return {
            "success": True,
            "status": "indexed",
            "chunk_size": chunk_size,
            "overlap": overlap,
            **summary,
        }

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        document_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            return _error("invalid_query", "检索问题不能为空。")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 10:
            return _error("invalid_top_k", "top_k 必须是 1 到 10 之间的整数。")
        if document_ids is not None:
            if not isinstance(document_ids, list) or not document_ids or any(
                not isinstance(item, str) or not item.strip() for item in document_ids
            ):
                return _error(
                    "invalid_document_ids", "document_ids 必须是非空 document_id 列表。"
                )
            available = self._registry_hashes()
            missing = sorted(set(document_ids) - set(available))
            if missing:
                return _error(
                    "document_not_found",
                    "指定的 document_id 不在 Registry 中。",
                    missing_document_ids=missing,
                )

        status = self.get_status()
        if not status.get("success"):
            return status
        if not status.get("ready"):
            return _error(
                "index_not_ready",
                "本地 RAG 索引尚未建立或已过期，请先运行 build_knowledge_index。",
                index_status={key: value for key, value in status.items() if key != "success"},
            )

        safe_query, detected = redact_sensitive_text(query.strip())
        try:
            query_vector = self.embedder.embed_query(safe_query)
            normalized, _ = validate_vectors([query_vector], expected_count=1)
            results = self.vector_store.search(
                normalized[0], top_k=top_k, document_ids=document_ids
            )
        except EmbeddingError as exc:
            return _error("embedding_error", str(exc))
        except VectorStoreError as exc:
            return _error("vector_store_error", str(exc))

        conflict_groups = self.registry.list_documents().get(
            "potential_version_conflicts", []
        )
        result_ids = {item["document_id"] for item in results}
        relevant_conflicts = [
            group
            for group in conflict_groups
            if {item.get("document_id") for item in group} & result_ids
        ]
        return {
            "success": True,
            "query": safe_query,
            "top_k": top_k,
            "model_name": status.get("model_name"),
            "searched_chunk_count": status.get("chunk_count"),
            "result_count": len(results),
            "results": results,
            "query_sensitive_information_masked": detected,
            "potential_version_conflicts": relevant_conflicts,
            "evidence_note": (
                "相似度仅用于候选片段排序；回答必须核对片段是否直接支持结论。"
            ),
        }


_DEFAULT_SERVICE: RAGService | None = None


def _default_service() -> RAGService:
    global _DEFAULT_SERVICE
    if _DEFAULT_SERVICE is None:
        _DEFAULT_SERVICE = RAGService()
    return _DEFAULT_SERVICE


def build_knowledge_index(
    *,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> dict[str, Any]:
    return _default_service().build_index(
        chunk_size=DEFAULT_CHUNK_SIZE if chunk_size is None else chunk_size,
        overlap=DEFAULT_CHUNK_OVERLAP if overlap is None else overlap,
    )


def get_knowledge_index_status() -> dict[str, Any]:
    return _default_service().get_status()


def search_knowledge_base(
    query: str,
    *,
    top_k: int | None = None,
    document_ids: list[str] | None = None,
) -> dict[str, Any]:
    return _default_service().search(
        query,
        top_k=5 if top_k is None else top_k,
        document_ids=document_ids,
    )


BUILD_KNOWLEDGE_INDEX_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "build_knowledge_index",
    "description": (
        "当本地企业知识库的 RAG 索引尚未建立或已经过期时使用。"
        "对已登记文档进行脱敏、分块、本地中文 Embedding 和本地索引构建；不得修改源文件。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "chunk_size": {
                "type": ["integer", "null"],
                "minimum": 100,
                "maximum": 4000,
                "description": "分块字符数；null 使用默认 500。",
            },
            "overlap": {
                "type": ["integer", "null"],
                "minimum": 0,
                "description": "相邻片段重叠字符数；null 使用默认 80，且必须小于 chunk_size。",
            },
        },
        "required": ["chunk_size", "overlap"],
        "additionalProperties": False,
    },
}


GET_KNOWLEDGE_INDEX_STATUS_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "get_knowledge_index_status",
    "description": (
        "在语义检索前检查本地企业知识索引是否已建立、是否包含全部 Registry 文档、"
        "是否有过期或孤立文档。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
}


SEARCH_KNOWLEDGE_BASE_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "search_knowledge_base",
    "description": (
        "当用户未明确指定文件，或要求在多个/全部企业文件中查找与问题最相关的内容时使用。"
        "执行本地 Top-K 语义检索并返回真实片段和来源；不要凭模型记忆补写公司制度。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "用户要查找的企业制度问题。"},
            "top_k": {
                "type": ["integer", "null"],
                "minimum": 1,
                "maximum": 10,
                "description": "返回片段数量；null 使用默认 5。",
            },
            "document_ids": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "description": "可选的 document_id 限定范围。",
            },
        },
        "required": ["query", "top_k", "document_ids"],
        "additionalProperties": False,
    },
}


RAG_TOOLS = [
    BUILD_KNOWLEDGE_INDEX_TOOL,
    GET_KNOWLEDGE_INDEX_STATUS_TOOL,
    SEARCH_KNOWLEDGE_BASE_TOOL,
]
