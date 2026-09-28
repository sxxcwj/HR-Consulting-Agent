"""Tests for bounded and privacy-aware registered document reading."""

from pathlib import Path

from src.knowledge import KnowledgeRegistry, read_document


def _registered(registry: KnowledgeRegistry, path: Path, text: str) -> dict:
    path.write_text(text, encoding="utf-8")
    result = registry.register_file(str(path))
    assert result["success"] is True
    return result["document"]


def test_reads_short_document_by_filename(tmp_path: Path) -> None:
    registry = KnowledgeRegistry(tmp_path / "knowledge")
    _registered(registry, tmp_path / "02_薪酬管理制度.md", "年度调薪在七月评审。")

    result = read_document(file_name="薪酬管理制度", registry=registry)

    assert result["success"] is True
    assert result["text"] == "年度调薪在七月评审。"
    assert result["truncated"] is False
    assert result["source"]["file_name"] == "02_薪酬管理制度.md"


def test_long_document_supports_bounded_ranges(tmp_path: Path) -> None:
    registry = KnowledgeRegistry(tmp_path / "knowledge")
    metadata = _registered(registry, tmp_path / "long.md", "甲" * 9000)

    first = read_document(document_id=metadata["document_id"], registry=registry)
    second = read_document(
        document_id=metadata["document_id"], start=4000, end=4500, registry=registry
    )

    assert len(first["text"]) == 4000
    assert first["truncated"] is True
    assert first["next_start"] == 4000
    assert len(second["text"]) == 500
    assert second["returned_range"] == {"start": 4000, "end": 4500}


def test_missing_document_id_is_explicit(tmp_path: Path) -> None:
    registry = KnowledgeRegistry(tmp_path / "knowledge")

    result = read_document(document_id="DOC-MISSING", registry=registry)

    assert result["success"] is False
    assert result["error"]["code"] == "document_not_found"


def test_invalid_and_too_large_ranges_are_rejected(tmp_path: Path) -> None:
    registry = KnowledgeRegistry(tmp_path / "knowledge")
    metadata = _registered(registry, tmp_path / "long.md", "甲" * 9000)

    invalid = read_document(
        document_id=metadata["document_id"], start=20, end=10, registry=registry
    )
    too_large = read_document(
        document_id=metadata["document_id"], start=0, end=7000, registry=registry
    )

    assert invalid["error"]["code"] == "invalid_range"
    assert too_large["error"]["code"] == "range_too_large"


def test_sensitive_identifiers_are_masked_before_model_use(tmp_path: Path) -> None:
    registry = KnowledgeRegistry(tmp_path / "knowledge")
    _registered(
        registry,
        tmp_path / "complaint.md",
        "员工姓名：张三\n家庭地址：虚构市测试路100号\n联系信息：13812345678，person@example.com，11010519491231002X。\n医疗信息：虚构测试记录。",
    )

    result = read_document(file_name="complaint.md", registry=registry)

    assert "13812345678" not in result["text"]
    assert "person@example.com" not in result["text"]
    assert "11010519491231002X" not in result["text"]
    assert "张三" not in result["text"]
    assert "测试路100号" not in result["text"]
    assert "虚构测试记录" not in result["text"]
    assert set(result["sensitive_information_masked"]) == {
        "手机号",
        "邮箱",
        "身份证号",
        "姓名",
        "地址",
        "高度敏感记录",
    }
