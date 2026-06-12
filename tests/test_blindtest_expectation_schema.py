import pytest

from src.reports.blindtest_expectation_schema import (
    BlindtestExpectationSummary,
    MonthlyBlindtestResult,
)


def _valid_monthly_result(month: str = "2026-01", pnl: float = 12.5) -> MonthlyBlindtestResult:
    return MonthlyBlindtestResult(
        month=month,
        pnl=pnl,
        trades=3,
        winning_trades=2,
        losing_trades=1,
        no_trade_decisions=5,
    )


def _valid_summary(**overrides: object) -> BlindtestExpectationSummary:
    values = {
        "run_id": "run_20260612_120000",
        "training_start": "2023-01-01",
        "training_end": "2024-12-30",
        "blindtest_start": "2024-12-31",
        "blindtest_end": "2025-12-30",
        "start_capital": 100.0,
        "final_result": 125.0,
        "total_pnl": 25.0,
        "best_month": "2025-03",
        "worst_month": "2025-08",
        "positive_months": 7,
        "negative_months": 4,
        "neutral_months": 1,
        "expected_monthly_min": -10.0,
        "expected_monthly_max": 20.0,
        "monthly_results": [_valid_monthly_result()],
    }
    values.update(overrides)
    return BlindtestExpectationSummary(**values)


def test_valid_summary_model_can_be_created() -> None:
    summary = _valid_summary()

    assert summary.run_id == "run_20260612_120000"
    assert summary.start_capital == 100.0
    assert len(summary.monthly_results) == 1


def test_negative_final_result_and_total_pnl_are_allowed() -> None:
    summary = _valid_summary(final_result=-50.0, total_pnl=-150.0)

    assert summary.final_result == -50.0
    assert summary.total_pnl == -150.0


def test_negative_monthly_pnl_is_allowed() -> None:
    result = _valid_monthly_result(pnl=-25.0)

    assert result.pnl == -25.0


def test_negative_trades_are_rejected() -> None:
    with pytest.raises(ValueError):
        MonthlyBlindtestResult(
            month="2026-01",
            pnl=0.0,
            trades=-1,
            winning_trades=0,
            losing_trades=0,
            no_trade_decisions=0,
        )


def test_monthly_results_can_contain_multiple_months() -> None:
    monthly_results = [
        _valid_monthly_result(month="2026-01"),
        _valid_monthly_result(month="2026-02", pnl=-5.0),
    ]

    summary = _valid_summary(monthly_results=monthly_results)

    assert len(summary.monthly_results) == 2


def test_run_id_must_be_valid() -> None:
    with pytest.raises(ValueError):
        _valid_summary(run_id="../unsafe")


def test_expected_monthly_range_can_be_none() -> None:
    summary = _valid_summary(expected_monthly_min=None, expected_monthly_max=None)

    assert summary.expected_monthly_min is None
    assert summary.expected_monthly_max is None
