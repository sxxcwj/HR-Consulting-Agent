"""Basic workforce headcount statistics."""

from __future__ import annotations

from typing import Any

from ._common import group_records, prepare_records, require_field


def calculate_headcount(
    data: list[dict[str, Any]],
    group_by: str | None = None,
) -> dict[str, Any]:
    """Count employee records overall and optionally by one field."""
    records, validation_error = prepare_records(data)
    if validation_error:
        return validation_error

    result: dict[str, Any] = {
        "success": True,
        "total_headcount": len(records),
        "counting_rule": "每条非空员工记录计为 1 人；未删除或填补记录。",
    }
    if group_by is None:
        return result
    if field_error := require_field(records, group_by):
        return field_error

    counts = {
        name: len(group)
        for name, group in group_records(records, group_by).items()
    }
    result.update(
        {
            "group_by": group_by,
            f"by_{group_by}": counts,
            "groups": counts,
        }
    )
    return result


CALCULATE_HEADCOUNT_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "calculate_headcount",
    "description": (
        "读取用户指定的 .xlsx 后，统计全公司员工人数，或按 department、position、"
        "employment_status 分组统计人数。只返回计数事实，不作管理判断。"
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
            "group_by": {
                "type": ["string", "null"],
                "enum": ["department", "position", "employment_status", None],
                "description": "可选分组字段；统计总人数时传 null。",
            },
        },
        "required": ["file_path", "sheet_name", "group_by"],
        "additionalProperties": False,
    },
}
