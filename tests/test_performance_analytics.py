"""Unit tests for performance summaries."""

from src.analytics.performance import analyze_performance_summary


DATA = [
    {"department": "销售部", "position": "客户经理", "score": 3.0},
    {"department": "销售部", "position": "客户经理", "score": "4.0"},
    {"department": "技术部", "position": "工程师", "score": None},
]


def test_performance_normal_missing_and_boundary_values() -> None:
    result = analyze_performance_summary(DATA, "score")

    assert result["valid_count"] == 2
    assert result["mean"] == 3.5
    assert result["median"] == 3.5
    assert result["min"] == 3
    assert result["max"] == 4
    assert result["missing_count"] == 1


def test_performance_grouped_statistics() -> None:
    result = analyze_performance_summary(DATA, "score", "department")

    assert result["groups"]["销售部"]["valid_count"] == 2
    assert result["groups"]["技术部"]["valid_count"] == 0
    assert result["groups"]["技术部"]["mean"] is None


def test_performance_empty_and_missing_fields() -> None:
    assert analyze_performance_summary([], "score")["error"]["code"] == "empty_data"
    assert analyze_performance_summary(DATA, "rating")["error"]["code"] == "field_not_found"
    assert (
        analyze_performance_summary(DATA, "score", "grade")["error"]["code"]
        == "field_not_found"
    )


def test_performance_invalid_and_all_missing_values() -> None:
    invalid = analyze_performance_summary([{"score": "A"}], "score")
    missing = analyze_performance_summary([{"score": None}], "score")

    assert invalid["error"]["code"] == "invalid_numeric_data"
    assert missing["error"]["code"] == "all_values_missing"


def test_performance_single_sample_warning() -> None:
    result = analyze_performance_summary([{"score": 5}], "score")

    assert result["valid_count"] == 1
    assert "sample_size_warning" in result
