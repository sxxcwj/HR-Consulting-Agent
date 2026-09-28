"""Deterministic employee-turnover-rate function tool."""

from __future__ import annotations

import math
from typing import Any


class TurnoverRateInputError(ValueError):
    """The supplied headcount data cannot produce a turnover rate."""


def _validate_non_negative_int(value: int | None, field: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TurnoverRateInputError(f"{field} 必须是整数。")
    if value < 0:
        raise TurnoverRateInputError(f"{field} 必须大于或等于 0。")


def _validate_average_headcount(value: float | None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TurnoverRateInputError("average_headcount 必须是数字。")
    if not math.isfinite(float(value)) or value <= 0:
        raise TurnoverRateInputError("average_headcount 必须大于 0。")


def _display_number(value: float) -> int | float:
    """Keep formulas readable while preserving non-integral headcounts."""
    return int(value) if value.is_integer() else value


def calculate_turnover_rate(
    *,
    leavers: int,
    average_headcount: float | None = None,
    starting_headcount: int | None = None,
    ending_headcount: int | None = None,
) -> dict[str, int | float | str]:
    """Calculate turnover rate from leavers and an available headcount basis.

    A directly supplied average headcount takes precedence. Otherwise both the
    starting and ending headcounts are required to derive the average.
    """
    _validate_non_negative_int(leavers, "leavers")
    _validate_average_headcount(average_headcount)
    _validate_non_negative_int(starting_headcount, "starting_headcount")
    _validate_non_negative_int(ending_headcount, "ending_headcount")

    if average_headcount is not None:
        resolved_average = float(average_headcount)
        formula = f"{leavers} / {_display_number(resolved_average)} * 100"
        result: dict[str, int | float | str] = {
            "leavers": leavers,
            "average_headcount": _display_number(resolved_average),
            "average_headcount_source": "provided",
            "turnover_rate": round(leavers / resolved_average * 100, 2),
            "unit": "%",
            "formula": formula,
        }
        return result

    if starting_headcount is None or ending_headcount is None:
        raise TurnoverRateInputError(
            "缺少必要人数：请提供 average_headcount，或者同时提供 "
            "starting_headcount 和 ending_headcount。"
        )

    resolved_average = (starting_headcount + ending_headcount) / 2
    if resolved_average <= 0:
        raise TurnoverRateInputError("根据期初和期末人数得到的平均员工人数必须大于 0。")

    return {
        "leavers": leavers,
        "starting_headcount": starting_headcount,
        "ending_headcount": ending_headcount,
        "average_headcount": _display_number(resolved_average),
        "average_headcount_source": "derived_from_starting_and_ending",
        "turnover_rate": round(leavers / resolved_average * 100, 2),
        "unit": "%",
        "formula": (
            f"{leavers} / (({starting_headcount} + {ending_headcount}) / 2) * 100"
        ),
    }


TURNOVER_RATE_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "calculate_turnover_rate",
    "description": (
        "当需要根据离职人数和平均员工人数，或者期初/期末人数，计算员工离职率时"
        "使用此工具。不要自己估算离职率。只有 leavers 与 average_headcount 均已提供，"
        "或者 leavers、starting_headcount、ending_headcount 均已提供时才调用。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "leavers": {
                "type": "integer",
                "minimum": 0,
                "description": "统计期间离职人数。",
            },
            "average_headcount": {
                "type": ["number", "null"],
                "exclusiveMinimum": 0,
                "description": "统计期间平均员工人数；未提供时传 null。",
            },
            "starting_headcount": {
                "type": ["integer", "null"],
                "minimum": 0,
                "description": "统计期期初员工人数；未提供时传 null。",
            },
            "ending_headcount": {
                "type": ["integer", "null"],
                "minimum": 0,
                "description": "统计期期末员工人数；未提供时传 null。",
            },
        },
        "required": [
            "leavers",
            "average_headcount",
            "starting_headcount",
            "ending_headcount",
        ],
        "additionalProperties": False,
    },
}
