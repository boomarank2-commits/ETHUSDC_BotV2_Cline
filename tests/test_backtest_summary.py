from dataclasses import replace

from src.data.candle_schema import Candle
from src.data.data_preparation_report import (
    DataPreparationReport,
    save_data_preparation_report,
)
from src.data.train_blind_split import TrainBlindSplit
from src.data.train_blind_split_report import (
    TrainBlindSplitReport,
    save_train_blind_split_report,
)
from src.reports.backtest_summary import (
    build_backtest_summary,
    load_backtest_summary,
    save_backtest_summary,
)
from src.router.activity_first_router_report import (
    build_activity_first_router_report,
    save_activity_first_router_report,
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
        training_candle_count=6,
        blindtest_candle_count=4,
        training_start="2026-01-01T00:00:00",
        training_end="2026-01-01T00:05:00",
        blindtest_start="2026-01-01T00:06:00",
        blindtest_end="2026-01-01T00:09:00",
        has_overlap=False,
        blindtest_after_training=True,
    )


def _candle(index: int) -> Candle:
    return Candle(
        open_time=f"2026-01-01T00:{index:02d}:00Z",
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1.0,
        quote_volume=100.0,
        trade_count=10,
        taker_buy_base_volume=0.5,
        taker_buy_quote_volume=50.0,
    )


def test_summary_fails_when_data_is_not_usable() -> None:
    run_id = "run_test_summary_unusable"
    save_data_preparation_report(_data_report(run_id, usable=False))

    summary = build_backtest_summary(run_id)

    assert summary.status == "failed"
    assert summary.usable_for_backtest is False


def test_summary_requires_activity_first_router_report() -> None:
    run_id = "run_test_summary_missing_activity_router"
    save_data_preparation_report(_data_report(run_id))
    save_train_blind_split_report(_split_report(run_id))

    summary = build_backtest_summary(run_id)

    assert summary.status == "failed"
    assert "no alternate backtest engine" in summary.message


def test_summary_is_built_only_from_activity_first_router() -> None:
    run_id = "run_test_summary_activity_first_only"
    save_data_preparation_report(_data_report(run_id))
    save_train_blind_split_report(_split_report(run_id))
    candles = [_candle(index) for index in range(10)]
    split = TrainBlindSplit(
        symbol="ETHUSDC",
        interval="1m",
        training_candles=candles[:6],
        blindtest_candles=candles[6:],
        training_start=candles[0].open_time,
        training_end=candles[5].open_time,
        blindtest_start=candles[6].open_time,
        blindtest_end=candles[9].open_time,
    )
    save_activity_first_router_report(build_activity_first_router_report(run_id, split))

    summary = build_backtest_summary(run_id)
    path = save_backtest_summary(summary)

    assert summary.status == "completed"
    assert summary.selected_family == "activity_first_router"
    assert load_backtest_summary(run_id) == summary
    assert path.is_file()


def test_summary_surfaces_selected_setup_family() -> None:
    run_id = "run_test_summary_selected_setup_family"
    save_data_preparation_report(_data_report(run_id))
    save_train_blind_split_report(_split_report(run_id))
    candles = [_candle(index) for index in range(10)]
    split = TrainBlindSplit(
        symbol="ETHUSDC",
        interval="1m",
        training_candles=candles[:6],
        blindtest_candles=candles[6:],
        training_start=candles[0].open_time,
        training_end=candles[5].open_time,
        blindtest_start=candles[6].open_time,
        blindtest_end=candles[9].open_time,
    )
    report = build_activity_first_router_report(run_id, split)
    save_activity_first_router_report(
        replace(
            report,
            selected_setups=[
                {
                    "candidate_id": "erem_btc_drawdown_q35_or_ema_below0",
                    "strategy_family": "erem_exposure_management",
                }
            ],
            trade_allowed_setup_count=1,
            selected_candidate_count=1,
            candidate_space_status="trade_allowed_found",
            router_artifact={"diagnostic_only": False},
        )
    )

    summary = build_backtest_summary(run_id)

    assert summary.selected_family == "erem_exposure_management"
    assert summary.selected_candidate_name == "erem_btc_drawdown_q35_or_ema_below0"
