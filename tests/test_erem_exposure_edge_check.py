from __future__ import annotations

import pandas as pd

from src.research.erem_exposure_edge_check import (
    EremConfig,
    EremThresholds,
    EremVariant,
    erem_risk_off,
    simulate_erem_exposure,
)


def _execution_frame() -> pd.DataFrame:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=8, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "open": [100.0, 100.0, 98.0, 90.0, 82.0, 80.0, 88.0, 95.0],
            "high": [101.0, 101.0, 99.0, 91.0, 83.0, 89.0, 96.0, 96.0],
            "low": [99.0, 97.0, 89.0, 81.0, 79.0, 79.0, 87.0, 94.0],
            "close": [100.0, 98.0, 90.0, 82.0, 80.0, 88.0, 95.0, 95.0],
            "brh_signal_update_bar": [True] * 8,
            "btc_4h_drawdown_from_20d_high": [
                -0.01,
                -0.03,
                -0.04,
                -0.04,
                -0.01,
                -0.01,
                -0.01,
                -0.01,
            ],
            "btc_4h_close_vs_ema20": [0.01, -0.02, -0.03, -0.02, 0.01, 0.01, 0.01, 0.01],
        },
        index=index,
    )


def _zero_cost_config() -> EremConfig:
    return EremConfig(fee_rate_per_side=0.0, slippage_rate_per_side=0.0)


def test_erem_risk_off_uses_training_threshold_and_optional_ema_filter() -> None:
    row = pd.Series(
        {
            "btc_4h_drawdown_from_20d_high": -0.03,
            "btc_4h_close_vs_ema20": 0.01,
        }
    )
    thresholds = EremThresholds(btc_drawdown_threshold=-0.02)

    assert erem_risk_off(
        row,
        EremVariant("drawdown", btc_drawdown_quantile=0.20),
        thresholds,
    )

    assert not erem_risk_off(
        pd.Series(
            {
                "btc_4h_drawdown_from_20d_high": -0.01,
                "btc_4h_close_vs_ema20": 0.01,
            }
        ),
        EremVariant("drawdown", btc_drawdown_quantile=0.20),
        thresholds,
    )

    assert erem_risk_off(
        pd.Series(
            {
                "btc_4h_drawdown_from_20d_high": -0.01,
                "btc_4h_close_vs_ema20": -0.01,
            }
        ),
        EremVariant("ema", btc_drawdown_quantile=0.20, use_btc_ema_filter=True),
        thresholds,
    )


def test_simulate_erem_exposure_reduces_drawdown_during_risk_off_block() -> None:
    execution = _execution_frame()
    result = simulate_erem_exposure(
        execution,
        EremVariant("drawdown", btc_drawdown_quantile=0.20),
        EremThresholds(btc_drawdown_threshold=-0.02),
        execution.index[0],
        execution.index[-1],
        _zero_cost_config(),
    )

    assert result["erem_pnl_usdc"] > result["buy_hold_pnl_usdc"]
    assert result["erem_maxdd_usdc"] < result["buy_hold_maxdd_usdc"]
    assert result["time_in_market_pct"] < 1.0
    assert result["avoided_loss_blocks"]
