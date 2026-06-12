from dataclasses import fields

import pytest

from src.backtest.buy_hold_benchmark import (
    BUY_HOLD_BENCHMARK_REPORT_FILENAME,
    build_buy_hold_benchmark_report,
    load_buy_hold_benchmark_report,
    save_buy_hold_benchmark_report,
)
from src.common.report_paths import get_run_report_dir
from src.data.candle_schema import Candle
from src.data.train_blind_split import TrainBlindSplit


def _candle(open_time: str, close: float) -> Candle:
    return Candle(open_time, close, close, close, close, 1.0)


def _split(entry_close: float = 100.0, exit_close: float = 120.0) -> TrainBlindSplit:
    training_candles = [_candle("2026-01-01T00:00:00", 999.0)]
    blindtest_candles = [
        _candle("2026-01-01T00:01:00", entry_close),
        _candle("2026-01-01T00:02:00", exit_close),
    ]
    return TrainBlindSplit(
        symbol="ETHUSDC",
        interval="1m",
        training_candles=training_candles,
        blindtest_candles=blindtest_candles,
        training_start=training_candles[0].open_time,
        training_end=training_candles[-1].open_time,
        blindtest_start=blindtest_candles[0].open_time,
        blindtest_end=blindtest_candles[-1].open_time,
    )


def test_report_calculates_positive_result() -> None:
    report = build_buy_hold_benchmark_report("run_20260612_200001", _split(100.0, 120.0))

    assert report.final_capital == 120.0
    assert report.total_pnl == 20.0
    assert report.total_pnl_pct == 20.0


def test_report_calculates_negative_pnl() -> None:
    report = build_buy_hold_benchmark_report("run_20260612_200002", _split(100.0, 80.0))

    assert report.final_capital == 80.0
    assert report.total_pnl == -20.0
    assert report.total_pnl_pct == -20.0


def test_only_blindtest_candles_are_used() -> None:
    report = build_buy_hold_benchmark_report("run_20260612_200003", _split(100.0, 120.0))

    assert report.entry_price == 100.0
    assert report.exit_price == 120.0


def test_trade_count_is_one() -> None:
    report = build_buy_hold_benchmark_report("run_20260612_200004", _split())

    assert report.trade_count == 1


def test_save_and_load_report() -> None:
    report = build_buy_hold_benchmark_report("run_20260612_200005", _split())

    report_path = save_buy_hold_benchmark_report(report)

    assert report_path == get_run_report_dir(report.run_id) / BUY_HOLD_BENCHMARK_REPORT_FILENAME
    assert load_buy_hold_benchmark_report(report.run_id) == report


def test_invalid_run_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_buy_hold_benchmark_report("../unsafe", _split())


def test_start_capital_must_be_positive() -> None:
    with pytest.raises(ValueError):
        build_buy_hold_benchmark_report("run_20260612_200006", _split(), start_capital=0.0)


def test_empty_blindtest_candles_are_rejected() -> None:
    split = _split()
    empty_blindtest_split = TrainBlindSplit(
        symbol=split.symbol,
        interval=split.interval,
        training_candles=split.training_candles,
        blindtest_candles=[],
        training_start=split.training_start,
        training_end=split.training_end,
        blindtest_start="",
        blindtest_end="",
    )

    with pytest.raises(ValueError):
        build_buy_hold_benchmark_report("run_20260612_200007", empty_blindtest_split)


def test_no_short_futures_margin_or_leverage_fields() -> None:
    report = build_buy_hold_benchmark_report("run_20260612_200008", _split())
    field_names = {field.name for field in fields(type(report))}

    assert "short" not in field_names
    assert "futures" not in field_names
    assert "margin" not in field_names
    assert "leverage" not in field_names
