from dataclasses import fields

import pytest

import src.backtest.strategy_v1 as strategy_module
from src.backtest.strategy_v1 import (
    StrategyV1Candidate,
    StrategyV1Result,
    StrategyV1Trade,
    default_strategy_v1_candidates,
    evaluate_strategy_v1_candidates,
    run_strategy_v1_on_candles,
    select_best_strategy_v1,
)
from src.data.candle_schema import Candle


def _candles(prices: list[float]) -> list[Candle]:
    return [
        Candle(f"2026-01-01T00:{index:02d}:00", price, price, price, price, 1.0)
        for index, price in enumerate(prices)
    ]


def _ohlc_candles(values: list[tuple[float, float, float, float]]) -> list[Candle]:
    return [
        Candle(f"2026-01-01T00:{index:02d}:00", open_, high, low, close, 1.0)
        for index, (open_, high, low, close) in enumerate(values)
    ]


def _candidate(family: str = "momentum_breakout") -> StrategyV1Candidate:
    return StrategyV1Candidate(family, "test", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0)


def _trade(month: str, pnl: float) -> StrategyV1Trade:
    return StrategyV1Trade(
        f"2024-{month}-01T00:00:00Z",
        f"2024-{month}-01T00:01:00Z",
        100.0,
        101.0,
        100.0,
        1.0,
        pnl,
        0.0,
        pnl,
        pnl,
        "max_hold",
        "range_breakout",
        "test",
    )


def test_default_candidates_have_multiple_families_and_expected_count() -> None:
    candidates = default_strategy_v1_candidates()

    assert len(candidates) == 612
    assert len({candidate.family for candidate in candidates}) > 1


def test_candidate_space_contains_mid_threshold_and_shorter_lookback_candidates() -> None:
    names = {candidate.name for candidate in default_strategy_v1_candidates()}

    assert "range_breakout_lb10_th0.006_tp0.01" in names
    assert "range_breakout_lb45_th0.012_tp0.02_ctx" in names
    assert "range_breakout_lb20_th0.01_tp0.02_trail0.008" in names
    assert "trend_pullback_lb60_th0.012_tp0.025_trail0.01_ctx" in names
    assert "trend_pullback_lb40_th0.009_tp0.014" in names
    assert "trend_pullback_lb50_th0.011_tp0.016_ctx" in names
    assert "situation_router_lb30_th0.008_tp0.014_trail0.006" in names
    assert "situation_router_lb45_th0.01_tp0.018_ctx" in names


def test_situation_router_entry_requires_recognizable_pre_entry_situation() -> None:
    candidate = StrategyV1Candidate(
        "situation_router", "situation", 3, 9, 0.01, 0.012, 0.006, 4, 0, 10.0, 100.0
    )

    weak_situation = run_strategy_v1_on_candles(
        _candles([100.0, 100.2, 100.4, 100.5, 100.6, 100.8, 101.0, 101.0, 100.8, 101.0, 102.0]),
        candidate,
    )
    learned_situation = run_strategy_v1_on_candles(
        _candles([100.0, 100.4, 100.8, 101.2, 101.6, 102.0, 102.4, 102.8, 102.2, 102.7, 104.0]),
        candidate,
    )

    assert weak_situation.trade_count == 0
    assert learned_situation.trade_count == 1


def test_candidate_space_extension_adds_trailing_candidates() -> None:
    candidates = default_strategy_v1_candidates()
    trailing = [candidate for candidate in candidates if candidate.trailing_stop_pct is not None]

    assert len(candidates) > 400
    assert len(trailing) == 168
    assert {candidate.trailing_stop_pct for candidate in trailing} == {0.006, 0.008, 0.01}


def test_fixed_stake_100_is_used() -> None:
    result = run_strategy_v1_on_candles(_candles([100, 102, 104]), _candidate())

    assert result.trades[0].stake_quote_amount == 100.0


def test_after_loss_next_trade_uses_100_stake() -> None:
    result = run_strategy_v1_on_candles(_candles([100, 102, 98, 100, 102, 104]), _candidate())

    assert len(result.trades) == 2
    assert [trade.stake_quote_amount for trade in result.trades] == [100.0, 100.0]
    assert result.trades[0].net_pnl < 0


def test_take_profit_uses_intrabar_high_not_only_close() -> None:
    result = run_strategy_v1_on_candles(_ohlc_candles([(100, 100, 100, 100), (102, 102, 102, 102), (102, 103, 102, 102)]), _candidate())

    assert result.trades[0].exit_reason == "take_profit"
    assert result.trades[0].exit_price == pytest.approx(102.4)


def test_stop_loss_uses_intrabar_low_not_only_close() -> None:
    result = run_strategy_v1_on_candles(_ohlc_candles([(100, 100, 100, 100), (102, 102, 102, 102), (102, 102, 101, 102)]), _candidate())

    assert result.trades[0].exit_reason == "stop_loss"
    assert result.trades[0].exit_price == pytest.approx(101.59)


