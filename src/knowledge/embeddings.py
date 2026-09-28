"""Injectable local embedding provider used by the V0.6 RAG layer."""

from __future__ import annotations

import math
import os
from collections.abc import Sequence
from typing import Any, Protocol


DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


class EmbeddingError(RuntimeError):
    """A local model could not be loaded or returned invalid vectors."""


class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def validate_vectors(
    vectors: Sequence[Sequence[float]], *, expected_count: int
) -> tuple[list[list[float]], int]:
    if len(vectors) != expected_count:
        raise EmbeddingError("Embedding 返回的向量数量与输入文本数量不一致。")
    if not vectors:
        raise EmbeddingError("Embedding 未返回向量。")
    dimension = len(vectors[0])
    if dimension <= 0:
        raise EmbeddingError("Embedding 向量维度无效。")
    normalized: list[list[float]] = []
    for vector in vectors:
        if len(vector) != dimension:
            raise EmbeddingError("Embedding 返回了维度不一致的向量。")
        converted = [float(value) for value in vector]
        if any(not math.isfinite(value) for value in converted):
            raise EmbeddingError("Embedding 向量包含非有限数值。")
        norm = math.sqrt(sum(value * value for value in converted))
        if norm == 0:
            raise EmbeddingError("Embedding 返回了零向量。")
        normalized.append([value / norm for value in converted])
    return normalized, dimension


class LocalBGEEmbedder:
    """Lazily load BGE so ordinary HR questions do not pay model startup cost."""

    def __init__(self, model_name: str | None = None, *, model: Any | None = None) -> None:
        selected = model_name or os.getenv("HR_AGENT_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        if not selected.strip():
            raise EmbeddingError("HR_AGENT_EMBEDDING_MODEL 不能为空。")
        self._model_name = selected.strip()
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model_name

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingError(
                "缺少 sentence-transformers，请先运行 python -m pip install -r requirements.txt。"
            ) from exc
        try:
            self._model = SentenceTransformer(self._model_name)
        except Exception as exc:  # library raises several backend-specific errors
            raise EmbeddingError(
                f"本地 Embedding 模型无法加载：{type(exc).__name__}。"
            ) from exc
        return self._model

    def _encode(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
            raise EmbeddingError("Embedding 输入必须包含非空文本。")
        model = self._load()
        try:
            encoded = model.encode(
                list(texts),
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            raw_vectors = encoded.tolist() if hasattr(encoded, "tolist") else list(encoded)
        except Exception as exc:
            raise EmbeddingError(f"本地 Embedding 计算失败：{type(exc).__name__}。") from exc
        vectors, _ = validate_vectors(raw_vectors, expected_count=len(texts))
        return vectors

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        if not isinstance(text, str) or not text.strip():
            raise EmbeddingError("检索查询不能为空。")
        return self._encode([f"{QUERY_INSTRUCTION}{text.strip()}"])[0]
