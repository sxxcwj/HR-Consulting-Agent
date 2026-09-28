"""Tests for V0.7 public state functions and tool schemas."""

from __future__ import annotations

import pytest

from src.state import PROJECT_STATE_TOOLS, ProjectStateStore
from src.state import tools as state_tools


@pytest.fixture
def isolated_store(tmp_path, monkeypatch: pytest.MonkeyPatch) -> ProjectStateStore:
    store = ProjectStateStore(tmp_path / "state")
    monkeypatch.setattr(state_tools, "_DEFAULT_STORE", store)
    return store


def test_all_six_tools_are_registered() -> None:
    names = [tool["name"] for tool in PROJECT_STATE_TOOLS]
    assert names == [
        "create_project_state",
        "list_project_states",
        "get_project_state",
        "select_project_state",
        "update_project_state",
        "archive_project_state",
    ]
    assert all(tool["strict"] is True for tool in PROJECT_STATE_TOOLS)


def test_public_functions_complete_state_lifecycle(isolated_store) -> None:
    created = state_tools.create_project_state(
        "组织诊断",
        objective="确认职责交叉原因",
        organization_context={
            "industry": "服务业",
            "employee_count": 80,
            "location": None,
            "development_stage": "成长期",
        },
    )
    project_id = created["project"]["project_id"]
    updated = state_tools.update_project_state(
        project_id=project_id,
        add_open_questions=["岗位说明书是否更新？"],
    )
    listed = state_tools.list_project_states()
    selected = state_tools.select_project_state(project_id)
    fetched = state_tools.get_project_state(project_id=project_id)
    archived = state_tools.archive_project_state(project_id)

    assert updated["success"] is True
    assert listed["count"] == 1
    assert selected["success"] is True
    assert fetched["project"]["open_questions"] == ["岗位说明书是否更新？"]
    assert archived["status"] == "archived"


def test_create_tool_requires_explicit_name_schema() -> None:
    schema = PROJECT_STATE_TOOLS[0]["parameters"]
    assert "name" in schema["required"]
    assert schema["additionalProperties"] is False


def test_update_tool_requires_all_nullable_fields_for_strict_calling() -> None:
    tool = next(item for item in PROJECT_STATE_TOOLS if item["name"] == "update_project_state")
    properties = tool["parameters"]["properties"]
    assert set(tool["parameters"]["required"]) == set(properties)
    assert properties["current_stage"]["enum"][-1] is None
