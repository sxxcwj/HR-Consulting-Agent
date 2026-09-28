"""Descriptive compensation statistics without compensation judgments."""

from __future__ import annotations

from typing import Any

from ._common import (
    group_records,
    numeric_summary,
    numeric_values,
    prepare_records,
    require_field,
)


def analyze_compensation_summary(
    data: list[dict[str, Any]],
    salary_field: str,
    group_by: str | None = None,
) -> dict[str, Any]:
    """Calculate count, mean, median, min, and max for a salary field."""
    records, validation_error = prepare_records(data)
    if validation_error:
        return validation_error
    if field_error := require_field(records, salary_field):
        return field_error
    if group_by is not None and (field_error := require_field(records, group_by)):
        return field_error

    all_values, total_missing, numeric_error = numeric_values(records, salary_field)
    if numeric_error:
        return numeric_error
    if not all_values:
        return {
            "success": False,
            "error": {
                "code": "all_values_missing",
                "message": f"字段“{salary_field}”没有可用于统计的有效数值。",
            },
            "field": salary_field,
            "missing_count": total_missing,
        }

    base: dict[str, Any] = {
        "success": True,
        "metric": salary_field,
        "total_rows": len(records),
        "missing_handling": "缺失薪酬不参与数值统计，但保留在总记录数和缺失数量中。",
        "calculation": "对有效数值计算 count、mean、median、min、max。",
    }
    if group_by is None:
        base.update(numeric_summary(all_values, total_missing))
        return base

    groups: dict[str, dict[str, Any]] = {}
    for group_name, group in group_records(records, group_by).items():
        values, missing_count, group_error = numeric_values(group, salary_field)
        if group_error:
            group_error["group"] = group_name
            return group_error
        groups[group_name] = numeric_summary(values, missing_count)
        groups[group_name]["total_rows"] = len(group)
    base.update({"group_by": group_by, "groups": groups})
    return base


ANALYZE_COMPENSATION_SUMMARY_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "analyze_compensation_summary",
    "description": (
        "读取用户指定的 .xlsx 后，对薪酬字段计算 count、mean、median、min、max，"
        "可按部门等字段分组。只返回描述性统计，不判断薪酬是否合理或过高。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "本地 .xlsx 文件路径。"},
            "sheet_name": {
                "type": ["string", "null"],
                "description": "指定 Sheet；单 Sheet 且未指定时传 null。",
            },
            "salary_field": {
                "type": "string",
                "description": "薪酬字段名，例如 monthly_salary。",
            },
            "group_by": {
                "type": ["string", "null"],
                "enum": ["department", "position", "employment_status", None],
                "description": "可选分组字段，例如 department；不分组时传 null。",
            },
        },
        "required": ["file_path", "sheet_name", "salary_field", "group_by"],
        "additionalProperties": False,
    },
}
