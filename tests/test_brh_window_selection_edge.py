from __future__ import annotations

import math

import pandas as pd

from src.research.brh_v1 import BrhConfig, BrhThresholds
from src.research.brh_window_selection_edge import (
    baseline_risk_on_windows,
    risk_on_signal_passes,
    variant_window_selection_edge,
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
            "open": [100.0, 100.0, 102.0, 110.0, 105.0, 100.0, 95.0, 90.0],
            "high": [101.0, 103.0, 104.0, 112.0, 106.0, 101.0, 96.0, 91.0],
            "low": [99.0, 99.0, 100.0, 108.0, 104.0, 99.0, 94.0, 89.0],
            "close": [100.0, 102.0, 109.0, 111.0, 104.0, 96.0, 91.0, 90.0],
            "brh_signal_update_bar": [True, False, False, False, True, False, False, False],
            "btc_4h_drawdown_from_20d_high": [-0.01] * 8,
            "usdc_dev": [0.0001] * 8,
            "basis_usdt_4h": [0.0] * 8,
        },
        index=index,
    )


def _thresholds() -> BrhThresholds:
    return BrhThresholds(
        btc_drawdown_q80=-0.02,
        btc_ema_q80=0.0,
        ethbtc_ret_q20=0.0,
        eth_dist_q20=0.0,
        eth_ofi_q40=0.0,
    )


def test_risk_on_signal_passes_requires_btc_q80_and_sanity_filters() -> None:
    row = pd.Series(
        {
            "btc_4h_drawdown_from_20d_high": -0.01,
            "usdc_dev": 0.0001,
            "basis_usdt_4h": 0.0,
        }
    )

    assert risk_on_signal_passes(row, _thresholds(), BrhConfig())
    weak_btc_row = row.copy()
    weak_btc_row["btc_4h_drawdown_from_20d_high"] = -0.03
    assert not risk_on_signal_passes(
        weak_btc_row,
        _thresholds(),
        BrhConfig(),
    )


def test_baseline_risk_on_windows_use_next_open_and_horizon_open() -> None:
    execution = _execution_frame()

    windows = baseline_risk_on_windows(
        execution,
        execution.index[0],
        execution.index[-1],
        _thresholds(),
        _zero_cost_brh_config(),
        hold_hours=2,
    )

    assert len(windows) == 2
    assert windows[0].signal_time == execution.index[0].isoformat()
    assert windows[0].entry_time == execution.index[1].isoformat()
    assert windows[0].exit_time == execution.index[3].isoformat()
    assert math.isclose(windows[0].net_return, 110.0 / 100.0 - 1.0)


def test_variant_window_selection_edge_compares_selected_to_risk_on_baseline() -> None:
    execution = _execution_frame()
    variant_report = {
        "variant": {"variant_id": "test_variant"},
        "eligible_for_blindtest": True,
        "folds": [
            {
                "fold_index": "1",
                "validation_start": execution.index[0].isoformat(),
                "validation_end": execution.index[-1].isoformat(),
                "thresholds": _thresholds().__dict__,
            }
        ],
    }
    validation_trades = pd.DataFrame(
        {
            "variant_id": ["test_variant"],
            "signal_time": [execution.index[0]],
            "entry_time": [execution.index[1]],
            "exit_time": [execution.index[3]],
            "net_return": [110.0 / 100.0 - 1.0],
            "net_pnl_usdc": [(110.0 / 100.0 - 1.0) * 100.0],
        }
    )

    result = variant_window_selection_edge(
        execution,
        validation_trades,
        variant_report,
        config=type(
            "Config",
            (),
            {
                "hold_hours": 2,
                "min_aggregate_edge_after_cost": 0.0,
                "min_positive_edge_folds": 1,
                "min_worst_fold_edge_after_cost": -0.005,
            },
        )(),
        brh_config=_zero_cost_brh_config(),
    )

    assert result["aggregate"]["window_selection_edge_after_cost_return"] > 0
    assert result["aggregate"]["passes_window_selection_edge_check"] is True
