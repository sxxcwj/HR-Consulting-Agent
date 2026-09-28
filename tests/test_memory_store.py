"""Tests for explicit V0.8 memory persistence and validation."""

from __future__ import annotations

import json

from src.memory import MemoryStore


def _save(
    store: MemoryStore,
    content: str = "公司考勤周期按自然月计算",
    category: str = "organization",
) -> dict:
    return store.save_memory(category=category, content=content)


def test_save_persists_across_store_instances(tmp_path) -> None:
    store = MemoryStore(tmp_path / "state")
    saved = _save(store)
    memory_id = saved["memory"]["memory_id"]

    reopened = MemoryStore(tmp_path / "state").get_memory(memory_id=memory_id)

    assert saved["success"] is True
    assert memory_id.startswith("MEM-")
    assert reopened["memory"]["content"] == "公司考勤周期按自然月计算"
    assert reopened["memory"]["source"] == "user_explicit"


def test_list_filters_category_and_archived_status(tmp_path) -> None:
    store = MemoryStore(tmp_path / "state")
    active = _save(store)["memory"]["memory_id"]
    archived = _save(store, "回答时优先使用中文", "preference")["memory"]["memory_id"]
    store.archive_memory(memory_id=archived)

    default_list = store.list_memories()
    all_items = store.list_memories(include_archived=True)
    preferences = store.list_memories(category="preference", include_archived=True)

    assert [item["memory_id"] for item in default_list["memories"]] == [active]
    assert all_items["count"] == 2
    assert preferences["memories"][0]["status"] == "archived"


def test_keyword_search_is_explicit_and_excludes_archived(tmp_path) -> None:
    store = MemoryStore(tmp_path / "state")
    expected = _save(store)["memory"]["memory_id"]
    archived = _save(store, "薪酬核算按自然月", "organization")["memory"]["memory_id"]
    store.archive_memory(memory_id=archived)

    result = store.search_memories(query="考勤口径", limit=5)

    assert result["success"] is True
    assert result["search_method"] == "keyword"
    assert [item["memory_id"] for item in result["memories"]] == [expected]
    assert result["memories"][0]["match_score"] > 0


def test_update_changes_only_explicit_fields(tmp_path) -> None:
    store = MemoryStore(tmp_path / "state")
    memory_id = _save(store)["memory"]["memory_id"]
    updated = store.update_memory(
        memory_id=memory_id,
        category="standing_instruction",
        content="考勤分析统一采用自然月口径",
    )

    assert updated["success"] is True
    assert updated["memory"]["category"] == "standing_instruction"
    assert updated["memory"]["content"] == "考勤分析统一采用自然月口径"
    assert updated["memory"]["created_at"] != ""


def test_update_requires_changes_and_active_memory(tmp_path) -> None:
    store = MemoryStore(tmp_path / "state")
    memory_id = _save(store)["memory"]["memory_id"]
    no_changes = store.update_memory(memory_id=memory_id)
    store.archive_memory(memory_id=memory_id)
    archived = store.update_memory(memory_id=memory_id, content="新内容")

    assert no_changes["error"]["code"] == "no_changes"
    assert archived["error"]["code"] == "memory_archived"


def test_forget_physically_removes_exact_memory(tmp_path) -> None:
    store = MemoryStore(tmp_path / "state")
    forgotten_id = _save(store)["memory"]["memory_id"]
    kept_id = _save(store, "内部术语：伙伴代表员工", "terminology")["memory"]["memory_id"]

    result = store.forget_memory(memory_id=forgotten_id)

    assert result == {
        "success": True,
        "status": "forgotten",
        "memory_id": forgotten_id,
        "deleted": True,
    }
    assert store.get_memory(memory_id=forgotten_id)["error"]["code"] == "memory_not_found"
    assert store.get_memory(memory_id=kept_id)["success"] is True


def test_missing_memory_and_invalid_category_fail_clearly(tmp_path) -> None:
    store = MemoryStore(tmp_path / "state")
    missing = store.get_memory(memory_id="MEM-NOT-FOUND")
    invalid = store.save_memory(category="other", content="内容")

    assert missing["error"]["code"] == "memory_not_found"
    assert invalid["error"]["code"] == "invalid_memory"


def test_duplicate_active_memory_is_rejected(tmp_path) -> None:
    store = MemoryStore(tmp_path / "state")
    first = _save(store)
    duplicate = _save(store)

    assert first["success"] is True
    assert duplicate["error"]["code"] == "duplicate_memory"
    assert duplicate["existing_memory_id"] == first["memory"]["memory_id"]


def test_sensitive_employee_data_and_credentials_are_rejected(tmp_path) -> None:
    store = MemoryStore(tmp_path / "state")
    phone = _save(store, "员工手机号是13812345678")
    secret = _save(store, "API_KEY=sk-abcdefghijklmnop")

    assert phone["error"]["code"] == "sensitive_memory_content"
    assert "手机号" in phone["detected_sensitive_types"]
    assert secret["error"]["code"] == "sensitive_memory_content"
    assert "密钥或凭据" in secret["detected_sensitive_types"]


def test_invalid_search_parameters_fail(tmp_path) -> None:
    store = MemoryStore(tmp_path / "state")
    assert store.search_memories(query="", limit=5)["error"]["code"] == "invalid_search"
    assert store.search_memories(query="考勤", limit=0)["error"]["code"] == "invalid_search"


def test_corrupt_and_unsupported_memory_files_fail_clearly(tmp_path) -> None:
    root = tmp_path / "state"
    root.mkdir()
    path = root / "memories.json"
    path.write_text("{not json", encoding="utf-8")
    corrupt = MemoryStore(root).list_memories()

    path.write_text(
        json.dumps({"schema_version": 99, "memories": []}), encoding="utf-8"
    )
    unsupported = MemoryStore(root).list_memories()

    assert corrupt["error"]["code"] == "memory_store_error"
    assert unsupported["error"]["code"] == "memory_store_error"
    assert "schema_version" in unsupported["error"]["message"]


def test_atomic_write_leaves_no_temporary_file(tmp_path) -> None:
    store = MemoryStore(tmp_path / "state")
    _save(store)
    assert store.path.exists()
    assert not store.path.with_suffix(".json.tmp").exists()
