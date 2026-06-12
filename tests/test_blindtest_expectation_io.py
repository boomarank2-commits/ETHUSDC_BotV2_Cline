import json

import pytest

from src.common.report_paths import get_run_report_dir
from src.reports.blindtest_expectation_io import (
    BLINDTEST_EXPECTATION_FILENAME,
    load_blindtest_expectation,
    save_blindtest_expectation,
)
from src.reports.blindtest_expectation_schema import (
    BlindtestExpectationSummary,
    MonthlyBlindtestResult,
)


def _monthly_result(month: str = "2026-01", pnl: float = 10.0) -> MonthlyBlindtestResult:
    return MonthlyBlindtestResult(
        month=month,
        pnl=pnl,
        trades=2,
        winning_trades=1,
        losing_trades=1,
        no_trade_decisions=4,
    )


def _summary(
    run_id: str = "run_20260612_130000",
    final_result: float = 110.0,
    total_pnl: float = 10.0,
) -> BlindtestExpectationSummary:
    return BlindtestExpectationSummary(
        run_id=run_id,
        training_start="2023-01-01",
        training_end="2024-12-30",
        blindtest_start="2024-12-31",
        blindtest_end="2025-12-30",
        start_capital=100.0,
        final_result=final_result,
        total_pnl=total_pnl,
        best_month="2025-03",
        worst_month="2025-08",
        positive_months=6,
        negative_months=5,
        neutral_months=1,
        expected_monthly_min=-20.0,
        expected_monthly_max=25.0,
        monthly_results=[
            _monthly_result(month="2025-01", pnl=12.0),
            _monthly_result(month="2025-02", pnl=-8.0),
        ],
    )


def test_save_blindtest_expectation_creates_json_in_run_report_dir() -> None:
    run_id = "run_20260612_130001"
    summary = _summary(run_id=run_id)

    report_path = save_blindtest_expectation(run_id, summary)

    assert report_path == get_run_report_dir(run_id) / BLINDTEST_EXPECTATION_FILENAME
    assert report_path.is_file()


def test_load_blindtest_expectation_loads_same_summary() -> None:
    run_id = "run_20260612_130002"
    summary = _summary(run_id=run_id)

    save_blindtest_expectation(run_id, summary)

    assert load_blindtest_expectation(run_id) == summary


def test_saved_json_contains_monthly_results() -> None:
    run_id = "run_20260612_130003"
    summary = _summary(run_id=run_id)

    report_path = save_blindtest_expectation(run_id, summary)
    raw_summary = json.loads(report_path.read_text(encoding="utf-8"))

    assert "monthly_results" in raw_summary
    assert len(raw_summary["monthly_results"]) == 2


def test_negative_final_result_and_total_pnl_are_preserved() -> None:
    run_id = "run_20260612_130004"
    summary = _summary(run_id=run_id, final_result=-50.0, total_pnl=-150.0)

    save_blindtest_expectation(run_id, summary)
    loaded_summary = load_blindtest_expectation(run_id)

    assert loaded_summary.final_result == -50.0
    assert loaded_summary.total_pnl == -150.0


def test_invalid_run_id_with_path_traversal_is_rejected() -> None:
    with pytest.raises(ValueError):
        save_blindtest_expectation("../unsafe", _summary())


def test_missing_file_is_handled_as_file_not_found_error() -> None:
    with pytest.raises(FileNotFoundError):
        load_blindtest_expectation("run_20260612_139999")
