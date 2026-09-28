"""Public project-state functions and Responses API tool schemas."""

from __future__ import annotations

from typing import Any

from .store import ProjectStateStore


_DEFAULT_STORE: ProjectStateStore | None = None


def _store() -> ProjectStateStore:
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = ProjectStateStore()
    return _DEFAULT_STORE


def create_project_state(
    name: str,
    *,
    objective: str | None = None,
    organization_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _store().create_project(
        name=name, objective=objective, organization_context=organization_context
    )


def list_project_states() -> dict[str, Any]:
    return _store().list_projects()


def get_project_state(*, project_id: str | None = None) -> dict[str, Any]:
    return _store().get_project(project_id=project_id)


def select_project_state(project_id: str) -> dict[str, Any]:
    return _store().select_project(project_id=project_id)


def update_project_state(**kwargs: Any) -> dict[str, Any]:
    return _store().update_project(**kwargs)


def archive_project_state(project_id: str) -> dict[str, Any]:
    return _store().archive_project(project_id=project_id)


ORGANIZATION_SCHEMA = {
    "type": ["object", "null"],
    "properties": {
        "industry": {"type": ["string", "null"]},
        "employee_count": {"type": ["integer", "null"], "minimum": 0},
        "location": {"type": ["string", "null"]},
        "development_stage": {"type": ["string", "null"]},
    },
    "required": ["industry", "employee_count", "location", "development_stage"],
    "additionalProperties": False,
}


CREATE_PROJECT_STATE_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "create_project_state",
    "description": (
        "仅当用户明确要求创建一个 HR 咨询项目时使用。保存项目名称、目标和组织背景，"
        "并将新项目设为当前项目；不要从普通问答自动创建。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "objective": {"type": ["string", "null"]},
            "organization_context": ORGANIZATION_SCHEMA,
        },
        "required": ["name", "objective", "organization_context"],
        "additionalProperties": False,
    },
}


LIST_PROJECT_STATES_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "list_project_states",
    "description": "当用户询问有哪些 HR 咨询项目或需要选择项目时，列出项目摘要。",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
}


GET_PROJECT_STATE_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "get_project_state",
    "description": (
        "读取明确 project_id 或当前选中的项目 State。用户说“继续当前项目”或"
        "“基于当前项目”时使用；State 只是用户确认的项目上下文。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {"project_id": {"type": ["string", "null"]}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
}


SELECT_PROJECT_STATE_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "select_project_state",
    "description": "当用户明确要求切换到某个非归档项目时，按准确 project_id 设为当前项目。",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
}


UPDATE_PROJECT_STATE_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "update_project_state",
    "description": (
        "仅当用户明确要求保存或更新当前项目上下文时使用。可更新项目目标/阶段/组织背景，"
        "追加用户确认事实、待补问题和决定，或设置文件引用；不要保存模型假设和建议。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {"type": ["string", "null"]},
            "name": {"type": ["string", "null"]},
            "objective": {"type": ["string", "null"]},
            "current_stage": {
                "type": ["string", "null"],
                "enum": [
                    "discovery",
                    "diagnosis",
                    "design",
                    "implementation",
                    "review",
                    None,
                ],
            },
            "organization_context": ORGANIZATION_SCHEMA,
            "add_confirmed_facts": {"type": ["array", "null"], "items": {"type": "string"}},
            "add_open_questions": {"type": ["array", "null"], "items": {"type": "string"}},
            "resolve_open_questions": {"type": ["array", "null"], "items": {"type": "string"}},
            "add_decisions": {"type": ["array", "null"], "items": {"type": "string"}},
            "selected_document_ids": {"type": ["array", "null"], "items": {"type": "string"}},
            "selected_data_files": {"type": ["array", "null"], "items": {"type": "string"}},
        },
        "required": [
            "project_id",
            "name",
            "objective",
            "current_stage",
            "organization_context",
            "add_confirmed_facts",
            "add_open_questions",
            "resolve_open_questions",
            "add_decisions",
            "selected_document_ids",
            "selected_data_files",
        ],
        "additionalProperties": False,
    },
}


ARCHIVE_PROJECT_STATE_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "archive_project_state",
    "description": (
        "当用户明确要求归档一个项目时使用。归档只改变状态并保留记录，不删除任何项目数据。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
}


PROJECT_STATE_TOOLS = [
    CREATE_PROJECT_STATE_TOOL,
    LIST_PROJECT_STATES_TOOL,
    GET_PROJECT_STATE_TOOL,
    SELECT_PROJECT_STATE_TOOL,
    UPDATE_PROJECT_STATE_TOOL,
    ARCHIVE_PROJECT_STATE_TOOL,
]
