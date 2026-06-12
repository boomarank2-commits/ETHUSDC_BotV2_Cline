from dataclasses import fields

import pytest

import src.backtest.strategy_v1 as strategy_module
from src.backtest.strategy_v1 import (
    StrategyV1Candidate,
    StrategyV1Result,
    default_strategy_v1_candidates,
    run_strategy_v1_on_candles,
    select_best_strategy_v1,
)
from src.data.candle_schema import Candle


def _candles(prices: list[float]) -> list[Candle]:
    return [
        Candle(f"2026-01-01T00:{index:02d}:00", price, price, price, price, 1.0)
        for index, price in enumerate(prices)
    ]


def _candidate(family: str = "momentum_breakout") -> StrategyV1Candidate:
    return StrategyV1Candidate(family, "test", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0)


def test_default_candidates_have_multiple_families_and_expected_count() -> None:
    candidates = default_strategy_v1_candidates()

    assert 24 <= len(candidates) <= 80
    assert len({candidate.family for candidate in candidates}) > 1


def test_fixed_stake_100_is_used() -> None:
    result = run_strategy_v1_on_candles(_candles([100, 102, 104]), _candidate())

    assert result.trades[0].stake_usdt == 100.0


def test_after_loss_next_trade_uses_100_stake() -> None:
    result = run_strategy_v1_on_candles(_candles([100, 102, 98, 100, 102, 104]), _candidate())

    assert len(result.trades) == 2
    assert [trade.stake_usdt for trade in result.trades] == [100.0, 100.0]
    assert result.trades[0].net_pnl < 0


def test_each_trade_uses_selected_fixed_stake() -> None:
    candidate = StrategyV1Candidate(
        "momentum_breakout", "test", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 500.0
    )
    result = run_strategy_v1_on_candles(_candles([100, 102, 98, 100, 102, 104]), candidate)

    assert len(result.trades) == 2
    assert [trade.stake_usdt for trade in result.trades] == [500.0, 500.0]
    assert result.stake_usdt == 500.0


def test_training_compares_multiple_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    candidates = [
        _candidate(),
        StrategyV1Candidate(
            "range_breakout", "range", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0
        ),
    ]
    monkeypatch.setattr(strategy_module, "default_strategy_v1_candidates", lambda: candidates)
    seen: list[StrategyV1Candidate] = []

    def fake_run(candles, candidate, start_capital_reference=100.0):
        seen.append(candidate)
        return StrategyV1Result(
            candidate, start_capital_reference, 100.0, 100.0, 0.0, 0.0, 0.0, 1, 1, 0, 0, 0.0, []
        )

    monkeypatch.setattr(strategy_module, "run_strategy_v1_on_candles", fake_run)

    select_best_strategy_v1(_candles([100, 101]))

    assert seen == candidates


def test_zero_trade_candidate_does_not_win_when_other_trades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    zero = _candidate()
    active = StrategyV1Candidate(
        "range_breakout", "active", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0
    )
    monkeypatch.setattr(strategy_module, "default_strategy_v1_candidates", lambda: [zero, active])

    def fake_run(candles, candidate, start_capital_reference=100.0):
        trades = [] if candidate == zero else [object()]
        return StrategyV1Result(
            candidate,
            start_capital_reference,
            100.0,
            100.0,
            0.0,
            0.0,
            0.0,
            len(trades),
            0,
            0,
            0,
            0.0,
            trades,
        )

    monkeypatch.setattr(strategy_module, "run_strategy_v1_on_candles", fake_run)

    assert select_best_strategy_v1(_candles([100, 101])).candidate == active


def test_falling_market_can_show_negative_result() -> None:
    result = run_strategy_v1_on_candles(_candles([100, 102, 98]), _candidate())

    assert result.total_net_pnl < 0


def test_no_short_futures_margin_or_leverage_fields() -> None:
    field_names = {field.name for field in fields(StrategyV1Candidate)}

    assert "short" not in field_names
    assert "futures" not in field_names
    assert "margin" not in field_names
    assert "leverage" not in field_names
