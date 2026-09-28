"""Tests for the JSON-backed V0.5 Knowledge Registry."""

import json
from pathlib import Path

from src.knowledge import KnowledgeRegistry, load_document


def _register_markdown(registry: KnowledgeRegistry, path: Path, text: str) -> dict:
    path.write_text(text, encoding="utf-8")
    loaded = load_document(str(path))
    assert loaded["success"] is True
    return registry.register_document(loaded)


def test_register_list_and_get_metadata(tmp_path: Path) -> None:
    registry = KnowledgeRegistry(tmp_path / "knowledge")
    result = _register_markdown(registry, tmp_path / "01_员工手册.md", "# 员工手册\n测试规则。")

    listed = registry.list_documents()
    metadata = registry.get_document_metadata(file_name="员工手册")

    assert result["status"] == "registered"
    assert listed["count"] == 1
    assert listed["documents"][0]["file_name"] == "01_员工手册.md"
    assert metadata["success"] is True
    assert metadata["document"]["document_id"] == result["document"]["document_id"]
    index = json.loads((tmp_path / "knowledge" / "index.json").read_text(encoding="utf-8"))
    assert len(index["documents"]) == 1


def test_same_document_registration_is_idempotent(tmp_path: Path) -> None:
    registry = KnowledgeRegistry(tmp_path / "knowledge")
    path = tmp_path / "policy.md"
    first = _register_markdown(registry, path, "# 制度\n同一内容。")
    second = registry.register_file(str(path))

    assert first["document"]["document_id"] == second["document"]["document_id"]
    assert second["status"] == "already_registered"
    assert registry.list_documents()["count"] == 1


def test_remove_registry_record_never_deletes_source_file(tmp_path: Path) -> None:
    registry = KnowledgeRegistry(tmp_path / "knowledge")
    source = tmp_path / "policy.md"
    registered = _register_markdown(registry, source, "# 制度\n虚构内容。")

    result = registry.remove_document_from_registry(registered["document"]["document_id"])

    assert result["success"] is True
    assert result["source_file_deleted"] is False
    assert source.exists()
    assert registry.list_documents()["count"] == 0


def test_multiple_versions_are_flagged_not_auto_resolved(tmp_path: Path) -> None:
    registry = KnowledgeRegistry(tmp_path / "knowledge")
    first = _register_markdown(
        registry, tmp_path / "薪酬管理制度2024.md", "# 薪酬制度\n四月调薪。"
    )
    second = _register_markdown(
        registry, tmp_path / "薪酬管理制度2026.md", "# 薪酬制度\n七月调薪。"
    )

    listed = registry.list_documents()

    assert first["success"] is True and second["success"] is True
    assert second["potential_conflicts"]
    assert listed["potential_version_conflicts"]
    assert {item["file_name"] for item in listed["potential_version_conflicts"][0]} == {
        "薪酬管理制度2024.md",
        "薪酬管理制度2026.md",
    }


def test_missing_document_metadata_returns_available_files(tmp_path: Path) -> None:
    registry = KnowledgeRegistry(tmp_path / "knowledge")
    _register_markdown(registry, tmp_path / "handbook.md", "# 手册\n内容。")

    result = registry.get_document_metadata(document_id="DOC-NOT-FOUND")

    assert result["error"]["code"] == "document_not_found"
    assert result["available_documents"] == ["handbook.md"]

