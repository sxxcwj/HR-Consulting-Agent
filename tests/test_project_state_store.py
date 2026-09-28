"""Tests for V0.7 project state persistence and validation."""

from __future__ import annotations

import json

from src.state import ProjectStateStore


def _create(store: ProjectStateStore, name: str = "销售离职诊断") -> dict:
    return store.create_project(
        name=name,
        objective="识别销售人员离职上升的可验证原因",
        organization_context={
            "industry": "制造业",
            "employee_count": 200,
            "location": "上海",
            "development_stage": "成长期",
        },
    )


def test_create_persists_and_selects_project(tmp_path) -> None:
    store = ProjectStateStore(tmp_path / "state")
    created = _create(store)
    project_id = created["project"]["project_id"]

    reopened = ProjectStateStore(tmp_path / "state")
    current = reopened.get_project()

    assert created["success"] is True
    assert project_id.startswith("PRJ-")
    assert current["project"]["project_id"] == project_id
    assert current["project"]["current_stage"] == "discovery"
    assert current["project"]["organization_context"]["employee_count"] == 200


def test_creating_second_project_changes_only_selection(tmp_path) -> None:
    store = ProjectStateStore(tmp_path / "state")
    first = _create(store, "项目一")["project"]["project_id"]
    second = _create(store, "项目二")["project"]["project_id"]
    listed = store.list_projects()

    assert listed["active_project_id"] == second
    assert {item["status"] for item in listed["projects"]} == {"active"}
    assert store.select_project(project_id=first)["success"] is True
    assert store.get_project()["project"]["project_id"] == first


def test_update_merges_context_and_explicit_lists(tmp_path) -> None:
    store = ProjectStateStore(tmp_path / "state")
    project_id = _create(store)["project"]["project_id"]
    updated = store.update_project(
        project_id=project_id,
        current_stage="diagnosis",
        organization_context={"employee_count": 210},
        add_confirmed_facts=["销售离职人数增加", "销售离职人数增加"],
        add_open_questions=["平均员工人数是多少？"],
        add_decisions=["先核对离职口径"],
        selected_document_ids=["DOC-ABC"],
        selected_data_files=["data/sales.xlsx"],
    )
    resolved = store.update_project(
        project_id=project_id,
        resolve_open_questions=["平均员工人数是多少？"],
    )

    assert updated["success"] is True
    assert updated["project"]["current_stage"] == "diagnosis"
    assert updated["project"]["organization_context"]["industry"] == "制造业"
    assert updated["project"]["organization_context"]["employee_count"] == 210
    assert updated["project"]["confirmed_facts"] == ["销售离职人数增加"]
    assert resolved["project"]["open_questions"] == []
    assert resolved["project"]["selected_document_ids"] == ["DOC-ABC"]


def test_update_requires_actual_changes(tmp_path) -> None:
    store = ProjectStateStore(tmp_path / "state")
    _create(store)
    result = store.update_project()
    assert result["success"] is False
    assert result["error"]["code"] == "no_changes"


def test_invalid_stage_and_employee_count_fail(tmp_path) -> None:
    store = ProjectStateStore(tmp_path / "state")
    project_id = _create(store)["project"]["project_id"]
    stage = store.update_project(project_id=project_id, current_stage="unknown")
    count = store.update_project(
        project_id=project_id, organization_context={"employee_count": -1}
    )
    assert stage["error"]["code"] == "invalid_update"
    assert count["error"]["code"] == "invalid_update"


def test_duplicate_active_name_is_rejected(tmp_path) -> None:
    store = ProjectStateStore(tmp_path / "state")
    _create(store)
    duplicate = _create(store)
    assert duplicate["success"] is False
    assert duplicate["error"]["code"] == "duplicate_project_name"


def test_archive_is_recoverable_but_not_selectable_or_updatable(tmp_path) -> None:
    store = ProjectStateStore(tmp_path / "state")
    project_id = _create(store)["project"]["project_id"]
    archived = store.archive_project(project_id=project_id)

    assert archived["success"] is True
    assert archived["deleted"] is False
    assert store.list_projects()["active_project_id"] is None
    assert store.select_project(project_id=project_id)["error"]["code"] == "project_archived"
    assert (
        store.update_project(project_id=project_id, objective="新目标")["error"]["code"]
        == "project_archived"
    )
    assert store.get_project(project_id=project_id)["project"]["status"] == "archived"


def test_no_active_project_is_explicit(tmp_path) -> None:
    store = ProjectStateStore(tmp_path / "state")
    project_id = _create(store)["project"]["project_id"]
    store.archive_project(project_id=project_id)

    result = store.get_project()
    assert result["success"] is False
    assert result["error"]["code"] == "project_not_found"
    assert "创建或选择" in result["error"]["message"]
    assert result["available_projects"] == [
        {
            "project_id": project_id,
            "name": "销售离职诊断",
            "status": "archived",
        }
    ]


def test_empty_explicit_project_id_does_not_fall_back_to_active(tmp_path) -> None:
    store = ProjectStateStore(tmp_path / "state")
    _create(store)
    result = store.get_project(project_id="")
    assert result["success"] is False
    assert "project_id" in result["error"]["message"]


def test_sensitive_employee_data_is_rejected(tmp_path) -> None:
    store = ProjectStateStore(tmp_path / "state")
    created = _create(store)
    project_id = created["project"]["project_id"]
    result = store.update_project(
        project_id=project_id,
        add_confirmed_facts=["员工手机号：13812345678"],
    )
    assert result["success"] is False
    assert result["error"]["code"] == "sensitive_state_content"
    assert "手机号" in result["detected_sensitive_types"]


def test_corrupt_and_unsupported_state_files_fail_clearly(tmp_path) -> None:
    root = tmp_path / "state"
    root.mkdir()
    path = root / "projects.json"
    path.write_text("{not json", encoding="utf-8")
    corrupt = ProjectStateStore(root).list_projects()
    assert corrupt["error"]["code"] == "state_store_error"

    path.write_text(
        json.dumps({"schema_version": 99, "active_project_id": None, "projects": []}),
        encoding="utf-8",
    )
    unsupported = ProjectStateStore(root).list_projects()
    assert unsupported["error"]["code"] == "state_store_error"
    assert "schema_version" in unsupported["error"]["message"]


def test_atomic_write_leaves_no_temporary_file(tmp_path) -> None:
    store = ProjectStateStore(tmp_path / "state")
    _create(store)
    assert store.path.exists()
    assert not store.path.with_suffix(".json.tmp").exists()
