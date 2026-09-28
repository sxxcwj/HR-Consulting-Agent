"""Unit tests for compensation summaries."""

from src.analytics.compensation import analyze_compensation_summary


DATA = [
    {"department": "销售部", "monthly_salary": 6000},
    {"department": "销售部", "monthly_salary": "8000"},
    {"department": "技术部", "monthly_salary": 12000},
    {"department": "技术部", "monthly_salary": None},
]


def test_compensation_normal_and_missing_values() -> None:
    result = analyze_compensation_summary(DATA, "monthly_salary")

    assert result["success"] is True
    assert result["count"] == 3
    assert result["mean"] == 8666.67
    assert result["median"] == 8000
    assert result["min"] == 6000
    assert result["max"] == 12000
    assert result["missing_count"] == 1


def test_compensation_grouped_statistics() -> None:
    result = analyze_compensation_summary(DATA, "monthly_salary", "department")

    assert result["groups"]["销售部"]["mean"] == 7000
    assert result["groups"]["技术部"]["mean"] == 12000
    assert result["groups"]["技术部"]["missing_count"] == 1
    assert "sample_size_warning" in result["groups"]["技术部"]


def test_compensation_empty_data() -> None:
    assert analyze_compensation_summary([], "salary")["error"]["code"] == "empty_data"


def test_compensation_missing_metric_and_group_fields() -> None:
    assert analyze_compensation_summary(DATA, "salary")["error"]["code"] == "field_not_found"
    assert (
        analyze_compensation_summary(DATA, "monthly_salary", "grade")["error"]["code"]
        == "field_not_found"
    )


def test_compensation_invalid_numeric_data() -> None:
    result = analyze_compensation_summary(
        [{"monthly_salary": 6000}, {"monthly_salary": "not-a-number"}],
        "monthly_salary",
    )

    assert result["error"]["code"] == "invalid_numeric_data"


def test_compensation_all_missing_and_single_value_boundaries() -> None:
    missing = analyze_compensation_summary([{"salary": None}], "salary")
    single = analyze_compensation_summary([{"salary": -100}], "salary")

    assert missing["error"]["code"] == "all_values_missing"
    assert single["min"] == -100
    assert "sample_size_warning" in single
