"""Descriptive performance-score statistics without employee labeling."""

from __future__ import annotations

from typing import Any

from ._common import (
    group_records,
    numeric_summary,
    numeric_values,
    prepare_records,
    require_field,
)


def analyze_performance_summary(
    data: list[dict[str, Any]],
    performance_field: str,
    group_by: str | None = None,
) -> dict[str, Any]:
    """Summarize valid performance scores overall or by a field."""
    records, validation_error = prepare_records(data)
    if validation_error:
        return validation_error
    if field_error := require_field(records, performance_field):
        return field_error
    if group_by is not None and (field_error := require_field(records, group_by)):
        return field_error

    all_values, total_missing, numeric_error = numeric_values(records, performance_field)
    if numeric_error:
        return numeric_error
    if not all_values:
        return {
            "success": False,
            "error": {
                "code": "all_values_missing",
                "message": f"字段“{performance_field}”没有可用于统计的有效数值。",
            },
            "field": performance_field,
            "missing_count": total_missing,
        }

    base: dict[str, Any] = {
        "success": True,
        "metric": performance_field,
        "total_rows": len(records),
        "missing_handling": "缺失绩效分数不参与数值统计，不自动填补或删除员工记录。",
        "calculation": "对有效数值计算 mean、median、min、max 和有效样本数。",
    }
    if group_by is None:
        base.update(numeric_summary(all_values, total_missing))
        base["valid_count"] = base.pop("count")
        return base

    groups: dict[str, dict[str, Any]] = {}
    for group_name, group in group_records(records, group_by).items():
        values, missing_count, group_error = numeric_values(group, performance_field)
        if group_error:
            group_error["group"] = group_name
            return group_error
        summary = numeric_summary(values, missing_count)
        summary["valid_count"] = summary.pop("count")
        summary["total_rows"] = len(group)
        groups[group_name] = summary
    base.update({"group_by": group_by, "groups": groups})
    return base


ANALYZE_PERFORMANCE_SUMMARY_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "analyze_performance_summary",
    "description": (
        "读取用户指定的 .xlsx 后，对绩效评分计算平均值、中位数、最小值、最大值、"
        "有效样本数和缺失数，可按 department 或 position 分组。不得评价个人绩效。"
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
            "performance_field": {
                "type": "string",
                "description": "绩效评分字段名，例如 performance_score。",
            },
            "group_by": {
                "type": ["string", "null"],
                "enum": ["department", "position", None],
                "description": "可选分组字段，例如 department 或 position。",
            },
        },
        "required": ["file_path", "sheet_name", "performance_field", "group_by"],
        "additionalProperties": False,
    },
}
