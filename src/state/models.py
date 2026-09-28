"""Data model and validation for explicit V0.7 project state."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


PROJECT_STAGES = ("discovery", "diagnosis", "design", "implementation", "review")
PROJECT_STATUSES = ("active", "archived")
ORGANIZATION_FIELDS = ("industry", "employee_count", "location", "development_stage")


class ProjectStateValidationError(ValueError):
    """A project state value violates the V0.7 contract."""


def _validate_short_text(value: Any, field_name: str, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ProjectStateValidationError(f"{field_name} 必须是字符串。")
    normalized = value.strip()
    if required and not normalized:
        raise ProjectStateValidationError(f"{field_name} 不能为空。")
    if len(normalized) > 2000:
        raise ProjectStateValidationError(f"{field_name} 不能超过 2000 个字符。")
    return normalized


def validate_string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ProjectStateValidationError(f"{field_name} 必须是字符串列表。")
    result: list[str] = []
    for item in value:
        normalized = _validate_short_text(item, field_name, required=True)
        if normalized not in result:
            result.append(normalized)
    if len(result) > 100:
        raise ProjectStateValidationError(f"{field_name} 单次最多包含 100 项。")
    return result


def validate_organization_context(value: Any) -> dict[str, str | int | None]:
    if not isinstance(value, dict):
        raise ProjectStateValidationError("organization_context 必须是对象。")
    unknown = sorted(set(value) - set(ORGANIZATION_FIELDS))
    if unknown:
        raise ProjectStateValidationError(
            f"organization_context 包含不支持的字段：{', '.join(unknown)}。"
        )
    result: dict[str, str | int | None] = {
        field_name: None for field_name in ORGANIZATION_FIELDS
    }
    for key, item in value.items():
        if key == "employee_count":
            if item is not None and (
                isinstance(item, bool) or not isinstance(item, int) or item < 0
            ):
                raise ProjectStateValidationError("employee_count 必须是大于或等于 0 的整数。")
            result[key] = item
        elif item is None:
            result[key] = None
        else:
            result[key] = _validate_short_text(item, key)
    return result


@dataclass(frozen=True)
class ProjectState:
    project_id: str
    name: str
    objective: str
    status: str
    current_stage: str
    organization_context: dict[str, str | int | None]
    confirmed_facts: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    selected_document_ids: list[str] = field(default_factory=list)
    selected_data_files: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProjectState":
        try:
            project_id = _validate_short_text(value["project_id"], "project_id", required=True)
            name = _validate_short_text(value["name"], "name", required=True)
            objective = _validate_short_text(value.get("objective", ""), "objective")
            status = value["status"]
            current_stage = value["current_stage"]
            if status not in PROJECT_STATUSES:
                raise ProjectStateValidationError("status 必须是 active 或 archived。")
            if current_stage not in PROJECT_STAGES:
                raise ProjectStateValidationError(
                    f"current_stage 必须是：{', '.join(PROJECT_STAGES)}。"
                )
            return cls(
                project_id=project_id,
                name=name,
                objective=objective,
                status=status,
                current_stage=current_stage,
                organization_context=validate_organization_context(
                    value.get("organization_context", {})
                ),
                confirmed_facts=validate_string_list(
                    value.get("confirmed_facts", []), "confirmed_facts"
                ),
                open_questions=validate_string_list(
                    value.get("open_questions", []), "open_questions"
                ),
                decisions=validate_string_list(value.get("decisions", []), "decisions"),
                selected_document_ids=validate_string_list(
                    value.get("selected_document_ids", []), "selected_document_ids"
                ),
                selected_data_files=validate_string_list(
                    value.get("selected_data_files", []), "selected_data_files"
                ),
                created_at=_validate_short_text(
                    value.get("created_at", ""), "created_at", required=True
                ),
                updated_at=_validate_short_text(
                    value.get("updated_at", ""), "updated_at", required=True
                ),
            )
        except KeyError as exc:
            raise ProjectStateValidationError(f"项目状态缺少字段：{exc.args[0]}。") from exc
