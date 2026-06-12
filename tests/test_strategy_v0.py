from dataclasses import fields

import pytest

import src.backtest.strategy_v0 as strategy_module
from src.backtest.strategy_v0 import (
    StrategyV0Candidate,
    StrategyV0Result,
    default_strategy_v0_candidates,
    run_strategy_v0_on_candles,
    select_best_strategy_v0,
)
from src.data.candle_schema import Candle


def _candles(prices: list[float]) -> list[Candle]:
    return [
        Candle(f"2026-01-01T00:{index:02d}:00", price, price, price, price, 1.0)
        for index, price in enumerate(prices)
    ]


def _candidate(name: str = "test") -> StrategyV0Candidate:
    return StrategyV0Candidate(name, 1, 0.001, 0.004, 0.004, 3, 10.0)


def test_default_candidates_compare_multiple_settings() -> None:
    assert len(default_strategy_v0_candidates()) > 1


def test_best_strategy_is_selected_from_training(monkeypatch: pytest.MonkeyPatch) -> None:
    weak = StrategyV0Candidate("weak", 1, 0.001, 0.004, 0.004, 3, 10.0)
    strong = StrategyV0Candidate("strong", 1, 0.001, 0.004, 0.004, 3, 10.0)
    monkeypatch.setattr(strategy_module, "default_strategy_v0_candidates", lambda: [weak, strong])

    def fake_run(candles, candidate, start_capital):
        final_capital = 90.0 if candidate.name == "weak" else 120.0
        return StrategyV0Result(candidate, start_capital, final_capital, 0.0, 0.0, 0, 0, 0, 0.0, [])

    monkeypatch.setattr(strategy_module, "run_strategy_v0_on_candles", fake_run)

    assert select_best_strategy_v0(_candles([100, 101]), 100.0).candidate == strong


def test_falling_market_can_show_negative_result() -> None:
    result = run_strategy_v0_on_candles(_candles([100, 102, 98]), _candidate(), 100.0)

    assert result.total_pnl < 0


def test_rising_momentum_market_can_create_positive_trade() -> None:
    result = run_strategy_v0_on_candles(_candles([100, 102, 104]), _candidate(), 100.0)

    assert result.trade_count == 1
    assert result.total_pnl > 0


def test_start_capital_must_be_positive() -> None:
    with pytest.raises(ValueError):
        run_strategy_v0_on_candles(_candles([100, 102]), _candidate(), 0.0)


def test_no_short_futures_margin_or_leverage_fields() -> None:
    field_names = {field.name for field in fields(StrategyV0Candidate)}

    assert "short" not in field_names
    assert "futures" not in field_names
    assert "margin" not in field_names
    assert "leverage" not in field_names
