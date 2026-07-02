from __future__ import annotations

import math

import pandas as pd

from src.research.brh_selection_edge_robustness_v2check import (
    BrhSelectionRobustnessConfig,
    trim_top_positive_values,
    unconditional_eth_windows,
    variant_robustness_gatekeeper,
)
from src.research.brh_v1 import BrhConfig
from src.research.erh_v1 import ErhConfig


def _zero_cost_brh_config() -> BrhConfig:
    return BrhConfig(
        trading_cost_config=ErhConfig(fee_rate_per_side=0.0, slippage_rate_per_side=0.0)
    )


def _execution_frame() -> pd.DataFrame:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=12, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "open": [
                100.0,
                100.0,
                102.0,
                104.0,
                104.0,
                106.0,
                108.0,
                110.0,
                112.0,
                114.0,
                116.0,
                118.0,
            ],
            "high": [
                101.0,
                103.0,
                105.0,
                105.0,
                107.0,
                109.0,
                111.0,
                113.0,
                115.0,
                117.0,
                119.0,
                120.0,
            ],
            "low": [
                99.0,
                99.0,
                101.0,
                103.0,
                103.0,
                105.0,
                107.0,
                109.0,
                111.0,
                113.0,
                115.0,
                117.0,
            ],
            "close": [
                100.0,
                102.0,
                104.0,
                104.0,
                106.0,
                108.0,
                110.0,
                112.0,
                114.0,
                116.0,
                118.0,
                119.0,
            ],
            "brh_signal_update_bar": [
                True,
                False,
                False,
                True,
                False,
                False,
                True,
                False,
                False,
                True,
                False,
                False,
            ],
            "btc_4h_drawdown_from_20d_high": [-0.01] * 12,
            "usdc_dev": [0.0001] * 12,
            "basis_usdt_4h": [0.0] * 12,
        },
        index=index,
    )


def test_trim_top_positive_values_removes_largest_winners_only() -> None:
    assert trim_top_positive_values([5.0, -2.0, 3.0, 1.0], 2) == [-2.0, 1.0]
    assert trim_top_positive_values([-5.0, -2.0], 2) == [-5.0, -2.0]


def test_unconditional_eth_windows_use_next_open_and_horizon_open() -> None:
    execution = _execution_frame()
    config = BrhSelectionRobustnessConfig(hold_hours=2)

    windows = unconditional_eth_windows(
        execution,
        execution.index[0],
        execution.index[-1],
        config,
        _zero_cost_brh_config(),
        enforce_non_overlap=False,
    )

    assert len(windows) == 3
    assert windows[0].signal_time == execution.index[0].isoformat()
    assert windows[0].entry_time == execution.index[1].isoformat()
    assert windows[0].exit_time == execution.index[3].isoformat()
    assert math.isclose(windows[0].net_return, 104.0 / 100.0 - 1.0)


def test_variant_robustness_gatekeeper_can_pass_synthetic_broad_variant() -> None:
    execution = _execution_frame()
    config = BrhSelectionRobustnessConfig(
        hold_hours=2,
        min_total_validation_trades=3,
        min_average_trades_per_fold=1.0,
        min_positive_folds=1,
        min_positive_edge_folds=1,
        min_profit_factor=1.0,
        max_profit_factor_for_selection=100.0,
        min_cost_robust_profit_factor=1.0,
        min_leave_one_out_profit_factor=1.0,
        min_leave_two_out_profit_factor=1.0,
        max_top1_pnl_share=1.0,
        max_top2_pnl_share=1.0,
        require_strategy_beats_buy_hold_per_day=False,
        top_trim_count=1,
    )
    variant_report = {
        "variant": {"variant_id": "brh_btc_risk_on_72h"},
        "eligible_for_blindtest": True,
        "positive_folds": 1,
        "slippage_robustness_2bp_profit_factor": 2.0,
        "validation_summary": {
            "trades": 3,
            "pnl_usdc": 12.0,
            "profit_factor": 2.0,
            "median_trade_net_pnl": 4.0,
        },
        "folds": [
            {
                "fold_index": "1",
                "validation_start": execution.index[0].isoformat(),
                "validation_end": execution.index[-1].isoformat(),
                "thresholds": {
                    "btc_drawdown_q80": -0.02,
                    "btc_ema_q80": 0.0,
                    "ethbtc_ret_q20": 0.0,
                    "eth_dist_q20": 0.0,
                    "eth_ofi_q40": 0.0,
                },
            }
        ],
    }
    validation_trades = pd.DataFrame(
        {
            "variant_id": ["brh_btc_risk_on_72h"] * 3,
            "signal_time": [execution.index[0], execution.index[3], execution.index[6]],
            "entry_time": [execution.index[1], execution.index[4], execution.index[7]],
            "exit_time": [execution.index[3], execution.index[6], execution.index[9]],
            "net_return": [0.10, 0.08, 0.06],
            "net_pnl_usdc": [10.0, 8.0, 6.0],
        }
    )

    result = variant_robustness_gatekeeper(
        execution,
        validation_trades,
        variant_report,
        buy_hold_usdc_per_day=None,
        validation_period_days=1.0,
        config=config,
        brh_config=_zero_cost_brh_config(),
    )

    assert result["aggregate"]["passes_robust_gatekeeper"] is True
    assert result["robust_gatekeeper_rejection_reasons"] == []
