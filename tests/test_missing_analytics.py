"""Unit tests for missing-data analysis."""

from src.analytics.missing import analyze_missing_data


DATA = [
    {"department": "销售部", "score": 3},
    {"department": "", "score": None},
    {"department": None, "score": 4},
    {"department": "技术部"},
]


def test_missing_data_normal_and_boundary_rates() -> None:
    result = analyze_missing_data(DATA)

    assert result["total_rows"] == 4
    assert result["fields"]["department"] == {
        "missing_count": 2,
        "missing_rate": 0.5,
    }
    assert result["fields"]["score"] == {
        "missing_count": 2,
        "missing_rate": 0.5,
    }


def test_missing_data_selected_fields() -> None:
    result = analyze_missing_data(DATA, ["score"])

    assert list(result["fields"]) == ["score"]


def test_missing_data_empty_and_missing_field() -> None:
    assert analyze_missing_data([])["error"]["code"] == "empty_data"
    assert analyze_missing_data(DATA, ["grade"])["error"]["code"] == "field_not_found"


def test_missing_data_invalid_record_type_and_no_fields() -> None:
    invalid = analyze_missing_data([{"a": 1}, 2])  # type: ignore[list-item]
    no_fields = analyze_missing_data([{}])

    assert invalid["error"]["code"] == "invalid_data"
    assert no_fields["error"]["code"] == "no_fields"


def test_missing_data_does_not_modify_records() -> None:
    original = [dict(row) for row in DATA]

    analyze_missing_data(DATA)

    assert DATA == original
