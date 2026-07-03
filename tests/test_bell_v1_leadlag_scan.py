from __future__ import annotations

import math

import pandas as pd

from src.research.bell_v1_leadlag_scan import (
    BellConfig,
    BellMetricSummary,
    BellThresholds,
    BellVariant,
    _eligible,
    bell_signal_passes,
    simulate_bell_variant,
)


def _thresholds() -> BellThresholds:
    return BellThresholds(
        btc_eth_impulse_gap_1h_q80=0.01,
        btc_eth_impulse_gap_4h_q80=0.02,
        btc_4h_ret_2_q60=0.015,
        btc_4h_drawdown_q70=-0.04,
        eth_4h_dist_to_20d_high_q70=-0.01,
        ethbtc_4h_ret_2_q40=-0.005,
    )


def _passing_row(**overrides: float) -> pd.Series:
    values = {
        "btc_eth_impulse_gap_1h": 0.02,
        "btc_eth_impulse_gap_4h": 0.03,
        "btc_4h_ret_2": 0.025,
        "btc_4h_close_vs_ema20": 0.01,
        "btc_4h_drawdown_from_20d_high": -0.02,
        "eth_4h_dist_to_20d_high": -0.02,
        "ethbtc_4h_ret_2": -0.01,
        "usdc_dev": 0.0001,
        "basis_usdt_4h": 0.0001,
    }
    values.update(overrides)
    return pd.Series(values)


def test_bell_signal_passes_impulse_and_riskon_variants() -> None:
    config = BellConfig()
    thresholds = _thresholds()

    impulse = BellVariant("bell_btcimp_ethlag_24h", "btc_impulse_eth_lag", 24)
    riskon = BellVariant("bell_riskon_ethbtclag_24h", "btc_riskon_ethbtc_lag", 24)

    assert bell_signal_passes(_passing_row(), impulse, thresholds, config) is True
    assert bell_signal_passes(_passing_row(), riskon, thresholds, config) is True
    assert (
        bell_signal_passes(
            _passing_row(ethbtc_4h_ret_2=0.01),
            impulse,
            thresholds,
            config,
        )
        is False
    )
    assert (
        bell_signal_passes(
            _passing_row(usdc_dev=0.01),
            riskon,
            thresholds,
            config,
        )
        is False
    )


def test_simulate_bell_variant_uses_next_open_and_blocks_overlap() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=12, freq="h", tz="UTC")
    execution = pd.DataFrame(
        {
            "open": [100.0 + i for i in range(len(index))],
            "high": [101.0 + i for i in range(len(index))],
            "low": [99.0 + i for i in range(len(index))],
            "close": [100.5 + i for i in range(len(index))],
            "bell_signal_update_bar": [True] * len(index),
            "btc_eth_impulse_gap_1h": [0.02] * len(index),
            "btc_eth_impulse_gap_4h": [0.03] * len(index),
            "btc_4h_ret_2": [0.025] * len(index),
            "btc_4h_close_vs_ema20": [0.01] * len(index),
            "btc_4h_drawdown_from_20d_high": [-0.02] * len(index),
            "eth_4h_dist_to_20d_high": [-0.02] * len(index),
            "ethbtc_4h_ret_2": [-0.01] * len(index),
            "usdc_dev": [0.0001] * len(index),
            "basis_usdt_4h": [0.0001] * len(index),
            "eth_4h_ret_2": [0.0] * len(index),
        },
        index=index,
    )
    variant = BellVariant("bell_btcimp_ethlag_3h", "btc_impulse_eth_lag", 3)

    trades = simulate_bell_variant(
        execution,
        variant,
        _thresholds(),
        BellConfig(),
        index[0],
        index[-1],
    )

    assert len(trades) == 2
    assert trades[0].signal_time == index[0].isoformat()
    assert trades[0].entry_time == index[1].isoformat()
    assert trades[0].exit_time == index[4].isoformat()
    assert trades[1].entry_time == index[5].isoformat()


def test_eligible_blocks_failed_sanity_and_concentration() -> None:
    good_summary = BellMetricSummary(
        trades=60,
        pnl_usdc=12.0,
        usdc_per_day=0.05,
        profit_factor=1.5,
        median_trade_net_pnl=0.1,
        max_drawdown_usdc=3.0,
        max_drawdown_pct=0.03,
        top1_pnl_share=0.2,
        top2_pnl_share=0.35,
        leave_one_out_profit_factor=1.3,
        leave_two_out_profit_factor=1.2,
        positive_trade_count=38,
        negative_trade_count=22,
    )
    fold_summaries = [
        BellMetricSummary(
            trades=10,
            pnl_usdc=1.0,
            usdc_per_day=0.01,
            profit_factor=1.2,
            median_trade_net_pnl=0.1,
            max_drawdown_usdc=1.0,
            max_drawdown_pct=0.01,
            top1_pnl_share=0.2,
            top2_pnl_share=0.3,
            leave_one_out_profit_factor=1.1,
            leave_two_out_profit_factor=1.05,
            positive_trade_count=6,
            negative_trade_count=4,
        )
        for _ in range(6)
    ]
    eligible, reasons = _eligible(
        good_summary,
        fold_summaries,
        good_summary,
        baseline_pnl_usdc=0.0,
        config=BellConfig(),
        sanity_passed=True,
    )
    assert eligible is True
    assert reasons == []

    concentrated = BellMetricSummary(
        **{
            **good_summary.__dict__,
            "top2_pnl_share": 0.70,
            "leave_two_out_profit_factor": 0.9,
        }
    )
    eligible, reasons = _eligible(
        concentrated,
        fold_summaries,
        good_summary,
        baseline_pnl_usdc=0.0,
        config=BellConfig(),
        sanity_passed=False,
    )

    assert eligible is False
    assert "leadlag_sanity_scan_failed" in reasons
    assert "top2_pnl_share_above_limit" in reasons
    assert "leave_two_out_profit_factor_below_minimum" in reasons


def test_profit_factor_can_be_infinite_without_crashing() -> None:
    summary = BellMetricSummary(
        trades=60,
        pnl_usdc=12.0,
        usdc_per_day=0.05,
        profit_factor=math.inf,
        median_trade_net_pnl=0.1,
        max_drawdown_usdc=0.0,
        max_drawdown_pct=0.0,
        top1_pnl_share=0.2,
        top2_pnl_share=0.35,
        leave_one_out_profit_factor=math.inf,
        leave_two_out_profit_factor=math.inf,
        positive_trade_count=60,
        negative_trade_count=0,
    )

    eligible, reasons = _eligible(
        summary,
        [summary for _ in range(6)],
        summary,
        baseline_pnl_usdc=0.0,
        config=BellConfig(),
        sanity_passed=True,
    )

    assert eligible is False
    assert "profit_factor_above_overfit_limit" in reasons
