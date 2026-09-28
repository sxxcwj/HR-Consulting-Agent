"""Shared validation helpers for deterministic descriptive analytics."""

from __future__ import annotations

import math
from collections.abc import Mapping
from decimal import Decimal
from statistics import mean, median
from typing import Any


Record = dict[str, Any]
AnalysisResult = dict[str, Any]


def error(code: str, message: str, **details: Any) -> AnalysisResult:
    result: AnalysisResult = {
        "success": False,
        "error": {"code": code, "message": message},
    }
    result.update(details)
    return result


def is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def prepare_records(data: list[dict[str, Any]]) -> tuple[list[Record], AnalysisResult | None]:
    if not isinstance(data, list):
        return [], error("invalid_data", "员工数据必须是记录列表。")
    if not data:
        return [], error("empty_data", "员工数据为空，无法执行统计。")
    if any(not isinstance(row, Mapping) for row in data):
        return [], error("invalid_data", "每条员工数据必须是字段到值的映射。")
    return [dict(row) for row in data], None


def available_fields(records: list[Record]) -> list[str]:
    fields: list[str] = []
    seen: set[str] = set()
    for row in records:
        for field in row:
            if field not in seen:
                seen.add(field)
                fields.append(field)
    return fields


def require_field(records: list[Record], field: str) -> AnalysisResult | None:
    if field not in available_fields(records):
        return error(
            "field_not_found",
            f"字段不存在：{field}。",
            available_fields=available_fields(records),
        )
    return None


def group_key(value: Any) -> str:
    return "（缺失）" if is_missing(value) else str(value)


def group_records(records: list[Record], field: str) -> dict[str, list[Record]]:
    groups: dict[str, list[Record]] = {}
    for row in records:
        groups.setdefault(group_key(row.get(field)), []).append(row)
    return groups


def numeric_values(
    records: list[Record],
    field: str,
) -> tuple[list[float], int, AnalysisResult | None]:
    values: list[float] = []
    missing_count = 0
    invalid_count = 0
    for row in records:
        value = row.get(field)
        if is_missing(value):
            missing_count += 1
            continue
        if isinstance(value, bool):
            invalid_count += 1
            continue
        if isinstance(value, (int, float, Decimal)):
            number = float(value)
        elif isinstance(value, str):
            try:
                number = float(value.strip().replace(",", ""))
            except ValueError:
                invalid_count += 1
                continue
        else:
            invalid_count += 1
            continue
        if not math.isfinite(number):
            invalid_count += 1
            continue
        values.append(number)

    if invalid_count:
        return [], missing_count, error(
            "invalid_numeric_data",
            f"字段“{field}”包含 {invalid_count} 个无法转换为有限数值的非缺失值。",
            field=field,
            invalid_count=invalid_count,
        )
    return values, missing_count, None


def display_number(value: float) -> int | float:
    rounded = round(value, 2)
    return int(rounded) if rounded.is_integer() else rounded


def numeric_summary(values: list[float], missing_count: int) -> AnalysisResult:
    count = len(values)
    if not count:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "missing_count": missing_count,
            "sample_size_warning": "没有有效数值，无法计算统计量。",
        }
    summary: AnalysisResult = {
        "count": count,
        "mean": display_number(mean(values)),
        "median": display_number(median(values)),
        "min": display_number(min(values)),
        "max": display_number(max(values)),
        "missing_count": missing_count,
    }
    if count < 2:
        summary["sample_size_warning"] = "有效样本量小于 2，结果仅描述该单条记录。"
    return summary
