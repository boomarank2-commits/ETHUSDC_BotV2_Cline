from dataclasses import fields

import pytest

from src.backtest.buy_hold_benchmark import BuyHoldBenchmarkReport, save_buy_hold_benchmark_report
from src.backtest.strategy_v0 import StrategyV0Candidate
from src.backtest.strategy_v0_report import (
    StrategyV0TrainingBlindtestReport,
    save_strategy_v0_report,
)
from src.backtest.strategy_v1 import StrategyV1Candidate
from src.backtest.strategy_v1_report import (
    StrategyV1TrainingBlindtestReport,
    save_strategy_v1_report,
)
from src.data.data_preparation_report import DataPreparationReport, save_data_preparation_report
from src.data.train_blind_split_report import TrainBlindSplitReport, save_train_blind_split_report
from src.reports.backtest_summary import (
    BacktestSummary,
    build_backtest_summary,
    load_backtest_summary,
    save_backtest_summary,
)


def _data_report(run_id: str, usable: bool = True) -> DataPreparationReport:
    return DataPreparationReport(
        run_id=run_id,
        symbol="ETHUSDC",
        interval="1m",
        candle_count=10,
        first_open_time="2026-01-01T00:00:00",
        last_open_time="2026-01-01T00:09:00",
        detected_gaps=0 if usable else 1,
        has_required_lookback=usable,
        usable_for_backtest=usable,
        reason=None if usable else "not enough candles for required lookback",
    )


def _split_report(run_id: str) -> TrainBlindSplitReport:
    return TrainBlindSplitReport(
        run_id=run_id,
        symbol="ETHUSDC",
        interval="1m",
        training_candle_count=3,
        blindtest_candle_count=2,
        training_start="2026-01-01T00:00:00",
        training_end="2026-01-01T00:02:00",
        blindtest_start="2026-01-01T00:03:00",
        blindtest_end="2026-01-01T00:04:00",
        has_overlap=False,
        blindtest_after_training=True,
    )


def _benchmark_report(run_id: str) -> BuyHoldBenchmarkReport:
    return BuyHoldBenchmarkReport(
        run_id=run_id,
        symbol="ETHUSDC",
        quote_asset="USDC",
        start_capital=100.0,
        blindtest_start="2026-01-01T00:03:00",
        blindtest_end="2026-01-01T00:04:00",
        entry_price=100.0,
        exit_price=120.0,
        quantity=1.0,
        final_capital=120.0,
        total_pnl=20.0,
        total_pnl_pct=20.0,
        trade_count=1,
    )


def _save_completed_reports(run_id: str) -> None:
    save_data_preparation_report(_data_report(run_id))
    save_train_blind_split_report(_split_report(run_id))
    save_buy_hold_benchmark_report(_benchmark_report(run_id))


def _strategy_report(run_id: str) -> StrategyV0TrainingBlindtestReport:
    return StrategyV0TrainingBlindtestReport(
        run_id=run_id,
        symbol="ETHUSDC",
        quote_asset="USDC",
        start_capital=100.0,
        selected_candidate=StrategyV0Candidate("selected", 1, 0.001, 0.004, 0.004, 3, 10.0),
        training_final_capital=130.0,
        training_total_pnl=30.0,
        training_total_pnl_pct=30.0,
        training_trade_count=2,
        blindtest_final_capital=111.0,
        blindtest_total_pnl=11.0,
        blindtest_total_pnl_pct=11.0,
        blindtest_trade_count=3,
        blindtest_winning_trades=2,
        blindtest_losing_trades=1,
        blindtest_max_drawdown=4.0,
        blindtest_start="2026-01-01T00:03:00",
        blindtest_end="2026-01-01T00:04:00",
    )


