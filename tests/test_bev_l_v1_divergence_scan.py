from __future__ import annotations

import pandas as pd

from src.research.bev_l_v1_divergence_scan import (
    BevConfig,
    _assign_quintile,
    rolling_prior_percentile,
    scan_bev_fold,
)


def test_rolling_prior_percentile_uses_only_prior_values() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=5, freq="h", tz="UTC")
    values = pd.Series([1.0, 2.0, 3.0, 2.0, 5.0], index=index)

    result = rolling_prior_percentile(values, lookback=3, min_periods=2)

    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == 1.0
    assert result.iloc[3] == 2 / 3
    assert result.iloc[4] == 1.0


def test_assign_quintile_uses_training_thresholds() -> None:
    thresholds = [0.1, 0.2, 0.3, 0.4]

    assert _assign_quintile(0.05, thresholds) == 0
    assert _assign_quintile(0.20, thresholds) == 2
    assert _assign_quintile(0.45, thresholds) == 4
    assert _assign_quintile(0.45, []) is None


def test_scan_bev_fold_detects_q5_positive_structure() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=100, freq="h", tz="UTC")
    block = [0.05] * 5 + [0.25] * 5 + [0.45] * 5 + [0.65] * 5 + [0.90] * 5
    divergence = (block * 4)[: len(index)]
    opens = [100.0] * len(index)
    for pos in range(1, len(index)):
        opens[pos] = opens[pos - 1] * (1.01 if divergence[pos - 1] > 0.8 else 0.99)
    execution = pd.DataFrame(
        {
            "open": opens,
            "close": opens,
            "divergence_score": divergence,
            "ethbtc_ret_24h": [0.01] * len(index),
        },
        index=index,
    )
    config = BevConfig(
        min_q5_validation_count=1,
        min_q5_minus_q1_net_return=0.0,
    )

    report = scan_bev_fold(
        execution,
        index[0],
        index[49],
        index[50],
        index[-3],
        horizon_hours=1,
        config=config,
    )

    assert report["row_count"] > 0
    assert report["best_quintile"]["quintile"] == 4
    assert report["fold_passed"] is True


def test_scan_bev_fold_rejects_negative_q5() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=80, freq="h", tz="UTC")
    divergence = [float(i % 50) / 50.0 for i in range(len(index))]
    execution = pd.DataFrame(
        {
            "open": [100.0 - i * 0.01 for i in range(len(index))],
            "close": [100.0 - i * 0.01 for i in range(len(index))],
            "divergence_score": divergence,
            "ethbtc_ret_24h": [0.01] * len(index),
        },
        index=index,
    )

    report = scan_bev_fold(
        execution,
        index[0],
        index[49],
        index[50],
        index[-5],
        horizon_hours=1,
        config=BevConfig(min_q5_validation_count=1),
    )

    assert report["fold_passed"] is False
    assert "q5_mean_not_positive" in report["rejection_reasons"]
