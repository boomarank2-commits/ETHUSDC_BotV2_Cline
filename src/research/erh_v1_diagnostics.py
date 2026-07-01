"""Diagnostics for ERH-v1 without changing the strategy.

The diagnostic separates four different causes that can all look like
``0/8 eligible`` in the final ERH-v1 report:

- no/few regimes,
- NaN or feature-join bugs,
- validation/fold mismatch,
- genuine lack of regime edge.

It does not optimize parameters, does not run blindtest selection and does not
change the UI/router path.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import REPORTS_DIR
from src.research.erh_v1 import (
    ERH_V1_VERSION,
    ErhConfig,
    ErhTrade,
    ErhVariant,
    _net_return,
    build_erh_feature_frames,
    build_erh_variants,
    latest_train_blind_window,
    load_1m_candles,
    simulate_erh_variant,
)

ERH_V1_DIAGNOSTIC_VERSION = "erh_v1_signal_funnel_diagnostic_20260701"


@dataclass(frozen=True)
class RegimeEpisode:
    """One contiguous active-regime block."""

    start: str
    end: str
    duration_bars: int
    avg_score: float
    min_score: int
    max_score: int


@dataclass(frozen=True)
class RegimeEpisodeReturn:
    """Unconditional return for one active-regime episode."""

    start: str
    end: str
    exit_time: str
    duration_hours: int
    entry_price: float
    exit_price: float
    net_return: float
    net_pnl_usdc: float
    avg_score: float


@dataclass(frozen=True)
class FeatureAudit:
    """NaN and condition audit for one ERH feature."""

    feature: str
    role: str
    nan_count: int
    nan_rate: float
    first_valid_timestamp: str | None
    true_count: int
    true_rate: float
    block_count: int
    block_rate: float


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, float) and math.isinf(value):
        return "inf"
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def _load_erh_frames() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.Timestamp,
    pd.Timestamp,
    pd.Timestamp,
]:
    eth_1m = load_1m_candles("ETHUSDC")
    training_start, blindtest_start, blindtest_end = latest_train_blind_window(eth_1m)
    window_start = training_start - pd.Timedelta(days=25)
    window_end = blindtest_end
    frames = {
        "ETHUSDC": eth_1m.loc[(eth_1m.index >= window_start) & (eth_1m.index <= window_end)],
        "BTCUSDC": load_1m_candles("BTCUSDC").loc[
            lambda frame: (frame.index >= window_start) & (frame.index <= window_end)
        ],
        "ETHBTC": load_1m_candles("ETHBTC").loc[
            lambda frame: (frame.index >= window_start) & (frame.index <= window_end)
        ],
        "ETHUSDT": load_1m_candles("ETHUSDT").loc[
            lambda frame: (frame.index >= window_start) & (frame.index <= window_end)
        ],
        "USDCUSDT": load_1m_candles("USDCUSDT").loc[
            lambda frame: (frame.index >= window_start) & (frame.index <= window_end)
        ],
    }
    execution, regime = build_erh_feature_frames(
        frames["ETHUSDC"],
        frames["ETHBTC"],
        frames["BTCUSDC"],
        frames["ETHUSDT"],
        frames["USDCUSDT"],
    )
    execution = execution.loc[
        (execution.index >= training_start) & (execution.index < blindtest_start)
    ]
    regime = regime.loc[(regime.index >= training_start) & (regime.index < blindtest_start)]
    return execution, regime, training_start, blindtest_start, blindtest_end


def build_regime_episodes(active: pd.Series, scores: pd.Series) -> list[RegimeEpisode]:
    """Return contiguous active periods for an indexed boolean series."""
    episodes: list[RegimeEpisode] = []
    active = active.fillna(False).astype(bool)
    start: pd.Timestamp | None = None
    previous: pd.Timestamp | None = None
    for timestamp, is_active in active.items():
        if is_active and start is None:
            start = timestamp
        if not is_active and start is not None and previous is not None:
            score_slice = scores.loc[start:previous].dropna()
            episodes.append(_episode_from_slice(start, previous, score_slice))
            start = None
        previous = timestamp
    if start is not None and previous is not None:
        score_slice = scores.loc[start:previous].dropna()
        episodes.append(_episode_from_slice(start, previous, score_slice))
    return episodes


def _episode_from_slice(
    start: pd.Timestamp,
    end: pd.Timestamp,
    score_slice: pd.Series,
) -> RegimeEpisode:
    duration_bars = int(len(score_slice)) if not score_slice.empty else 0
    return RegimeEpisode(
        start=start.isoformat(),
        end=end.isoformat(),
        duration_bars=duration_bars,
        avg_score=float(score_slice.mean()) if not score_slice.empty else math.nan,
        min_score=int(score_slice.min()) if not score_slice.empty else 0,
        max_score=int(score_slice.max()) if not score_slice.empty else 0,
    )


def build_feature_audit(regime: pd.DataFrame) -> list[FeatureAudit]:
    """Audit each ERH-v1 hard gate and score component on training data."""
    conditions: dict[str, tuple[str, pd.Series]] = {
        "eth_4h_close_vs_ema20": ("gate_eth_trend", regime["eth_4h_close_vs_ema20"] > 0),
        "ethbtc_4h_close_vs_ema20": (
            "gate_ethbtc_trend",
            regime["ethbtc_4h_close_vs_ema20"] > 0,
        ),
        "ethbtc_4h_slope_6": ("gate_ethbtc_slope", regime["ethbtc_4h_slope_6"] > 0),
        "btc_4h_drawdown_from_20d_high": (
            "gate_btc_not_crash",
            regime["btc_4h_drawdown_from_20d_high"] > -0.15,
        ),
        "eth_of_4h_buy_share_3avg": (
            "gate_orderflow",
            regime["eth_of_4h_buy_share_3avg"] >= 0.505,
        ),
        "usdc_dev": ("gate_usdc", regime["usdc_dev"] <= 0.0015),
        "basis_usdt_4h": ("gate_basis", regime["basis_usdt_4h"].abs() <= 0.0015),
        "eth_4h_ret_6": ("score_eth_24h_ret", regime["eth_4h_ret_6"] > 0.02),
        "ethbtc_4h_ret_6": ("score_ethbtc_24h_ret", regime["ethbtc_4h_ret_6"] > 0.01),
        "ethbtc_4h_above_ema_streak": (
            "score_ethbtc_streak",
            regime["ethbtc_4h_above_ema_streak"] >= 3,
        ),
        "eth_of_ofi_4h_3sum": ("score_orderflow_3sum", regime["eth_of_ofi_4h_3sum"] > 0.03),
        "btc_4h_close_vs_ema20": ("score_btc_constructive", regime["btc_4h_close_vs_ema20"] > 0),
    }
    audits: list[FeatureAudit] = []
    denominator = max(len(regime), 1)
    for feature, (role, condition) in conditions.items():
        values = regime[feature]
        valid_condition = condition & values.notna()
        true_count = int(valid_condition.sum())
        nan_count = int(values.isna().sum())
        first_valid = values.first_valid_index()
        audits.append(
            FeatureAudit(
                feature=feature,
                role=role,
                nan_count=nan_count,
                nan_rate=nan_count / denominator,
                first_valid_timestamp=first_valid.isoformat() if first_valid is not None else None,
                true_count=true_count,
                true_rate=true_count / denominator,
                block_count=denominator - true_count,
                block_rate=(denominator - true_count) / denominator,
            )
        )
    return audits


def compute_unconditional_regime_returns(
    execution: pd.DataFrame,
    active: pd.Series,
    config: ErhConfig,
) -> tuple[list[RegimeEpisodeReturn], dict[str, Any]]:
    """Hold ETHUSDC only while the provided active regime is true.

    ERH feature rows are indexed by availability time. To stay consistent with
    ``simulate_erh_variant``, an active transition can only be entered on the
    next execution row's open, and an inactive transition can only be exited on
    the next execution row's open.
    """
    active = active.reindex(execution.index).fillna(False).astype(bool)
    scores = execution["regime_score"].reindex(execution.index)
    episodes: list[RegimeEpisodeReturn] = []
    signal_start_pos: int | None = None
    entry_pos: int | None = None
    active_end_pos: int | None = None
    active_values = active.to_numpy(dtype=bool)

    for position, is_active in enumerate(active_values):
        if is_active:
            if signal_start_pos is None:
                signal_start_pos = position
                entry_pos = position + 1 if position + 1 < len(execution) else None
            active_end_pos = position
            continue

        if signal_start_pos is not None and active_end_pos is not None:
            if entry_pos is not None:
                exit_pos = position + 1 if position + 1 < len(execution) else position
                episodes.append(
                    _unconditional_episode_from_positions(
                        execution=execution,
                        scores=scores,
                        signal_start_pos=signal_start_pos,
                        entry_pos=entry_pos,
                        active_end_pos=active_end_pos,
                        exit_pos=exit_pos,
                        exit_at_close=exit_pos == position,
                        config=config,
                    )
                )
            signal_start_pos = None
            entry_pos = None
            active_end_pos = None

    if signal_start_pos is not None and entry_pos is not None and active_end_pos is not None:
        episodes.append(
            _unconditional_episode_from_positions(
                execution=execution,
                scores=scores,
                signal_start_pos=signal_start_pos,
                entry_pos=entry_pos,
                active_end_pos=active_end_pos,
                exit_pos=len(execution) - 1,
                exit_at_close=True,
                config=config,
            )
        )

    pnls = [episode.net_pnl_usdc for episode in episodes]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [-pnl for pnl in pnls if pnl < 0]
    profit_factor = None
    if losses:
        profit_factor = sum(wins) / sum(losses) if sum(losses) > 0 else None
    elif wins:
        profit_factor = math.inf

    full_return, _ = _net_return(
        float(execution.iloc[0]["open"]),
        float(execution.iloc[-1]["close"]),
        config,
    )
    summary = {
        "episode_count": len(episodes),
        "total_pnl_usdc": float(sum(pnls)),
        "avg_return_per_episode": float(np.mean([e.net_return for e in episodes]))
        if episodes
        else None,
        "win_rate_per_episode": len(wins) / len(episodes) if episodes else None,
        "profit_factor": _to_jsonable(profit_factor),
        "buy_and_hold_full_period_net_return": full_return,
        "buy_and_hold_full_period_pnl_usdc": full_return * config.position_size_usdc,
    }
    return episodes, summary


def _unconditional_episode_from_positions(
    execution: pd.DataFrame,
    scores: pd.Series,
    signal_start_pos: int,
    entry_pos: int,
    active_end_pos: int,
    exit_pos: int,
    exit_at_close: bool,
    config: ErhConfig,
) -> RegimeEpisodeReturn:
    entry_timestamp = execution.index[entry_pos]
    exit_timestamp = execution.index[exit_pos]
    reported_end_pos = max(entry_pos, active_end_pos)
    active_end = execution.index[reported_end_pos]
    entry_price = float(execution.iloc[entry_pos]["open"])
    exit_column = "close" if exit_at_close else "open"
    exit_price = float(execution.iloc[exit_pos][exit_column])
    net_return, _ = _net_return(entry_price, exit_price, config)
    score_slice = scores.iloc[signal_start_pos : active_end_pos + 1].dropna()
    return RegimeEpisodeReturn(
        start=entry_timestamp.isoformat(),
        end=active_end.isoformat(),
        exit_time=exit_timestamp.isoformat(),
        duration_hours=int((exit_timestamp - entry_timestamp).total_seconds() // 3600),
        entry_price=entry_price,
        exit_price=exit_price,
        net_return=net_return,
        net_pnl_usdc=net_return * config.position_size_usdc,
        avg_score=float(score_slice.mean()) if not score_slice.empty else math.nan,
    )


def _exit_reason_counts(trades: list[ErhTrade]) -> dict[str, int]:
    return dict(Counter(trade.exit_reason for trade in trades))


def build_signal_funnel(
    execution: pd.DataFrame,
    variants: list[ErhVariant],
    config: ErhConfig,
    training_start: pd.Timestamp,
    blindtest_start: pd.Timestamp,
) -> list[dict[str, Any]]:
    """Count where ERH-v1 proposals disappear before eligibility checks."""
    rows: list[dict[str, Any]] = []
    for variant in variants:
        active = (
            execution["hard_gate_pass"].fillna(False).astype(bool)
            & (execution["regime_score"] >= variant.regime_score_min)
        )
        trigger = active & execution["entry_trigger_base"].fillna(False).astype(bool)
        blocked = trigger & execution["no_chase_block"].fillna(False).astype(bool)
        entry_bars = trigger & ~blocked
        trades = simulate_erh_variant(
            execution,
            variant,
            config,
            training_start,
            blindtest_start - pd.Timedelta(hours=1),
        )
        rows.append(
            {
                "variant_id": variant.variant_id,
                "regime_score_min": variant.regime_score_min,
                "bars_total": int(len(execution)),
                "regime_active_bars": int(active.sum()),
                "entry_trigger_bars": int(trigger.sum()),
                "trigger_blocked_by_no_chase": int(blocked.sum()),
                "candidate_entry_bars_after_no_chase": int(entry_bars.sum()),
                "trades_actually_opened": len(trades),
                "exit_reason_counts": _exit_reason_counts(trades),
            }
        )
    return rows


def classify_root_cause(
    feature_audit: list[FeatureAudit],
    hard_gate_episode_count: int,
    score3_episode_count: int,
    score3_return_summary: dict[str, Any],
    signal_funnel: list[dict[str, Any]],
) -> tuple[str, list[str], str]:
    """Classify the current ERH-v1 failure without changing the strategy."""
    evidence: list[str] = []
    suspicious_features = [
        audit
        for audit in feature_audit
        if audit.role.startswith("gate_")
        and (audit.true_rate < 0.02 or audit.nan_rate > 0.50)
    ]
    if hard_gate_episode_count == 0 or suspicious_features:
        evidence.append(
            "At least one hard-gate feature almost never passes or is heavily NaN, "
            "or no hard-gate episode exists. Nearly-always-true sanity gates are "
            "not treated as bugs because they do not block entries."
        )
        evidence.extend(
            f"{audit.role}: true_rate={audit.true_rate:.4f}, nan_rate={audit.nan_rate:.4f}"
            for audit in suspicious_features
        )
        return (
            "C_possible_implementation_or_gate_definition_bug",
            evidence,
            "Audit the suspicious gate feature definitions before changing strategy logic.",
        )

    if score3_episode_count < 8:
        evidence.append(f"Only {score3_episode_count} score>=3 episodes found in training.")
        return (
            "A_frequency_or_validation_design_problem",
            evidence,
            (
                "Do not tune exits. Decide whether ERH-v1 is too rare or needs "
                "episode-based validation."
            ),
        )

    win_rate = score3_return_summary.get("win_rate_per_episode")
    avg_return = score3_return_summary.get("avg_return_per_episode")
    total_pnl = score3_return_summary.get("total_pnl_usdc")
    if (
        win_rate is not None
        and avg_return is not None
        and total_pnl is not None
        and win_rate > 0.60
        and avg_return > 0.01
        and total_pnl > 0
    ):
        evidence.append(
            "Unconditional score>=3 regime holding is positive, but the strategy "
            "did not pass walkforward."
        )
        return (
            "D_entry_exit_or_validation_mismatch",
            evidence,
            "Inspect entry timing and fold design; do not loosen regime gates yet.",
        )

    max_trades = max((row["trades_actually_opened"] for row in signal_funnel), default=0)
    evidence.append(
        "Regime episodes exist, trades are generated, but unconditional regime "
        "returns and/or validation performance are not robust."
    )
    evidence.append(f"Maximum full-training ERH trade count by variant: {max_trades}.")
    return (
        "B_genuine_edge_problem",
        evidence,
        "Treat ERH-v1 as likely non-trading edge unless a concrete implementation bug is found.",
    )


def run_erh_v1_diagnostics(config: ErhConfig | None = None) -> dict[str, Any]:
    """Run ERH-v1 signal-funnel diagnostics only."""
    active_config = config or ErhConfig(output_dir=REPORTS_DIR / "research" / "erh_v1_diag")
    execution, regime, training_start, blindtest_start, blindtest_end = _load_erh_frames()
    variants = build_erh_variants()

    hard_gate_active = regime["hard_gate_pass"].fillna(False).astype(bool)
    score3_active_4h = hard_gate_active & (regime["regime_score"] >= 3)
    score4_active_4h = hard_gate_active & (regime["regime_score"] >= 4)
    hard_gate_episodes = build_regime_episodes(hard_gate_active, regime["regime_score"])
    score3_episodes = build_regime_episodes(score3_active_4h, regime["regime_score"])
    score4_episodes = build_regime_episodes(score4_active_4h, regime["regime_score"])
    feature_audit = build_feature_audit(regime)
    signal_funnel = build_signal_funnel(
        execution,
        variants,
        active_config,
        training_start,
        blindtest_start,
    )

    score3_active_1h = (
        execution["hard_gate_pass"].fillna(False).astype(bool)
        & (execution["regime_score"] >= 3)
    )
    score4_active_1h = (
        execution["hard_gate_pass"].fillna(False).astype(bool)
        & (execution["regime_score"] >= 4)
    )
    score3_returns, score3_return_summary = compute_unconditional_regime_returns(
        execution,
        score3_active_1h,
        active_config,
    )
    score4_returns, score4_return_summary = compute_unconditional_regime_returns(
        execution,
        score4_active_1h,
        active_config,
    )
    root_cause, evidence, next_step = classify_root_cause(
        feature_audit,
        len(hard_gate_episodes),
        len(score3_episodes),
        score3_return_summary,
        signal_funnel,
    )

    report = {
        "strategy_version": ERH_V1_DIAGNOSTIC_VERSION,
        "diagnoses_strategy_version": ERH_V1_VERSION,
        "status": "diagnostic_complete",
        "uses_blindtest_for_parameter_selection": False,
        "changes_strategy_parameters": False,
        "runs_blindtest": False,
        "data_range": {
            "training_start": training_start.isoformat(),
            "blindtest_start": blindtest_start.isoformat(),
            "blindtest_end": blindtest_end.isoformat(),
        },
        "regime_sanity": {
            "training_4h_bars": int(len(regime)),
            "hard_gate_active_bar_count": int(hard_gate_active.sum()),
            "score3_active_bar_count": int(score3_active_4h.sum()),
            "score4_active_bar_count": int(score4_active_4h.sum()),
            "score_distribution": {
                str(int(score)): int(count)
                for score, count in regime["regime_score"].value_counts().sort_index().items()
            },
            "hard_gate_episode_count": len(hard_gate_episodes),
            "score3_episode_count": len(score3_episodes),
            "score4_episode_count": len(score4_episodes),
            "hard_gate_episodes": [asdict(episode) for episode in hard_gate_episodes],
            "score3_episodes": [asdict(episode) for episode in score3_episodes],
            "score4_episodes": [asdict(episode) for episode in score4_episodes],
        },
        "feature_nan_and_gate_audit": [asdict(audit) for audit in feature_audit],
        "signal_funnel_by_variant": signal_funnel,
        "unconditional_regime_return_test": {
            "score3": {
                "summary": score3_return_summary,
                "episodes": [asdict(episode) for episode in score3_returns],
            },
            "score4": {
                "summary": score4_return_summary,
                "episodes": [asdict(episode) for episode in score4_returns],
            },
        },
        "suspected_root_cause_category": root_cause,
        "evidence_for_suspected_root_cause": evidence,
        "recommended_next_step": next_step,
    }

    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "erh_v1_diagnostic_report.json"
    report["output_paths"] = {"report": str(report_path)}
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=_to_jsonable) + "\n",
        encoding="utf-8",
    )
    return report