def test_stop_loss_wins_when_stop_and_take_profit_are_touched_same_candle() -> None:
    result = run_strategy_v1_on_candles(_ohlc_candles([(100, 100, 100, 100), (102, 102, 102, 102), (102, 103, 101, 102)]), _candidate())

    assert result.trades[0].exit_reason == "stop_loss"


def test_trailing_stop_uses_prior_intrabar_high_conservatively() -> None:
    candidate = StrategyV1Candidate(
        "momentum_breakout", "trail", 1, None, 0.001, 0.02, 0.02, 5, 0, 10.0, 100.0, trailing_stop_pct=0.01
    )
    result = run_strategy_v1_on_candles(
        _ohlc_candles([(100, 100, 100, 100), (102, 102, 102, 102), (102.8, 103, 102.5, 102.8), (102.8, 102.9, 101.9, 102.0)]),
        candidate,
    )

    assert result.trades[0].exit_reason == "trailing_stop"
    assert result.trades[0].exit_price == pytest.approx(101.97)


def test_trend_pullback_entry_uses_threshold_to_avoid_noise_trades() -> None:
    candidate = StrategyV1Candidate(
        "trend_pullback", "pullback_threshold", 2, 3, 0.01, 0.02, 0.01, 3, 0, 10.0, 100.0
    )

    noisy_recovery = run_strategy_v1_on_candles(_candles([100.0, 101.2, 101.0, 101.1, 102.0]), candidate)
    real_recovery = run_strategy_v1_on_candles(_candles([100.0, 102.0, 101.0, 101.6, 103.0]), candidate)

    assert noisy_recovery.trade_count == 0
    assert real_recovery.trade_count == 1


def test_engine_counts_signals_no_trade_and_blocked_context() -> None:
    candidate = StrategyV1Candidate(
        "momentum_breakout", "ctx", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0, use_context_filter=True
    )

    result = run_strategy_v1_on_candles(_candles([100, 102, 104]), candidate, context_by_symbol=None)

    assert result.signal_count == 1
    assert result.blocked_signal_count == 1
    assert result.no_trade_count >= 1
    assert result.trade_count == 0


def test_allowed_entry_times_gate_blocks_otherwise_valid_entries() -> None:
    candidate = _candidate()
    candles = _candles([100, 102, 104])

    blocked = run_strategy_v1_on_candles(candles, candidate, allowed_entry_times=set())
    allowed = run_strategy_v1_on_candles(candles, candidate, allowed_entry_times={candles[1].open_time})

    assert blocked.trade_count == 0
    assert blocked.signal_count == 0
    assert allowed.trade_count == 1
    assert allowed.signal_count == 1


def test_each_trade_uses_selected_fixed_stake() -> None:
    candidate = StrategyV1Candidate(
        "momentum_breakout", "test", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 500.0
    )
    result = run_strategy_v1_on_candles(_candles([100, 102, 98, 100, 102, 104]), candidate)

    assert len(result.trades) == 2
    assert [trade.stake_quote_amount for trade in result.trades] == [500.0, 500.0]
    assert result.stake_quote_amount == 500.0


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


def test_low_activity_penalty_prefers_robust_near_equal_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    rare = StrategyV1Candidate(
        "range_breakout", "rare", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0
    )
    robust = StrategyV1Candidate(
        "range_breakout", "robust", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0
    )
    monkeypatch.setattr(strategy_module, "default_strategy_v1_candidates", lambda: [rare, robust])

    def fake_run(candles, candidate, start_capital_reference=100.0):
        if candidate == rare:
            return StrategyV1Result(
                candidate, start_capital_reference, 100.0, 103.55, 3.55, 3.55, 0.0, 18, 9, 9, 0, 0.0, []
            )
        return StrategyV1Result(
            candidate, start_capital_reference, 100.0, 103.52, 3.52, 3.52, 0.0, 31, 16, 15, 0, 0.0, []
        )

    monkeypatch.setattr(strategy_module, "run_strategy_v1_on_candles", fake_run)

    assert select_best_strategy_v1(_candles([100, 101])).candidate == robust
    _, evaluations = evaluate_strategy_v1_candidates(_candles([100, 101]))
    rare_eval = next(item for item in evaluations if item.candidate == rare)
    assert rare_eval.low_activity_penalty > 2.0