def _strategy_v1_report(run_id: str) -> StrategyV1TrainingBlindtestReport:
    return StrategyV1TrainingBlindtestReport(
        run_id=run_id,
        symbol="ETHUSDC",
        quote_asset="USDC",
        start_capital_reference=100.0,
        stake_usdt=100.0,
        profile="normal",
        selected_candidate=StrategyV1Candidate(
            "momentum_breakout", "v1_selected", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0
        ),
        training_family="momentum_breakout",
        training_final_capital_reference=140.0,
        training_total_net_pnl=40.0,
        training_total_net_pnl_pct=40.0,
        training_usdt_per_day=1.0,
        training_trade_count=4,
        blindtest_final_capital_reference=122.0,
        blindtest_total_net_pnl=22.0,
        blindtest_total_net_pnl_pct=22.0,
        blindtest_usdt_per_day=0.5,
        blindtest_trade_count=5,
        blindtest_winning_trades=3,
        blindtest_losing_trades=2,
        blindtest_neutral_trades=0,
        blindtest_max_drawdown=3.0,
        blindtest_start="2026-01-01T00:03:00",
        blindtest_end="2026-01-01T00:04:00",
        positive_days=2,
        negative_days=1,
        neutral_days=0,
        best_day_pnl=5.0,
        worst_day_pnl=-2.0,
    )


def test_completed_summary_is_built_from_reports() -> None:
    run_id = "run_20260612_210001"
    _save_completed_reports(run_id)

    summary = build_backtest_summary(run_id)

    assert summary.status == "completed"


def test_result_values_come_from_buy_hold_benchmark() -> None:
    run_id = "run_20260612_210002"
    _save_completed_reports(run_id)

    summary = build_backtest_summary(run_id)

    assert summary.final_capital == 120.0
    assert summary.total_pnl == 20.0
    assert summary.total_pnl_pct == 20.0
    assert summary.trade_count == 1


def test_summary_prefers_strategy_v0_over_buy_hold() -> None:
    run_id = "run_20260612_210007"
    _save_completed_reports(run_id)
    save_strategy_v0_report(_strategy_report(run_id))

    summary = build_backtest_summary(run_id)

    assert summary.final_capital == 111.0
    assert summary.total_pnl == 11.0
    assert summary.trade_count == 3
    assert summary.message == "Strategy V0 training+blindtest completed"


def test_summary_prefers_strategy_v1_over_v0_and_buy_hold() -> None:
    run_id = "run_20260612_210008"
    _save_completed_reports(run_id)
    save_strategy_v0_report(_strategy_report(run_id))
    save_strategy_v1_report(_strategy_v1_report(run_id))

    summary = build_backtest_summary(run_id)

    assert summary.final_capital == 122.0
    assert summary.total_pnl == 22.0
    assert summary.trade_count == 5
    assert summary.message == "Strategy V1 training+blindtest completed"
    assert summary.selected_family == "momentum_breakout"
    assert summary.best_day_pnl == 5.0


def test_windows_come_from_train_blind_split_report() -> None:
    run_id = "run_20260612_210003"
    _save_completed_reports(run_id)

    summary = build_backtest_summary(run_id)

    assert summary.training_start == "2026-01-01T00:00:00"
    assert summary.training_end == "2026-01-01T00:02:00"
    assert summary.blindtest_start == "2026-01-01T00:03:00"
    assert summary.blindtest_end == "2026-01-01T00:04:00"


def test_data_quality_comes_from_data_preparation_report() -> None:
    run_id = "run_20260612_210004"
    _save_completed_reports(run_id)

    summary = build_backtest_summary(run_id)
    assert summary.candle_count == 10
    assert summary.detected_gaps == 0
    assert summary.usable_for_backtest is True


def test_failed_summary_for_not_usable_data_preparation_report() -> None:
    run_id = "run_20260612_210005"
    save_data_preparation_report(_data_report(run_id, usable=False))

    summary = build_backtest_summary(run_id)
    assert summary.status == "failed"
    assert summary.final_capital is None
    assert "not enough candles" in summary.message


def test_save_and_load_summary() -> None:
    run_id = "run_20260612_210006"
    _save_completed_reports(run_id)
    summary = build_backtest_summary(run_id)

    save_backtest_summary(summary)

    assert load_backtest_summary(run_id) == summary


def test_missing_reports_are_rejected() -> None:
    with pytest.raises(FileNotFoundError):
        build_backtest_summary("run_20260612_219999")


def test_invalid_run_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_backtest_summary("../unsafe")


def test_no_short_futures_margin_or_leverage_fields() -> None:
    field_names = {field.name for field in fields(BacktestSummary)}

    assert "short" not in field_names
    assert "futures" not in field_names
    assert "margin" not in field_names
    assert "leverage" not in field_names
