"""Atomic JSON persistence for explicit HR consulting project state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.knowledge.knowledge_reader import redact_sensitive_text

from .models import (
    PROJECT_STAGES,
    ProjectState,
    ProjectStateValidationError,
    validate_organization_context,
    validate_string_list,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_ROOT = PROJECT_ROOT / "state"
STATE_SCHEMA_VERSION = 1


class ProjectStateStoreError(RuntimeError):
    """The state file could not be safely read or written."""


def _error(code: str, message: str, **details: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "error": {"code": code, "message": message},
    }
    result.update(details)
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sensitive_labels(value: Any) -> list[str]:
    labels: list[str] = []
    if isinstance(value, str):
        _, detected = redact_sensitive_text(value)
        labels.extend(detected)
    elif isinstance(value, list):
        for item in value:
            labels.extend(_sensitive_labels(item))
    elif isinstance(value, dict):
        for item in value.values():
            labels.extend(_sensitive_labels(item))
    return sorted(set(labels))


def _merge_unique(existing: list[str], additions: list[str]) -> list[str]:
    result = list(existing)
    for item in additions:
        if item not in result:
            result.append(item)
    return result


class ProjectStateStore:
    """Persist only user-authorized project context, never chat transcripts."""

    def __init__(self, root: str | Path = DEFAULT_STATE_ROOT) -> None:
        self.root = Path(root).expanduser()
        self.path = self.root / "projects.json"

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {
            "schema_version": STATE_SCHEMA_VERSION,
            "active_project_id": None,
            "projects": [],
        }

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProjectStateStoreError(
                f"项目 State 文件无法读取：{type(exc).__name__}。"
            ) from exc
        if not isinstance(value, dict):
            raise ProjectStateStoreError("项目 State 文件格式无效。")
        if value.get("schema_version") != STATE_SCHEMA_VERSION:
            raise ProjectStateStoreError("项目 State schema_version 不受支持。")
        if not isinstance(value.get("projects"), list):
            raise ProjectStateStoreError("项目 State 的 projects 必须是列表。")
        active_id = value.get("active_project_id")
        if active_id is not None and not isinstance(active_id, str):
            raise ProjectStateStoreError("项目 State 的 active_project_id 无效。")
        try:
            projects = [ProjectState.from_dict(item).to_dict() for item in value["projects"]]
        except (ProjectStateValidationError, TypeError) as exc:
            raise ProjectStateStoreError(f"项目 State 内容无效：{exc}") from exc
        ids = [item["project_id"] for item in projects]
        if len(ids) != len(set(ids)):
            raise ProjectStateStoreError("项目 State 存在重复 project_id。")
        if active_id is not None:
            active = next((item for item in projects if item["project_id"] == active_id), None)
            if active is None or active["status"] != "active":
                raise ProjectStateStoreError("active_project_id 未指向可用的 active 项目。")
        return {**value, "projects": projects}

    def _write(self, value: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        try:
            temporary.write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError as exc:
            raise ProjectStateStoreError(
                f"项目 State 写入失败：{type(exc).__name__}。"
            ) from exc

    @staticmethod
    def _select_project(data: dict[str, Any], project_id: str | None) -> dict[str, Any]:
        if project_id is not None:
            if not isinstance(project_id, str) or not project_id.strip():
                raise ProjectStateValidationError("project_id 必须是非空字符串。")
            selected_id = project_id.strip()
        else:
            selected_id = data.get("active_project_id")
        if not selected_id:
            raise ProjectStateValidationError("当前没有选中的项目，请先创建或选择项目。")
        project = next(
            (item for item in data["projects"] if item["project_id"] == selected_id), None
        )
        if project is None:
            raise ProjectStateValidationError("没有找到指定 project_id。")
        return project

    def create_project(
        self,
        *,
        name: str,
        objective: str | None = None,
        organization_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            now = _now()
            template = ProjectState.from_dict(
                {
                    "project_id": "TEMP",
                    "name": name,
                    "objective": "" if objective is None else objective,
                    "status": "active",
                    "current_stage": "discovery",
                    "organization_context": (
                        {} if organization_context is None else organization_context
                    ),
                    "confirmed_facts": [],
                    "open_questions": [],
                    "decisions": [],
                    "selected_document_ids": [],
                    "selected_data_files": [],
                    "created_at": now,
                    "updated_at": now,
                }
            )
        except ProjectStateValidationError as exc:
            return _error("invalid_project", str(exc))
        labels = _sensitive_labels(
            [template.name, template.objective, template.organization_context]
        )
        if labels:
            return _error(
                "sensitive_state_content",
                "项目 State 不保存员工级敏感信息，请先匿名化。",
                detected_sensitive_types=labels,
            )
        try:
            data = self._read()
            duplicate = next(
                (
                    item
                    for item in data["projects"]
                    if item["status"] == "active"
                    and item["name"].casefold() == template.name.casefold()
                ),
                None,
            )
            if duplicate:
                return _error(
                    "duplicate_project_name",
                    "已存在同名 active 项目，请选择该项目或使用不同名称。",
                    existing_project_id=duplicate["project_id"],
                )
            project = ProjectState(
                **{
                    **template.to_dict(),
                    "project_id": f"PRJ-{uuid4().hex[:12].upper()}",
                }
            )
            data["projects"].append(project.to_dict())
            data["active_project_id"] = project.project_id
            self._write(data)
        except ProjectStateStoreError as exc:
            return _error("state_store_error", str(exc))
        return {"success": True, "status": "created", "project": project.to_dict()}

    def list_projects(self) -> dict[str, Any]:
        try:
            data = self._read()
        except ProjectStateStoreError as exc:
            return _error("state_store_error", str(exc))
        projects = sorted(data["projects"], key=lambda item: item["updated_at"], reverse=True)
        return {
            "success": True,
            "count": len(projects),
            "active_project_id": data.get("active_project_id"),
            "projects": [
                {
                    "project_id": item["project_id"],
                    "name": item["name"],
                    "objective": item["objective"],
                    "status": item["status"],
                    "current_stage": item["current_stage"],
                    "updated_at": item["updated_at"],
                    "is_selected": item["project_id"] == data.get("active_project_id"),
                }
                for item in projects
            ],
        }

    def get_project(self, *, project_id: str | None = None) -> dict[str, Any]:
        try:
            data = self._read()
            project = self._select_project(data, project_id)
        except ProjectStateStoreError as exc:
            return _error("state_store_error", str(exc))
        except ProjectStateValidationError as exc:
            return _error("project_not_found", str(exc))
        return {
            "success": True,
            "project": project,
            "is_selected": project["project_id"] == data.get("active_project_id"),
            "evidence_note": "项目 State 是用户确认的 PROJECT_CONTEXT，不等于外部核验事实。",
        }

    def select_project(self, *, project_id: str) -> dict[str, Any]:
        try:
            data = self._read()
            project = self._select_project(data, project_id)
            if project["status"] == "archived":
                return _error("project_archived", "归档项目不能设为当前项目。")
            data["active_project_id"] = project_id
            self._write(data)
        except ProjectStateStoreError as exc:
            return _error("state_store_error", str(exc))
        except ProjectStateValidationError as exc:
            return _error("project_not_found", str(exc))
        return {"success": True, "status": "selected", "project": project}

    def update_project(
        self,
        *,
        project_id: str | None = None,
        name: str | None = None,
        objective: str | None = None,
        current_stage: str | None = None,
        organization_context: dict[str, Any] | None = None,
        add_confirmed_facts: list[str] | None = None,
        add_open_questions: list[str] | None = None,
        resolve_open_questions: list[str] | None = None,
        add_decisions: list[str] | None = None,
        selected_document_ids: list[str] | None = None,
        selected_data_files: list[str] | None = None,
    ) -> dict[str, Any]:
        changes = {
            "name": name,
            "objective": objective,
            "current_stage": current_stage,
            "organization_context": organization_context,
            "add_confirmed_facts": add_confirmed_facts,
            "add_open_questions": add_open_questions,
            "resolve_open_questions": resolve_open_questions,
            "add_decisions": add_decisions,
            "selected_document_ids": selected_document_ids,
            "selected_data_files": selected_data_files,
        }
        if all(value is None for value in changes.values()):
            return _error("no_changes", "没有提供任何项目 State 变更。")
        labels = _sensitive_labels(changes)
        if labels:
            return _error(
                "sensitive_state_content",
                "项目 State 不保存员工级敏感信息，请先匿名化。",
                detected_sensitive_types=labels,
            )
        try:
            data = self._read()
            current = self._select_project(data, project_id)
            if current["status"] == "archived":
                return _error("project_archived", "归档项目不能更新。")
            updated = dict(current)
            if name is not None:
                if not isinstance(name, str) or not name.strip():
                    raise ProjectStateValidationError("name 不能为空。")
                updated["name"] = name.strip()
            if objective is not None:
                if not isinstance(objective, str):
                    raise ProjectStateValidationError("objective 必须是字符串。")
                updated["objective"] = objective.strip()
            if current_stage is not None:
                if current_stage not in PROJECT_STAGES:
                    raise ProjectStateValidationError(
                        f"current_stage 必须是：{', '.join(PROJECT_STAGES)}。"
                    )
                updated["current_stage"] = current_stage
            if organization_context is not None:
                context = validate_organization_context(organization_context)
                updated["organization_context"] = {
                    **updated["organization_context"],
                    **{key: value for key, value in context.items() if value is not None},
                }
            for field_name, additions in (
                ("confirmed_facts", add_confirmed_facts),
                ("open_questions", add_open_questions),
                ("decisions", add_decisions),
            ):
                if additions is not None:
                    updated[field_name] = _merge_unique(
                        updated[field_name], validate_string_list(additions, field_name)
                    )
            if resolve_open_questions is not None:
                resolved = set(validate_string_list(resolve_open_questions, "resolve_open_questions"))
                updated["open_questions"] = [
                    item for item in updated["open_questions"] if item not in resolved
                ]
            if selected_document_ids is not None:
                updated["selected_document_ids"] = validate_string_list(
                    selected_document_ids, "selected_document_ids"
                )
            if selected_data_files is not None:
                updated["selected_data_files"] = validate_string_list(
                    selected_data_files, "selected_data_files"
                )
            updated["updated_at"] = _now()
            validated = ProjectState.from_dict(updated).to_dict()
            data["projects"] = [
                validated if item["project_id"] == validated["project_id"] else item
                for item in data["projects"]
            ]
            self._write(data)
        except ProjectStateStoreError as exc:
            return _error("state_store_error", str(exc))
        except ProjectStateValidationError as exc:
            return _error("invalid_update", str(exc))
        return {"success": True, "status": "updated", "project": validated}

    def archive_project(self, *, project_id: str) -> dict[str, Any]:
        try:
            data = self._read()
            project = self._select_project(data, project_id)
            if project["status"] == "archived":
                return _error("project_archived", "项目已经归档。")
            archived = {**project, "status": "archived", "updated_at": _now()}
            data["projects"] = [
                archived if item["project_id"] == project_id else item
                for item in data["projects"]
            ]
            if data.get("active_project_id") == project_id:
                data["active_project_id"] = None
            self._write(data)
        except ProjectStateStoreError as exc:
            return _error("state_store_error", str(exc))
        except ProjectStateValidationError as exc:
            return _error("project_not_found", str(exc))
        return {
            "success": True,
            "status": "archived",
            "project": archived,
            "deleted": False,
        }