def test_training_stability_metrics_count_months_and_profit_concentration(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = _candidate("range_breakout")
    monkeypatch.setattr(strategy_module, "default_strategy_v1_candidates", lambda: [candidate])
    trades = [_trade("01", 5.0), _trade("01", -1.0), _trade("02", -0.5)]

    def fake_run(candles, candidate, start_capital_reference=100.0):
        return StrategyV1Result(
            candidate, start_capital_reference, 100.0, 103.5, 3.5, 3.5, 0.0, 3, 1, 2, 0, 2.0, trades
        )

    monkeypatch.setattr(strategy_module, "run_strategy_v1_on_candles", fake_run)

    _, evaluations = evaluate_strategy_v1_candidates(_candles([100, 101]))
    evaluation = evaluations[0]

    assert evaluation.training_active_months == 2
    assert evaluation.training_positive_months == 1
    assert evaluation.training_negative_months == 1
    assert evaluation.training_top_trade_profit_share == 1.0
    assert evaluation.training_profit_concentration_warning is True


def test_final_score_uses_stability_penalty_for_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    concentrated = StrategyV1Candidate("range_breakout", "concentrated", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0)
    stable = StrategyV1Candidate("range_breakout", "stable", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0)
    monkeypatch.setattr(strategy_module, "default_strategy_v1_candidates", lambda: [concentrated, stable])
    concentrated_trades = [_trade("01", 5.5)] + [_trade("01", -0.02) for _ in range(23)]
    stable_trades = [_trade(f"{month:02d}", 0.6) for month in range(1, 9)] + [_trade("09", -0.1) for _ in range(16)]

    def fake_run(candles, candidate, start_capital_reference=100.0):
        if candidate == concentrated:
            return StrategyV1Result(
                candidate, start_capital_reference, 100.0, 105.0, 5.0, 5.0, 0.0, 24, 1, 23, 0, 1.0, concentrated_trades
            )
        return StrategyV1Result(
            candidate, start_capital_reference, 100.0, 104.7, 4.7, 4.7, 0.0, 24, 8, 16, 0, 1.0, stable_trades
        )

    monkeypatch.setattr(strategy_module, "run_strategy_v1_on_candles", fake_run)

    selected, evaluations = evaluate_strategy_v1_candidates(_candles([100, 101]))

    assert selected.candidate == stable
    concentrated_eval = next(item for item in evaluations if item.candidate == concentrated)
    assert concentrated_eval.adjusted_score_final < concentrated_eval.adjusted_score
    assert concentrated_eval.concentration_penalty > 0


def test_training_score_penalizes_negative_and_inactive_months(monkeypatch: pytest.MonkeyPatch) -> None:
    unstable = StrategyV1Candidate("range_breakout", "unstable", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0)
    steadier = StrategyV1Candidate("range_breakout", "steadier", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0)
    monkeypatch.setattr(strategy_module, "default_strategy_v1_candidates", lambda: [unstable, steadier])
    unstable_trades = [_trade(f"{month:02d}", 0.8) for month in range(1, 7)] + [_trade(f"{month:02d}", -0.2) for month in range(7, 14)]
    steadier_trades = [_trade(f"{month:02d}", 0.35) for month in range(1, 13)] + [_trade(f"{month:02d}", -0.1) for month in range(13, 17)]

    def fake_run(candles, candidate, start_capital_reference=100.0):
        if candidate == unstable:
            return StrategyV1Result(
                candidate, start_capital_reference, 100.0, 103.4, 3.4, 3.4, 0.0, 31, 6, 7, 0, 6.0, unstable_trades
            )
        return StrategyV1Result(
            candidate, start_capital_reference, 100.0, 103.1, 3.1, 3.1, 0.0, 31, 12, 4, 0, 6.0, steadier_trades
        )

    monkeypatch.setattr(strategy_module, "run_strategy_v1_on_candles", fake_run)

    selected, evaluations = evaluate_strategy_v1_candidates(_candles([100, 101]))

    assert selected.candidate == steadier
    unstable_eval = next(item for item in evaluations if item.candidate == unstable)
    assert unstable_eval.stability_penalty > 1.0
    assert "inactive training months" in unstable_eval.stability_diagnosis


def test_selection_uses_final_score_not_raw_score(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_winner = StrategyV1Candidate("range_breakout", "raw_winner", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0)
    final_winner = StrategyV1Candidate("range_breakout", "final_winner", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0)
    monkeypatch.setattr(strategy_module, "default_strategy_v1_candidates", lambda: [raw_winner, final_winner])
    raw_winner_trades = [_trade(f"{month:02d}", 0.9) for month in range(1, 7)] + [_trade(f"{month:02d}", -0.2) for month in range(7, 14)]
    final_winner_trades = [_trade(f"{month:02d}", 0.25) for month in range(1, 13)] + [_trade(f"{month:02d}", -0.05) for month in range(13, 17)]

    def fake_run(candles, candidate, start_capital_reference=100.0):
        if candidate == raw_winner:
            return StrategyV1Result(candidate, start_capital_reference, 100.0, 103.8, 3.8, 3.8, 0.0, 31, 6, 7, 0, 8.0, raw_winner_trades)
        return StrategyV1Result(candidate, start_capital_reference, 100.0, 103.0, 3.0, 3.0, 0.0, 31, 12, 4, 0, 4.0, final_winner_trades)

    monkeypatch.setattr(strategy_module, "run_strategy_v1_on_candles", fake_run)

    selected, _ = evaluate_strategy_v1_candidates(_candles([100, 101]))

    assert selected.candidate == final_winner


def test_falling_market_can_show_negative_result() -> None:
    result = run_strategy_v1_on_candles(_candles([100, 102, 98]), _candidate())

    assert result.total_net_pnl < 0


def test_no_short_futures_margin_or_leverage_fields() -> None:
    field_names = {field.name for field in fields(StrategyV1Candidate)}

    assert "short" not in field_names
    assert "futures" not in field_names
    assert "margin" not in field_names
    assert "leverage" not in field_names
