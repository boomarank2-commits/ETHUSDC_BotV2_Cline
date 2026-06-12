from dataclasses import fields

import src.backtest.strategy_v1_report as report_module
from src.backtest.strategy_v1 import StrategyV1Candidate, StrategyV1Result, StrategyV1Trade
from src.backtest.strategy_v1_report import (
    StrategyV1TrainingBlindtestReport,
    build_strategy_v1_training_blindtest_report,
    load_strategy_v1_report,
    save_strategy_v1_report,
)
from src.data.candle_schema import Candle
from src.data.train_blind_split import TrainBlindSplit


def _candle(index: int) -> Candle:
    return Candle(f"2026-01-0{1 + index // 2}T00:0{index % 2}:00", 100.0, 100.0, 100.0, 100.0, 1.0)


def _split() -> TrainBlindSplit:
    training = [_candle(0), _candle(1)]
    blindtest = [_candle(2), _candle(3), _candle(4)]
    return TrainBlindSplit(
        "ETHUSDC",
        "1m",
        training,
        blindtest,
        training[0].open_time,
        training[-1].open_time,
        blindtest[0].open_time,
        blindtest[-1].open_time,
    )


def _candidate() -> StrategyV1Candidate:
    return StrategyV1Candidate(
        "momentum_breakout", "selected", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0
    )


def _trade(day: str, pnl: float) -> StrategyV1Trade:
    return StrategyV1Trade(
        day,
        day,
        100.0,
        101.0,
        100.0,
        1.0,
        pnl,
        0.2,
        pnl,
        pnl,
        "max_hold",
        "momentum_breakout",
        "selected",
    )


def test_blindtest_uses_exact_training_candidate(monkeypatch) -> None:
    selected = _candidate()
    used: list[StrategyV1Candidate] = []
    monkeypatch.setattr(
        report_module,
        "select_best_strategy_v1",
        lambda candles, start_capital_reference: StrategyV1Result(
            selected, 100.0, 100.0, 110.0, 10.0, 10.0, 1.0, 1, 1, 0, 0, 0.0, []
        ),
    )

    def fake_run(candles, candidate, start_capital_reference=100.0):
        used.append(candidate)
        return StrategyV1Result(candidate, 100.0, 100.0, 101.0, 1.0, 1.0, 1.0, 1, 1, 0, 0, 0.0, [])

    monkeypatch.setattr(report_module, "run_strategy_v1_on_candles", fake_run)
    report = build_strategy_v1_training_blindtest_report("run_20260612_240001", _split())

    assert report.selected_candidate == selected
    assert used == [selected]


def test_daily_stats_are_calculated(monkeypatch) -> None:
    selected = _candidate()
    monkeypatch.setattr(
        report_module,
        "select_best_strategy_v1",
        lambda candles, start_capital_reference: StrategyV1Result(
            selected, 100.0, 100.0, 110.0, 10.0, 10.0, 1.0, 1, 1, 0, 0, 0.0, []
        ),
    )
    monkeypatch.setattr(
        report_module,
        "run_strategy_v1_on_candles",
        lambda candles, candidate, start_capital_reference=100.0: StrategyV1Result(
            candidate,
            100.0,
            100.0,
            100.0,
            0.0,
            0.0,
            0.0,
            2,
            1,
            1,
            0,
            1.0,
            [_trade("2026-01-02", 2.0), _trade("2026-01-03", -1.0)],
        ),
    )

    report = build_strategy_v1_training_blindtest_report("run_20260612_240002", _split())

    assert report.positive_days == 1
    assert report.negative_days == 1
    assert report.best_day_pnl == 2.0
    assert report.worst_day_pnl == -1.0


def test_strategy_v1_report_save_and_load(monkeypatch) -> None:
    selected = _candidate()
    monkeypatch.setattr(
        report_module,
        "select_best_strategy_v1",
        lambda candles, start_capital_reference: StrategyV1Result(
            selected, 100.0, 100.0, 110.0, 10.0, 10.0, 1.0, 1, 1, 0, 0, 0.0, []
        ),
    )
    monkeypatch.setattr(
        report_module,
        "run_strategy_v1_on_candles",
        lambda candles, candidate, start_capital_reference=100.0: StrategyV1Result(
            candidate, 100.0, 100.0, 101.0, 1.0, 1.0, 1.0, 1, 1, 0, 0, 0.0, []
        ),
    )
    report = build_strategy_v1_training_blindtest_report("run_20260612_240003", _split())

    save_strategy_v1_report(report)

    assert load_strategy_v1_report(report.run_id) == report


def test_report_uses_selected_stake_usdt(monkeypatch) -> None:
    selected = _candidate()
    used: list[StrategyV1Candidate] = []
    monkeypatch.setattr(
        report_module,
        "select_best_strategy_v1",
        lambda candles, start_capital_reference: StrategyV1Result(
            selected, 100.0, 100.0, 110.0, 10.0, 10.0, 1.0, 1, 1, 0, 0, 0.0, []
        ),
    )

    def fake_run(candles, candidate, start_capital_reference=100.0):
        used.append(candidate)
        return StrategyV1Result(
            candidate, 100.0, candidate.stake_usdt, 101.0, 1.0, 1.0, 1.0, 1, 1, 0, 0, 0.0, []
        )

    monkeypatch.setattr(report_module, "run_strategy_v1_on_candles", fake_run)

    report = build_strategy_v1_training_blindtest_report(
        "run_20260612_240004", _split(), stake_usdt=500.0
    )

    assert report.stake_usdt == 500.0
    assert report.selected_candidate.stake_usdt == 500.0
    assert used[0].stake_usdt == 500.0


def test_report_stores_profile(monkeypatch) -> None:
    selected = _candidate()
    monkeypatch.setattr(
        report_module,
        "select_best_strategy_v1",
        lambda candles, start_capital_reference: StrategyV1Result(
            selected, 100.0, 100.0, 110.0, 10.0, 10.0, 1.0, 1, 1, 0, 0, 0.0, []
        ),
    )
    monkeypatch.setattr(
        report_module,
        "run_strategy_v1_on_candles",
        lambda candles, candidate, start_capital_reference=100.0: StrategyV1Result(
            candidate, 100.0, candidate.stake_usdt, 101.0, 1.0, 1.0, 1.0, 1, 1, 0, 0, 0.0, []
        ),
    )

    report = build_strategy_v1_training_blindtest_report(
        "run_20260612_240005", _split(), profile="aggressive"
    )

    assert report.profile == "aggressive"


def test_invalid_profile_is_rejected() -> None:
    try:
        build_strategy_v1_training_blindtest_report(
            "run_20260612_240006", _split(), profile="invalid"
        )
    except ValueError as error:
        assert "profile" in str(error)
    else:
        raise AssertionError("invalid profile must fail")


def test_no_short_futures_margin_or_leverage_fields() -> None:
    field_names = {field.name for field in fields(StrategyV1TrainingBlindtestReport)}

    assert "short" not in field_names
    assert "futures" not in field_names
    assert "margin" not in field_names
    assert "leverage" not in field_names
