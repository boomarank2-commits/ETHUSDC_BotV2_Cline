from __future__ import annotations

import math

import pandas as pd

from src.research.brh_v1 import BrhConfig, calibrate_brh_thresholds
from src.research.brh_v1_diagnostics import (
    concentration_metrics,
    horizon_decay_metrics,
    selected_window_attribution,
    verify_blindtest_threshold_source,
)
from src.research.erh_v1 import ErhConfig


def _zero_cost_brh_config() -> BrhConfig:
    return BrhConfig(
        trading_cost_config=ErhConfig(fee_rate_per_side=0.0, slippage_rate_per_side=0.0)
    )


def _execution_frame() -> pd.DataFrame:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=8, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "open": [100.0, 102.0, 104.0, 103.0, 106.0, 105.0, 108.0, 110.0],
            "high": [101.0, 105.0, 106.0, 104.0, 108.0, 107.0, 111.0, 112.0],
            "low": [99.0, 101.0, 102.0, 100.0, 104.0, 103.0, 106.0, 109.0],
            "close": [100.5, 103.0, 103.5, 102.0, 105.0, 106.0, 109.0, 111.0],
            "brh_signal_update_bar": [True] * 8,
            "btc_4h_drawdown_from_20d_high": list(range(8)),
            "btc_4h_close_vs_ema20": list(range(8)),
            "ethbtc_4h_ret_6": list(range(8)),
            "eth_4h_dist_to_20d_high": list(range(8)),
            "eth_of_ofi_4h_3sum": list(range(8)),
        },
        index=index,
    )


def test_verify_blindtest_threshold_source_matches_training_only_recalculation() -> None:
    execution = _execution_frame()
    training_start = execution.index[0]
    blindtest_start = execution.index[5]
    thresholds = calibrate_brh_thresholds(
        execution,
        training_start,
        blindtest_start - pd.Timedelta(hours=1),
    )
    report = {"selected_thresholds": thresholds.__dict__}

    verification = verify_blindtest_threshold_source(
        report,
        execution,
        training_start,
        blindtest_start,
    )

    assert verification["blindtest_quantile_thresholds_source"] == "training_only"
    assert verification["matches_recalculated_training_only_thresholds"] is True
    assert verification["max_abs_threshold_diff"] == 0.0


def test_concentration_metrics_reports_top_share_and_leave_two_out_pf() -> None:
    trades = pd.DataFrame({"net_pnl_usdc": [10.0, -1.0, -1.0, 5.0]})

    metrics = concentration_metrics(trades)

    assert metrics["trade_count"] == 4
    assert metrics["total_pnl_usdc"] == 13.0
    assert math.isclose(metrics["top_trade_pnl_share"]["1"], 10.0 / 13.0)
    assert metrics["leave_two_out_profit_factor"] == 0.0


def test_horizon_decay_metrics_uses_existing_trade_entry_path() -> None:
    execution = _execution_frame()
    trades = pd.DataFrame(
        {
            "entry_time": [execution.index[1]],
            "entry_price": [102.0],
            "exit_price": [103.0],
            "net_return": [103.0 / 102.0 - 1.0],
            "net_pnl_usdc": [(103.0 / 102.0 - 1.0) * 100.0],
        }
    )

    metrics = horizon_decay_metrics(
        trades,
        execution,
        horizons_hours=(1, 2),
        cost_config=_zero_cost_brh_config(),
    )

    assert metrics["trade_count"] == 1
    assert math.isclose(
        metrics["by_horizon"]["1"]["mean_net_pnl_usdc"],
        (104.0 / 102.0 - 1.0) * 100.0,
    )
    assert metrics["by_horizon"]["2"]["mean_mfe_ret"] > 0


def test_selected_window_attribution_is_zero_for_fixed_spot_hold() -> None:
    execution = _execution_frame()
    trades = pd.DataFrame(
        {
            "entry_price": [102.0],
            "exit_price": [106.0],
            "net_return": [106.0 / 102.0 - 1.0],
        }
    )

    attribution = selected_window_attribution(
        trades,
        execution,
        _zero_cost_brh_config(),
    )

    assert attribution["trade_count"] == 1
    assert attribution["max_abs_signal_minus_same_window_eth"] == 0.0
