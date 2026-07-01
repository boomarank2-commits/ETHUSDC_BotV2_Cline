from __future__ import annotations

import math

import pandas as pd

from src.research.brh_v1 import (
    BrhConfig,
    BrhThresholds,
    BrhVariant,
    brh_signal_passes,
    build_brh_variants,
    calibrate_brh_thresholds,
    simulate_brh_variant,
)
from src.research.erh_v1 import ErhConfig


def _zero_cost_config() -> BrhConfig:
    return BrhConfig(
        trading_cost_config=ErhConfig(fee_rate_per_side=0.0, slippage_rate_per_side=0.0)
    )


def _row(**overrides: float | bool) -> dict:
    row = {
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "brh_signal_update_bar": True,
        "btc_4h_drawdown_from_20d_high": -0.01,
        "btc_4h_close_vs_ema20": 0.02,
        "ethbtc_4h_ret_6": -0.03,
        "eth_4h_dist_to_20d_high": -0.12,
        "eth_of_ofi_4h_3sum": -0.02,
        "usdc_dev": 0.0001,
        "basis_usdt_4h": 0.0,
    }
    row.update(overrides)
    return row


def test_build_brh_variants_uses_tiny_fixed_grid() -> None:
    variants = build_brh_variants()

    assert len(variants) == 7
    assert variants[0].variant_id == "brh_btc_risk_on_72h"
    assert all(variant.hold_hours == 72 for variant in variants)


def test_calibrate_brh_thresholds_uses_only_requested_window() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=10, freq="4h", tz="UTC")
    frame = pd.DataFrame(
        {
            "brh_signal_update_bar": [True] * 10,
            "btc_4h_drawdown_from_20d_high": list(range(10)),
            "btc_4h_close_vs_ema20": list(range(10)),
            "ethbtc_4h_ret_6": list(range(10)),
            "eth_4h_dist_to_20d_high": list(range(10)),
            "eth_of_ofi_4h_3sum": list(range(10)),
        },
        index=index,
    )

    thresholds = calibrate_brh_thresholds(frame, index[0], index[4])

    assert math.isclose(thresholds.btc_drawdown_q80, 3.2)
    assert math.isclose(thresholds.ethbtc_ret_q20, 0.8)


def test_brh_signal_passes_requires_risk_on_and_selected_dip() -> None:
    thresholds = BrhThresholds(
        btc_drawdown_q80=-0.02,
        btc_ema_q80=0.01,
        ethbtc_ret_q20=-0.02,
        eth_dist_q20=-0.10,
        eth_ofi_q40=0.0,
    )
    variant = BrhVariant("test", use_ethbtc_ret_q20=True)

    assert brh_signal_passes(
        pd.Series(_row()),
        variant,
        thresholds,
        BrhConfig(),
    )
    assert not brh_signal_passes(
        pd.Series(_row(ethbtc_4h_ret_6=0.01)),
        variant,
        thresholds,
        BrhConfig(),
    )


def test_simulate_brh_variant_enters_next_open_and_blocks_overlap() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=8, freq="h", tz="UTC")
    rows = []
    for position, timestamp in enumerate(index):
        rows.append(
            _row(
                open=100.0 + position,
                high=101.0 + position,
                low=99.0 + position,
                close=100.5 + position,
                brh_signal_update_bar=timestamp in {index[0], index[1], index[4]},
            )
        )
    execution = pd.DataFrame(rows, index=index)
    thresholds = BrhThresholds(
        btc_drawdown_q80=-0.02,
        btc_ema_q80=0.01,
        ethbtc_ret_q20=-0.02,
        eth_dist_q20=-0.10,
        eth_ofi_q40=0.0,
    )
    variant = BrhVariant("test", hold_hours=2)

    trades = simulate_brh_variant(
        execution,
        variant,
        thresholds,
        _zero_cost_config(),
        start=index[0],
        end=index[-1],
    )

    assert len(trades) == 2
    assert trades[0].signal_time == index[0].isoformat()
    assert trades[0].entry_time == index[1].isoformat()
    assert trades[0].exit_time == index[3].isoformat()
    assert trades[1].signal_time == index[4].isoformat()
    assert trades[1].entry_time == index[5].isoformat()
    assert trades[1].exit_time == index[7].isoformat()
    assert math.isclose(trades[0].net_return, 103.0 / 101.0 - 1.0)
