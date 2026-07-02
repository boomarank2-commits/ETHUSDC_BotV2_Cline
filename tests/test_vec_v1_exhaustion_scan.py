from __future__ import annotations

import pandas as pd

from src.research.erh_v1 import ErhConfig
from src.research.vec_v1_exhaustion_scan import (
    VecConfig,
    VecThresholds,
    VecVariant,
    resample_vec_candles,
    simulate_vec_variant,
    vec_signal_passes,
)


def test_resample_vec_candles_indexes_only_closed_bars_by_availability() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=30, freq="min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": [100.0] * 30,
            "high": [102.0] * 30,
            "low": [99.0] * 30,
            "close": [101.0] * 30,
            "quote_volume": [10.0] * 30,
            "trade_count": [1] * 30,
            "taker_buy_quote_volume": [3.0] * 30,
        },
        index=index,
    )

    bars = resample_vec_candles(frame, "15min")

    assert list(bars.index) == [
        pd.Timestamp("2026-01-01T00:15:00Z"),
        pd.Timestamp("2026-01-01T00:30:00Z"),
    ]
    assert bars.iloc[0]["quote_volume"] == 150.0
    assert bars.iloc[0]["taker_sell_quote_volume"] == 105.0
    assert bars.iloc[0]["sell_imbalance"] == 0.4


def test_vec_signal_requires_volume_selling_drop_and_reclaim() -> None:
    thresholds = VecThresholds(
        quote_volume_ratio_min=2.0,
        sell_imbalance_min=0.35,
        bar_return_max=-0.01,
        close_location_min=0.55,
    )
    variant = VecVariant("synthetic", timeframe="15min", hold_hours=1)
    row = pd.Series(
        {
            "quote_volume_ratio_20d": 2.4,
            "sell_imbalance": 0.42,
            "bar_return": -0.018,
            "close_location": 0.62,
        }
    )

    assert vec_signal_passes(row, variant, thresholds)

    weak_reclaim = row.copy()
    weak_reclaim["close_location"] = 0.40

    assert not vec_signal_passes(weak_reclaim, variant, thresholds)


def test_simulate_vec_variant_enters_next_bar_and_exits_fixed_horizon() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=7, freq="15min", tz="UTC")
    bars = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0, 104.0, 110.0, 111.0],
            "quote_volume_ratio_20d": [3.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            "sell_imbalance": [0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "bar_return": [-0.02, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "close_location": [0.8, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        },
        index=index,
    )
    trades = simulate_vec_variant(
        bars,
        VecVariant("synthetic", timeframe="15min", hold_hours=1),
        VecThresholds(
            quote_volume_ratio_min=2.0,
            sell_imbalance_min=0.35,
            bar_return_max=-0.01,
            close_location_min=0.55,
        ),
        VecConfig(
            trading_cost_config=ErhConfig(
                position_size_usdc=100.0,
                fee_rate_per_side=0.0,
                slippage_rate_per_side=0.0,
                extra_slippage_robustness_per_side=0.0,
            )
        ),
        index[0],
        index[-1],
    )

    assert len(trades) == 1
    assert trades[0].signal_time == index[0].isoformat()
    assert trades[0].entry_time == index[1].isoformat()
    assert trades[0].exit_time == index[5].isoformat()
    assert trades[0].entry_price == 101.0
    assert trades[0].exit_price == 110.0
    assert trades[0].net_pnl_usdc > 8.9
