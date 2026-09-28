"""Unit tests for workforce headcount analytics."""

from src.analytics.workforce import calculate_headcount


DATA = [
    {"department": "销售部", "position": "客户经理", "employment_status": "在职"},
    {"department": "销售部", "position": "客户经理", "employment_status": "离职"},
    {"department": "技术部", "position": "工程师", "employment_status": "在职"},
    {"department": None, "position": "工程师", "employment_status": "在职"},
]


def test_headcount_total_and_grouped_counts() -> None:
    total = calculate_headcount(DATA)
    grouped = calculate_headcount(DATA, "department")

    assert total["total_headcount"] == 4
    assert grouped["by_department"] == {"销售部": 2, "技术部": 1, "（缺失）": 1}


def test_headcount_empty_data() -> None:
    assert calculate_headcount([])["error"]["code"] == "empty_data"


def test_headcount_missing_group_field() -> None:
    result = calculate_headcount(DATA, "grade")

    assert result["success"] is False
    assert result["error"]["code"] == "field_not_found"


def test_headcount_invalid_record_type() -> None:
    result = calculate_headcount([{"department": "销售部"}, "bad"])  # type: ignore[list-item]

    assert result["error"]["code"] == "invalid_data"


def test_headcount_single_record_boundary() -> None:
    result = calculate_headcount([{"position": "HRBP"}], "position")

    assert result["total_headcount"] == 1
    assert result["by_position"] == {"HRBP": 1}
