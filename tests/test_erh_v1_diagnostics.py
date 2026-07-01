from __future__ import annotations

import pandas as pd

from src.research.erh_v1 import ErhConfig
from src.research.erh_v1_diagnostics import (
    FeatureAudit,
    build_regime_episodes,
    classify_root_cause,
    compute_unconditional_regime_returns,
)


def test_build_regime_episodes_counts_contiguous_blocks() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=6, freq="4h", tz="UTC")
    active = pd.Series([False, True, True, False, True, False], index=index)
    scores = pd.Series([0, 3, 4, 1, 5, 0], index=index)

    episodes = build_regime_episodes(active, scores)

    assert len(episodes) == 2
    assert episodes[0].start == index[1].isoformat()
    assert episodes[0].end == index[2].isoformat()
    assert episodes[0].duration_bars == 2
    assert episodes[0].avg_score == 3.5
    assert episodes[1].duration_bars == 1


def test_unconditional_regime_return_enters_and_exits_on_active_blocks() -> None:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=4, freq="h", tz="UTC")
    execution = pd.DataFrame(
        {
            "open": [100.0, 101.0, 103.0, 104.0],
            "close": [101.0, 103.0, 102.0, 105.0],
            "regime_score": [3, 3, 0, 0],
        },
        index=index,
    )
    active = pd.Series([True, True, False, False], index=index)

    episodes, summary = compute_unconditional_regime_returns(
        execution,
        active,
        ErhConfig(),
    )

    assert len(episodes) == 1
    assert episodes[0].start == index[1].isoformat()
    assert episodes[0].end == index[1].isoformat()
    assert episodes[0].exit_time == index[3].isoformat()
    assert episodes[0].net_pnl_usdc > 2.0
    assert summary["episode_count"] == 1


def test_classify_root_cause_flags_suspicious_gate_feature() -> None:
    audit = [
        FeatureAudit(
            feature="ethbtc_4h_close_vs_ema20",
            role="gate_ethbtc_trend",
            nan_count=0,
            nan_rate=0.0,
            first_valid_timestamp="2026-01-01T00:00:00+00:00",
            true_count=0,
            true_rate=0.0,
            block_count=100,
            block_rate=1.0,
        )
    ]

    category, evidence, _ = classify_root_cause(
        audit,
        hard_gate_episode_count=0,
        score3_episode_count=0,
        score3_return_summary={},
        signal_funnel=[],
    )

    assert category == "C_possible_implementation_or_gate_definition_bug"
    assert evidence


def test_classify_root_cause_detects_genuine_edge_problem() -> None:
    audit = [
        FeatureAudit(
            feature="ethbtc_4h_close_vs_ema20",
            role="gate_ethbtc_trend",
            nan_count=0,
            nan_rate=0.0,
            first_valid_timestamp="2026-01-01T00:00:00+00:00",
            true_count=40,
            true_rate=0.4,
            block_count=60,
            block_rate=0.6,
        )
    ]

    category, _, _ = classify_root_cause(
        audit,
        hard_gate_episode_count=10,
        score3_episode_count=10,
        score3_return_summary={
            "win_rate_per_episode": 0.40,
            "avg_return_per_episode": -0.001,
            "total_pnl_usdc": -5.0,
        },
        signal_funnel=[{"trades_actually_opened": 20}],
    )

    assert category == "B_genuine_edge_problem"
