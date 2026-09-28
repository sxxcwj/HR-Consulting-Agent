"""Missing-data statistics that never modify source records."""

from __future__ import annotations

from typing import Any

from ._common import available_fields, is_missing, prepare_records


def analyze_missing_data(
    data: list[dict[str, Any]],
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """Count missing values and rates for selected or all fields."""
    records, validation_error = prepare_records(data)
    if validation_error:
        return validation_error

    existing_fields = available_fields(records)
    selected_fields = existing_fields if fields is None else fields
    if not selected_fields:
        return {
            "success": False,
            "error": {"code": "no_fields", "message": "没有可统计的字段。"},
        }
    missing_fields = [field for field in selected_fields if field not in existing_fields]
    if missing_fields:
        return {
            "success": False,
            "error": {
                "code": "field_not_found",
                "message": f"字段不存在：{', '.join(missing_fields)}。",
            },
            "available_fields": existing_fields,
        }

    total_rows = len(records)
    field_stats = {
        field: {
            "missing_count": sum(1 for row in records if is_missing(row.get(field))),
            "missing_rate": round(
                sum(1 for row in records if is_missing(row.get(field))) / total_rows,
                4,
            ),
        }
        for field in selected_fields
    }
    return {
        "success": True,
        "total_rows": total_rows,
        "fields": field_stats,
        "missing_handling": "只统计缺失，不删除记录、不填补数据、不修改源文件。",
    }


ANALYZE_MISSING_DATA_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "analyze_missing_data",
    "description": (
        "读取用户指定的 .xlsx 后，统计全部或指定字段的缺失数量和缺失比例。"
        "不删除、不填补、不修改任何数据。"
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
            "fields": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "description": "要统计的字段；全部字段时传 null。",
            },
        },
        "required": ["file_path", "sheet_name", "fields"],
        "additionalProperties": False,
    },
}
