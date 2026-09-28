"""Tests for local embedding validation without downloading a model."""

from __future__ import annotations

import math

import pytest

from src.knowledge.embeddings import EmbeddingError, LocalBGEEmbedder, validate_vectors


class FakeEncoded(list):
    def tolist(self) -> list[list[float]]:
        return list(self)


class FakeModel:
    def __init__(self) -> None:
        self.inputs: list[list[str]] = []

    def encode(self, texts, **kwargs):
        self.inputs.append(list(texts))
        return FakeEncoded([[3.0, 4.0] for _ in texts])


def test_local_embedder_normalizes_documents() -> None:
    model = FakeModel()
    embedder = LocalBGEEmbedder(model_name="fake", model=model)
    vectors = embedder.embed_documents(["制度一", "制度二"])
    assert len(vectors) == 2
    assert math.isclose(sum(value * value for value in vectors[0]), 1.0)


def test_query_uses_chinese_retrieval_instruction() -> None:
    model = FakeModel()
    embedder = LocalBGEEmbedder(model_name="fake", model=model)
    embedder.embed_query("年度调薪")
    assert model.inputs[0][0].startswith("为这个句子生成表示以用于检索相关文章：")


def test_embedding_rejects_empty_text() -> None:
    embedder = LocalBGEEmbedder(model_name="fake", model=FakeModel())
    with pytest.raises(EmbeddingError, match="非空文本"):
        embedder.embed_documents([""])


@pytest.mark.parametrize(
    "vectors,count,message",
    [
        ([], 1, "数量"),
        ([[0.0, 0.0]], 1, "零向量"),
        ([[1.0, 0.0], [1.0]], 2, "维度"),
        ([[float("nan"), 1.0]], 1, "非有限"),
    ],
)
def test_vector_validation_errors(vectors, count, message) -> None:
    with pytest.raises(EmbeddingError, match=message):
        validate_vectors(vectors, expected_count=count)
