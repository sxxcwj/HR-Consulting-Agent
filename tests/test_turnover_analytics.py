"""Unit tests for basic turnover analysis."""

from src.analytics.turnover import calculate_turnover_analysis


DATA = [
    {
        "department": "销售部",
        "employment_status": "离职",
        "hire_date": "2024-01-01",
        "termination_date": "2025-01-01",
    },
    {
        "department": "销售部",
        "employment_status": "在职",
        "hire_date": "2024-02-01",
        "termination_date": None,
    },
    {
        "department": "技术部",
        "employment_status": "active",
        "hire_date": "2024-03-01",
        "termination_date": None,
    },
    {
        "department": "技术部",
        "employment_status": "resigned",
        "hire_date": "2023-01-01",
        "termination_date": "2025-02-01",
    },
]


def test_turnover_counts_without_guessing_rate() -> None:
    result = calculate_turnover_analysis(DATA)

    assert result["leaver_count"] == 2
    assert result["active_count"] == 2
    assert result["leavers_by_department"] == {"销售部": 1, "技术部": 1}
    assert result["turnover_rate"] is None
    assert "不推测离职率" in result["turnover_rate_unavailable_reason"]


def test_turnover_reuses_existing_rate_with_average_headcount() -> None:
    result = calculate_turnover_analysis(DATA, average_headcount=20)

    assert result["turnover_rate"]["turnover_rate"] == 10
    assert result["turnover_rate"]["formula"] == "2 / 20 * 100"


def test_turnover_reuses_existing_rate_with_start_and_end() -> None:
    result = calculate_turnover_analysis(DATA, starting_headcount=30, ending_headcount=20)

    assert result["turnover_rate"]["average_headcount"] == 25
    assert result["turnover_rate"]["turnover_rate"] == 8


def test_turnover_empty_and_missing_fields() -> None:
    assert calculate_turnover_analysis([])["error"]["code"] == "empty_data"
    result = calculate_turnover_analysis(
        [{"department": "销售部"}],
        hire_date_field=None,
        termination_date_field=None,
    )
    assert result["error"]["code"] == "field_not_found"


def test_turnover_invalid_status_type_and_headcount() -> None:
    invalid_status = calculate_turnover_analysis(
        [{"department": "销售部", "employment_status": 1}],
        hire_date_field=None,
        termination_date_field=None,
    )
    invalid_headcount = calculate_turnover_analysis(DATA, average_headcount=-1)

    assert invalid_status["error"]["code"] == "invalid_status_data"
    assert invalid_headcount["error"]["code"] == "invalid_headcount_basis"


def test_turnover_unknown_status_and_partial_headcount_are_explicit() -> None:
    data = [
        {
            "department": "销售部",
            "employment_status": "其他",
            "hire_date": None,
            "termination_date": None,
        }
    ]
    result = calculate_turnover_analysis(data, starting_headcount=10)

    assert result["unknown_status_count"] == 1
    assert result["turnover_rate"] is None
    assert "同时提供" in result["headcount_input_warning"]


def test_turnover_rejects_invalid_partial_headcount() -> None:
    result = calculate_turnover_analysis(DATA, starting_headcount=-1)

    assert result["error"]["code"] == "invalid_headcount_basis"
