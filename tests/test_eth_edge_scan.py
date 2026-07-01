from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.research.erh_v1 import ErhConfig
from src.research.eth_edge_scan import (
    EdgeScanConfig,
    FeatureSpec,
    assign_time_folds,
    compute_forward_net_returns,
    scan_feature_horizon,
)


def _zero_cost_config() -> ErhConfig:
    return ErhConfig(fee_rate_per_side=0.0, slippage_rate_per_side=0.0)


def test_forward_returns_use_next_open_after_feature_row() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=4, freq="h", tz="UTC")
    execution = pd.DataFrame({"open": [100.0, 101.0, 103.0, 102.0]}, index=index)

    returns = compute_forward_net_returns(execution, 1, _zero_cost_config())

    assert returns.index[0] == index[0]
    assert math.isclose(returns.iloc[0], 103.0 / 101.0 - 1.0)


def test_assign_time_folds_are_chronological_and_clipped() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=6, freq="h", tz="UTC")

    folds = assign_time_folds(index, index[0], index[-1], fold_count=3)

    assert folds.iloc[0] == 0
    assert folds.iloc[-1] == 2
    assert folds.is_monotonic_increasing


def test_scan_feature_horizon_detects_low_quintile_reversion() -> None:
    periods = 240
    index = pd.date_range("2026-01-01T00:00:00Z", periods=periods, freq="h", tz="UTC")
    feature_values = np.tile(np.arange(5), periods // 5)
    step_returns = np.zeros(periods - 1)
    for signal_pos, feature_value in enumerate(feature_values[:-2]):
        step_returns[signal_pos + 1] = 0.01 if feature_value == 0 else -0.004

    opens = [100.0]
    for step_return in step_returns:
        opens.append(opens[-1] * (1.0 + step_return))
    execution = pd.DataFrame(
        {
            "open": opens,
            "synthetic_feature": feature_values,
        },
        index=index,
    )
    config = EdgeScanConfig(
        min_quintile_count=10,
        trading_cost_config=_zero_cost_config(),
    )

    result = scan_feature_horizon(
        execution=execution,
        feature=FeatureSpec(
            name="synthetic_feature",
            description="synthetic low-value reversion feature",
            high_value_interpretation="higher synthetic value",
        ),
        horizon_hours=1,
        training_start=index[0],
        blindtest_start=index[-1] + pd.Timedelta(hours=1),
        config=config,
    )

    assert result["status"] == "scanned"
    assert result["edge_candidate"] is True
    assert result["edge_side"] == "low_quintile_reversion_or_stress"
    assert result["best_quintile"]["quintile"] == 0
    assert result["best_quintile"]["positive_folds"] >= 3
