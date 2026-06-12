from dataclasses import fields

import src.backtest.strategy_v0_report as report_module
from src.backtest.strategy_v0 import StrategyV0Candidate, StrategyV0Result
from src.backtest.strategy_v0_report import (
    build_strategy_v0_training_blindtest_report,
    load_strategy_v0_report,
    save_strategy_v0_report,
)
from src.data.candle_schema import Candle
from src.data.train_blind_split import TrainBlindSplit


def _candle(index: int, price: float = 100.0) -> Candle:
    return Candle(f"2026-01-01T00:{index:02d}:00", price, price, price, price, 1.0)


def _split() -> TrainBlindSplit:
    training = [_candle(0), _candle(1)]
    blindtest = [_candle(2), _candle(3)]
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


def test_blindtest_uses_exact_selected_candidate(monkeypatch) -> None:
    selected = StrategyV0Candidate("selected", 1, 0.001, 0.004, 0.004, 3, 10.0)
    used_candidates: list[StrategyV0Candidate] = []

    monkeypatch.setattr(
        report_module,
        "select_best_strategy_v0",
        lambda candles, start_capital: StrategyV0Result(
            selected, start_capital, 110.0, 10.0, 10.0, 1, 1, 0, 0.0, []
        ),
    )

    def fake_run(candles, candidate, start_capital):
        used_candidates.append(candidate)
        return StrategyV0Result(candidate, start_capital, 105.0, 5.0, 5.0, 1, 1, 0, 0.0, [])

    monkeypatch.setattr(report_module, "run_strategy_v0_on_candles", fake_run)

    report = build_strategy_v0_training_blindtest_report("run_20260612_230001", _split())

    assert report.selected_candidate == selected
    assert used_candidates == [selected]


def test_strategy_v0_report_save_and_load(monkeypatch) -> None:
    candidate = StrategyV0Candidate("selected", 1, 0.001, 0.004, 0.004, 3, 10.0)
    monkeypatch.setattr(
        report_module,
        "select_best_strategy_v0",
        lambda candles, start_capital: StrategyV0Result(
            candidate, start_capital, 110.0, 10.0, 10.0, 1, 1, 0, 0.0, []
        ),
    )
    monkeypatch.setattr(
        report_module,
        "run_strategy_v0_on_candles",
        lambda candles, candidate, start_capital: StrategyV0Result(
            candidate, start_capital, 105.0, 5.0, 5.0, 1, 1, 0, 0.0, []
        ),
    )
    report = build_strategy_v0_training_blindtest_report("run_20260612_230002", _split())

    save_strategy_v0_report(report)

    assert load_strategy_v0_report(report.run_id) == report


def test_no_short_futures_margin_or_leverage_fields() -> None:
    field_names = {field.name for field in fields(report_module.StrategyV0TrainingBlindtestReport)}

    assert "short" not in field_names
    assert "futures" not in field_names
    assert "margin" not in field_names
    assert "leverage" not in field_names
