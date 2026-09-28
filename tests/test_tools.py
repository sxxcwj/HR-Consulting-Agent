"""Unit tests for the deterministic turnover-rate tool."""

import pytest

from src.tools import TurnoverRateInputError, calculate_turnover_rate


def test_calculates_with_starting_and_ending_headcount() -> None:
    result = calculate_turnover_rate(
        leavers=30,
        starting_headcount=200,
        ending_headcount=180,
    )

    assert result["average_headcount"] == 190
    assert result["average_headcount_source"] == "derived_from_starting_and_ending"
    assert result["turnover_rate"] == 15.79
    assert result["formula"] == "30 / ((200 + 180) / 2) * 100"


def test_calculates_with_provided_average_headcount() -> None:
    result = calculate_turnover_rate(leavers=20, average_headcount=200)

    assert result["average_headcount"] == 200
    assert result["average_headcount_source"] == "provided"
    assert result["turnover_rate"] == 10.0
    assert result["unit"] == "%"


def test_zero_leavers_returns_zero_rate() -> None:
    result = calculate_turnover_rate(leavers=0, average_headcount=200)

    assert result["turnover_rate"] == 0.0


def test_zero_average_headcount_is_rejected() -> None:
    with pytest.raises(TurnoverRateInputError, match="必须大于 0"):
        calculate_turnover_rate(leavers=10, average_headcount=0)


def test_missing_headcount_is_rejected() -> None:
    with pytest.raises(TurnoverRateInputError, match="缺少必要人数"):
        calculate_turnover_rate(leavers=30)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"leavers": -1, "average_headcount": 100}, "leavers"),
        ({"leavers": 1, "starting_headcount": -1, "ending_headcount": 100}, "starting_headcount"),
        ({"leavers": 1, "starting_headcount": 0, "ending_headcount": 0}, "平均员工人数"),
    ],
)
def test_invalid_values_are_rejected(kwargs: dict[str, int], message: str) -> None:
    with pytest.raises(TurnoverRateInputError, match=message):
        calculate_turnover_rate(**kwargs)
