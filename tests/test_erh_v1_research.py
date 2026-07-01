from __future__ import annotations

import math

import pandas as pd

from src.research.erh_v1 import (
    ErhConfig,
    ErhVariant,
    build_erh_variants,
    resample_closed_candles,
    simulate_erh_variant,
    variant_regime_active,
)


def _minute_frame(minutes: int, start: str = "2026-01-01T00:00:00Z") -> pd.DataFrame:
    index = pd.date_range(start=start, periods=minutes, freq="min", tz="UTC")
    prices = [100.0 + minute * 0.01 for minute in range(minutes)]
    return pd.DataFrame(
        {
            "open": prices,
            "high": [price + 0.05 for price in prices],
            "low": [price - 0.05 for price in prices],
            "close": [price + 0.01 for price in prices],
            "volume": [1.0] * minutes,
            "quote_volume": [100.0] * minutes,
            "trade_count": [10] * minutes,
            "taker_buy_quote_volume": [52.0] * minutes,
        },
        index=index,
    )


def _execution_row(**overrides: float | bool | int) -> dict:
    row = {
        "open": 100.0,
        "high": 101.0,
        "low": 99.5,
        "close": 100.5,
        "hard_gate_pass": True,
        "regime_score": 3,
        "entry_trigger_base": True,
        "no_chase_block": False,
        "ethbtc_4h_close_vs_ema20": 0.01,
        "eth_4h_close_vs_ema20": 0.01,
        "btc_4h_drawdown_from_20d_high": -0.02,
        "eth_of_4h_buy_share": 0.52,
    }
    row.update(overrides)
    return row


def test_resample_closed_candles_indexes_by_availability_time() -> None:
    source = _minute_frame(240)

    h4 = resample_closed_candles(source, "4h")

    assert len(h4) == 1
    assert h4.index[0] == pd.Timestamp("2026-01-01T04:00:00Z")
    assert h4.iloc[0]["open"] == 100.0


def test_resample_closed_candles_ignores_partial_higher_timeframe() -> None:
    source = _minute_frame(239)

    h4 = resample_closed_candles(source, "4h")

    assert h4.empty


def test_variant_regime_active_requires_score_and_hard_gates() -> None:
    frame = pd.DataFrame(
        {
            "hard_gate_pass": [True, True, False],
            "regime_score": [3, 2, 5],
        }
    )
    variant = ErhVariant("test", regime_score_min=3, trail_arm=0.03, trail_giveback=0.03)

    active = variant_regime_active(frame, variant)

    assert active.tolist() == [True, False, False]


def test_build_erh_variants_uses_tiny_grid() -> None:
    variants = build_erh_variants()

    assert len(variants) == 8
    assert {variant.regime_score_min for variant in variants} == {3, 4}


def test_simulate_erh_variant_enters_next_hour_and_hits_hard_stop() -> None:
    index = pd.date_range(
        start="2026-01-01T00:00:00Z", periods=3, freq="h", tz="UTC"
    )
    execution = pd.DataFrame(
        [
            _execution_row(open=100.0, high=101.0, low=99.0, close=100.5),
            _execution_row(
                open=100.5,
                high=101.0,
                low=93.0,
                close=94.0,
                entry_trigger_base=False,
            ),
            _execution_row(
                open=94.0,
                high=94.5,
                low=93.5,
                close=94.2,
                entry_trigger_base=False,
            ),
        ],
        index=index,
    )
    variant = ErhVariant("test", regime_score_min=3, trail_arm=0.03, trail_giveback=0.03)

    trades = simulate_erh_variant(
        execution,
        variant,
        ErhConfig(),
        start=index[0],
        end=index[-1],
    )

    assert len(trades) == 1
    assert trades[0].entry_time == index[0].isoformat()
    assert trades[0].exit_reason == "hard_stop"
    assert math.isclose(trades[0].exit_price, 94.0)
    assert trades[0].net_pnl_usdc < -6.0


def test_simulate_erh_variant_exits_on_regime_break_next_open() -> None:
    index = pd.date_range(
        start="2026-01-01T00:00:00Z", periods=4, freq="h", tz="UTC"
    )
    execution = pd.DataFrame(
        [
            _execution_row(open=100.0, high=101.0, low=99.5, close=100.8),
            _execution_row(
                open=101.0,
                high=102.0,
                low=100.5,
                close=101.5,
                entry_trigger_base=False,
                hard_gate_pass=False,
            ),
            _execution_row(
                open=101.2,
                high=101.5,
                low=100.8,
                close=101.0,
                entry_trigger_base=False,
            ),
            _execution_row(
                open=101.0,
                high=101.2,
                low=100.0,
                close=100.5,
                entry_trigger_base=False,
            ),
        ],
        index=index,
    )
    variant = ErhVariant("test", regime_score_min=3, trail_arm=0.03, trail_giveback=0.03)

    trades = simulate_erh_variant(
        execution,
        variant,
        ErhConfig(),
        start=index[0],
        end=index[-1],
    )

    assert len(trades) == 1
    assert trades[0].exit_time == index[2].isoformat()
    assert trades[0].exit_reason == "regime_end"
