"""Basic turnover counts with optional reuse of the V0.2 rate tool."""

from __future__ import annotations

import math
from typing import Any

from src.tools.turnover import TurnoverRateInputError, calculate_turnover_rate

from ._common import group_key, is_missing, prepare_records, require_field


ACTIVE_STATUSES = {"在职", "active", "employed", "试用"}
LEAVER_STATUSES = {"离职", "terminated", "resigned", "separated", "inactive"}


def _normalized_status(value: Any) -> str | None:
    if is_missing(value):
        return None
    if not isinstance(value, str):
        return "__INVALID_TYPE__"
    return value.strip().lower()


def calculate_turnover_analysis(
    data: list[dict[str, Any]],
    status_field: str = "employment_status",
    department_field: str = "department",
    hire_date_field: str | None = "hire_date",
    termination_date_field: str | None = "termination_date",
    average_headcount: float | None = None,
    starting_headcount: int | None = None,
    ending_headcount: int | None = None,
) -> dict[str, Any]:
    """Count active/leaver records and optionally calculate an overall rate."""
    records, validation_error = prepare_records(data)
    if validation_error:
        return validation_error
    required_fields = [status_field, department_field]
    optional_fields = [hire_date_field, termination_date_field]
    for field in [*required_fields, *(item for item in optional_fields if item)]:
        if field_error := require_field(records, field):
            return field_error

    if average_headcount is not None and (
        isinstance(average_headcount, bool)
        or not isinstance(average_headcount, (int, float))
        or not math.isfinite(float(average_headcount))
        or average_headcount <= 0
    ):
        return {
            "success": False,
            "error": {
                "code": "invalid_headcount_basis",
                "message": "average_headcount 必须是大于 0 的有限数值。",
            },
        }
    for field, value in (
        ("starting_headcount", starting_headcount),
        ("ending_headcount", ending_headcount),
    ):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            return {
                "success": False,
                "error": {
                    "code": "invalid_headcount_basis",
                    "message": f"{field} 必须是大于或等于 0 的整数。",
                },
            }

    active_count = 0
    leaver_count = 0
    unknown_status_count = 0
    invalid_status_count = 0
    leavers_by_department: dict[str, int] = {}
    leaver_rows: list[dict[str, Any]] = []
    for row in records:
        status = _normalized_status(row.get(status_field))
        if status in ACTIVE_STATUSES:
            active_count += 1
        elif status in LEAVER_STATUSES:
            leaver_count += 1
            leaver_rows.append(row)
            department = group_key(row.get(department_field))
            leavers_by_department[department] = leavers_by_department.get(department, 0) + 1
        elif status == "__INVALID_TYPE__":
            invalid_status_count += 1
        else:
            unknown_status_count += 1

    if invalid_status_count:
        return {
            "success": False,
            "error": {
                "code": "invalid_status_data",
                "message": f"字段“{status_field}”包含 {invalid_status_count} 个非文本状态值。",
            },
            "field": status_field,
        }

    result: dict[str, Any] = {
        "success": True,
        "total_rows": len(records),
        "active_count": active_count,
        "leaver_count": leaver_count,
        "unknown_status_count": unknown_status_count,
        "leavers_by_department": leavers_by_department,
        "status_mapping": {
            "active": sorted(ACTIVE_STATUSES),
            "leaver": sorted(LEAVER_STATUSES),
        },
    }
    if hire_date_field:
        result["hire_date_present_count"] = sum(
            1 for row in records if not is_missing(row.get(hire_date_field))
        )
    if termination_date_field:
        result["termination_date_present_for_leavers"] = sum(
            1 for row in leaver_rows if not is_missing(row.get(termination_date_field))
        )

    can_calculate_rate = average_headcount is not None or (
        starting_headcount is not None and ending_headcount is not None
    )
    if can_calculate_rate:
        try:
            result["turnover_rate"] = calculate_turnover_rate(
                leavers=leaver_count,
                average_headcount=average_headcount,
                starting_headcount=starting_headcount,
                ending_headcount=ending_headcount,
            )
        except TurnoverRateInputError as exc:
            return {
                "success": False,
                "error": {"code": "invalid_headcount_basis", "message": str(exc)},
                "confirmed_statistics": result,
            }
    else:
        result["turnover_rate"] = None
        result["turnover_rate_unavailable_reason"] = (
            "未提供平均员工人数，或完整的期初与期末人数；不推测离职率。"
        )
        if starting_headcount is not None or ending_headcount is not None:
            result["headcount_input_warning"] = "期初和期末人数必须同时提供。"
    return result


CALCULATE_TURNOVER_ANALYSIS_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "calculate_turnover_analysis",
    "description": (
        "读取用户指定的 .xlsx 后，统计离职人数、在职人数和各部门离职人数。只有用户"
        "另行提供平均人数，或同时提供期初与期末人数时，才复用 calculate_turnover_rate"
        " 计算整体离职率；不得从快照人数猜测平均人数。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "本地 .xlsx 文件路径。"},
            "sheet_name": {"type": ["string", "null"], "description": "指定 Sheet。"},
            "status_field": {"type": "string", "description": "在职状态字段名。"},
            "department_field": {"type": "string", "description": "部门字段名。"},
            "hire_date_field": {
                "type": ["string", "null"],
                "description": "入职日期字段；没有或不使用时传 null。",
            },
            "termination_date_field": {
                "type": ["string", "null"],
                "description": "离职日期字段；没有或不使用时传 null。",
            },
            "average_headcount": {
                "type": ["number", "null"],
                "exclusiveMinimum": 0,
                "description": "用户提供的平均员工人数；未提供时传 null。",
            },
            "starting_headcount": {
                "type": ["integer", "null"],
                "minimum": 0,
                "description": "用户提供的期初人数；未提供时传 null。",
            },
            "ending_headcount": {
                "type": ["integer", "null"],
                "minimum": 0,
                "description": "用户提供的期末人数；未提供时传 null。",
            },
        },
        "required": [
            "file_path",
            "sheet_name",
            "status_field",
            "department_field",
            "hire_date_field",
            "termination_date_field",
            "average_headcount",
            "starting_headcount",
            "ending_headcount",
        ],
        "additionalProperties": False,
    },
}
