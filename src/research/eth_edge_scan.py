"""Research-only ETHUSDC long-only edge existence scan.

This module deliberately does not build a strategy. It answers one narrower
question before another patch cycle starts:

    Does any already available ETH/BTC/orderflow/context feature show a stable
    positive forward-return structure after realistic spot roundtrip costs?

Only the 730-day training window is scanned. The 365-day blindtest remains
untouched because this is an exploratory existence check, not a candidate
selection ready for confirmation.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import REPORTS_DIR
from src.research.erh_v1 import (
    ErhConfig,
    _net_return,
    build_erh_feature_frames,
    latest_train_blind_window,
    load_1m_candles,
)

ETH_EDGE_SCAN_VERSION = "eth_edge_existence_scan_20260701"


@dataclass(frozen=True)
class EdgeScanConfig:
    """Configuration for the research-only edge scan."""

    horizons_hours: tuple[int, ...] = (1, 4, 12, 24, 72)
    fold_count: int = 6
    quintile_count: int = 5
    min_quintile_count: int = 100
    min_positive_folds: int = 3
    min_folds_present: int = 3
    output_dir: Path = REPORTS_DIR / "research" / "eth_edge_scan"
    trading_cost_config: ErhConfig = field(default_factory=ErhConfig)


@dataclass(frozen=True)
class FeatureSpec:
    """One feature tested by quintile against future returns."""

    name: str
    description: str
    high_value_interpretation: str


@dataclass(frozen=True)
class QuintileStats:
    """Forward-return statistics for one feature quintile."""

    quintile: int
    count: int
    mean_net_return: float
    median_net_return: float
    mean_pnl_usdc: float
    win_rate: float
    folds_present: int
    positive_folds: int
    fold_mean_net_returns: dict[str, float]


FEATURE_SPECS: tuple[FeatureSpec, ...] = (
    FeatureSpec(
        "eth_1h_ret_3",
        "ETHUSDC short impulse over the last 3 closed 1h candles",
        "ETH short-term strength / chase risk",
    ),
    FeatureSpec(
        "eth_4h_ret_6",
        "ETHUSDC 24h return from closed 4h candles",
        "ETH medium-term strength",
    ),
    FeatureSpec(
        "ethbtc_4h_ret_6",
        "ETHBTC 24h relative return from closed 4h candles",
        "ETH leadership versus BTC",
    ),
    FeatureSpec(
        "eth_4h_close_vs_ema20",
        "ETHUSDC 4h close distance to EMA20",
        "ETH trend extension above EMA20",
    ),
    FeatureSpec(
        "eth_4h_dist_to_20d_high",
        "ETHUSDC 4h distance to rolling 20-day high",
        "ETH near range high when closer to zero",
    ),
    FeatureSpec(
        "eth_of_ofi_4h_3sum",
        "ETHUSDC kline taker-buy orderflow imbalance over 3 closed 4h bars",
        "persistent taker-buy pressure",
    ),
    FeatureSpec(
        "eth_of_4h_buy_share_3avg",
        "ETHUSDC kline taker-buy quote-volume share over 3 closed 4h bars",
        "persistent buy-side quote-volume dominance",
    ),
    FeatureSpec(
        "eth_of_quote_vol_z_20",
        "ETHUSDC 4h quote-volume z-score versus 20 closed 4h bars",
        "unusual ETH activity / volume expansion",
    ),
    FeatureSpec(
        "btc_4h_close_vs_ema20",
        "BTCUSDC 4h close distance to EMA20",
        "BTC constructive risk context",
    ),
    FeatureSpec(
        "btc_4h_drawdown_from_20d_high",
        "BTCUSDC drawdown from rolling 20-day high",
        "BTC closer to highs / less crash stress",
    ),
    FeatureSpec(
        "btc_4h_rv_20",
        "BTCUSDC realized volatility over 20 closed 4h bars",
        "higher BTC volatility / risk turbulence",
    ),
    FeatureSpec(
        "usdc_dev",
        "USDCUSDT absolute peg deviation",
        "larger USDC peg stress",
    ),
    FeatureSpec(
        "basis_usdt_4h",
        "ETHUSDC versus ETHUSDT/USDCUSDT cross-quote basis",
        "larger quote/basis dislocation",
    ),
)


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, float) and math.isinf(value):
        return "inf"
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    return value


def _load_training_execution() -> tuple[
    pd.DataFrame,
    pd.Timestamp,
    pd.Timestamp,
    pd.Timestamp,
]:
    eth_1m = load_1m_candles("ETHUSDC")
    training_start, blindtest_start, blindtest_end = latest_train_blind_window(eth_1m)
    window_start = training_start - pd.Timedelta(days=25)
    window_end = blindtest_start - pd.Timedelta(minutes=1)
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
    execution, _ = build_erh_feature_frames(
        frames["ETHUSDC"],
        frames["ETHBTC"],
        frames["BTCUSDC"],
        frames["ETHUSDT"],
        frames["USDCUSDT"],
    )
    execution = execution.loc[
        (execution.index >= training_start) & (execution.index < blindtest_start)
    ].copy()
    return execution, training_start, blindtest_start, blindtest_end


def compute_forward_net_returns(
    execution: pd.DataFrame,
    horizon_hours: int,
    cost_config: ErhConfig,
) -> pd.Series:
    """Return next-open to horizon-open net returns for each feature row.

    A feature row at position ``i`` is only known after that row closed. The
    hypothetical long therefore enters at ``i + 1`` open and exits
    ``horizon_hours`` later at ``i + 1 + horizon_hours`` open.
    """
    if horizon_hours < 1:
        msg = "horizon_hours must be >= 1"
        raise ValueError(msg)
    returns: list[float] = []
    index: list[pd.Timestamp] = []
    max_signal_pos = len(execution) - horizon_hours - 2
    for signal_pos in range(max_signal_pos + 1):
        entry_pos = signal_pos + 1
        exit_pos = entry_pos + horizon_hours
        entry_price = float(execution.iloc[entry_pos]["open"])
        exit_price = float(execution.iloc[exit_pos]["open"])
        net_return, _ = _net_return(entry_price, exit_price, cost_config)
        returns.append(net_return)
        index.append(execution.index[signal_pos])
    return pd.Series(returns, index=pd.Index(index, name=execution.index.name))


def assign_time_folds(
    index: pd.Index,
    start: pd.Timestamp,
    end: pd.Timestamp,
    fold_count: int,
) -> pd.Series:
    """Assign chronological fold numbers to timestamps."""
    if fold_count < 1:
        msg = "fold_count must be >= 1"
        raise ValueError(msg)
    total_seconds = max((end - start).total_seconds(), 1.0)
    fold_values: list[int] = []
    for timestamp in pd.DatetimeIndex(index):
        raw_fold = int(((timestamp - start).total_seconds() / total_seconds) * fold_count)
        fold_values.append(min(max(raw_fold, 0), fold_count - 1))
    return pd.Series(fold_values, index=index, dtype="int64")


def _quintile_stats(
    subset: pd.DataFrame,
    quintile: int,
    config: EdgeScanConfig,
) -> QuintileStats:
    returns = subset["forward_net_return"]
    fold_means = returns.groupby(subset["fold"]).mean()
    fold_mean_dict = {
        str(int(fold)): float(value)
        for fold, value in fold_means.sort_index().items()
    }
    return QuintileStats(
        quintile=int(quintile),
        count=int(len(subset)),
        mean_net_return=float(returns.mean()),
        median_net_return=float(returns.median()),
        mean_pnl_usdc=float(returns.mean() * config.trading_cost_config.position_size_usdc),
        win_rate=float((returns > 0).mean()),
        folds_present=int(fold_means.count()),
        positive_folds=int((fold_means > 0).sum()),
        fold_mean_net_returns=fold_mean_dict,
    )


def scan_feature_horizon(
    execution: pd.DataFrame,
    feature: FeatureSpec,
    horizon_hours: int,
    training_start: pd.Timestamp,
    blindtest_start: pd.Timestamp,
    config: EdgeScanConfig,
) -> dict[str, Any]:
    """Scan one feature/horizon pair by quintile."""
    forward_returns = compute_forward_net_returns(
        execution,
        horizon_hours,
        config.trading_cost_config,
    )
    feature_values = execution[feature.name].reindex(forward_returns.index)
    scan_frame = pd.DataFrame(
        {
            "feature_value": feature_values,
            "forward_net_return": forward_returns,
        }
    ).dropna()
    if scan_frame.empty:
        return {
            "feature": asdict(feature),
            "horizon_hours": horizon_hours,
            "status": "no_valid_rows",
            "row_count": 0,
            "quintiles": [],
            "best_quintile": None,
            "edge_candidate": False,
        }

    scan_frame["fold"] = assign_time_folds(
        scan_frame.index,
        training_start,
        blindtest_start,
        config.fold_count,
    )
    try:
        scan_frame["quintile"] = pd.qcut(
            scan_frame["feature_value"],
            q=config.quintile_count,
            labels=False,
            duplicates="drop",
        )
    except ValueError:
        return {
            "feature": asdict(feature),
            "horizon_hours": horizon_hours,
            "status": "qcut_failed",
            "row_count": int(len(scan_frame)),
            "quintiles": [],
            "best_quintile": None,
            "edge_candidate": False,
        }
    scan_frame = scan_frame.dropna(subset=["quintile"])
    if scan_frame.empty:
        return {
            "feature": asdict(feature),
            "horizon_hours": horizon_hours,
            "status": "no_quintiles_after_qcut",
            "row_count": 0,
            "quintiles": [],
            "best_quintile": None,
            "edge_candidate": False,
        }

    scan_frame["quintile"] = scan_frame["quintile"].astype(int)
    quintiles = [
        _quintile_stats(group, int(quintile), config)
        for quintile, group in scan_frame.groupby("quintile", sort=True)
    ]
    best = max(quintiles, key=lambda item: item.mean_net_return)
    worst = min(quintiles, key=lambda item: item.mean_net_return)
    quintile_means = [item.mean_net_return for item in quintiles]
    monotonic_increasing = all(
        later >= earlier
        for earlier, later in zip(quintile_means, quintile_means[1:], strict=False)
    )
    monotonic_decreasing = all(
        later <= earlier
        for earlier, later in zip(quintile_means, quintile_means[1:], strict=False)
    )
    highest_quintile = max(item.quintile for item in quintiles)
    edge_side = "middle"
    if best.quintile <= 1:
        edge_side = "low_quintile_reversion_or_stress"
    elif best.quintile >= highest_quintile - 1:
        edge_side = "high_quintile_momentum_or_strength"

    edge_candidate = (
        best.mean_net_return > 0
        and best.count >= config.min_quintile_count
        and best.folds_present >= config.min_folds_present
        and best.positive_folds >= config.min_positive_folds
    )
    return {
        "feature": asdict(feature),
        "horizon_hours": horizon_hours,
        "status": "scanned",
        "row_count": int(len(scan_frame)),
        "quintiles": [asdict(item) for item in quintiles],
        "best_quintile": asdict(best),
        "worst_quintile": asdict(worst),
        "top_bottom_mean_spread": float(quintile_means[-1] - quintile_means[0])
        if len(quintile_means) >= 2
        else None,
        "best_minus_worst_mean_spread": float(best.mean_net_return - worst.mean_net_return),
        "monotonic_increasing_by_quintile": monotonic_increasing,
        "monotonic_decreasing_by_quintile": monotonic_decreasing,
        "edge_side": edge_side,
        "edge_candidate": edge_candidate,
    }


def run_eth_edge_existence_scan(config: EdgeScanConfig | None = None) -> dict[str, Any]:
    """Run the training-only ETH edge existence scan."""
    active_config = config or EdgeScanConfig()
    execution, training_start, blindtest_start, blindtest_end = _load_training_execution()

    scans: list[dict[str, Any]] = []
    for feature in FEATURE_SPECS:
        if feature.name not in execution.columns:
            scans.append(
                {
                    "feature": asdict(feature),
                    "status": "missing_feature_column",
                    "horizon_hours": None,
                    "edge_candidate": False,
                }
            )
            continue
        for horizon in active_config.horizons_hours:
            scans.append(
                scan_feature_horizon(
                    execution=execution,
                    feature=feature,
                    horizon_hours=horizon,
                    training_start=training_start,
                    blindtest_start=blindtest_start,
                    config=active_config,
                )
            )

    edge_candidates = [
        scan
        for scan in scans
        if scan.get("status") == "scanned" and scan.get("edge_candidate") is True
    ]
    edge_candidates = sorted(
        edge_candidates,
        key=lambda item: (
            item["best_quintile"]["mean_net_return"],
            item["best_quintile"]["positive_folds"],
            item["best_quintile"]["count"],
        ),
        reverse=True,
    )
    reversion_candidates = [
        item
        for item in edge_candidates
        if item["edge_side"] == "low_quintile_reversion_or_stress"
    ]
    momentum_candidates = [
        item
        for item in edge_candidates
        if item["edge_side"] == "high_quintile_momentum_or_strength"
    ]

    status = "edge_candidate_found" if edge_candidates else "no_training_edge_candidate_found"
    report: dict[str, Any] = {
        "strategy_version": ETH_EDGE_SCAN_VERSION,
        "status": status,
        "research_only": True,
        "builds_strategy": False,
        "runs_blindtest": False,
        "uses_blindtest_for_parameter_selection": False,
        "data_range": {
            "training_start": training_start.isoformat(),
            "blindtest_start": blindtest_start.isoformat(),
            "blindtest_end_not_used": blindtest_end.isoformat(),
        },
        "data_sources_used": [
            "ETHUSDC 1m OHLCV and complete kline fields, resampled to closed 1h/4h",
            "BTCUSDC 1m context, resampled to closed 4h",
            "ETHBTC 1m relative-strength context, resampled to closed 4h",
            "ETHUSDT 1m plus USDCUSDT 1m for spot cross-quote/basis sanity",
        ],
        "execution_assumption": (
            "Feature row i is known only after close; hypothetical forward return "
            "enters at row i+1 open and exits after the requested horizon."
        ),
        "cost_model": {
            "position_size_usdc": active_config.trading_cost_config.position_size_usdc,
            "fee_rate_per_side": active_config.trading_cost_config.fee_rate_per_side,
            "slippage_rate_per_side": active_config.trading_cost_config.slippage_rate_per_side,
            "roundtrip_cost_floor_ret": (
                active_config.trading_cost_config.roundtrip_cost_floor_ret
            ),
        },
        "scan_config": {
            "horizons_hours": list(active_config.horizons_hours),
            "fold_count": active_config.fold_count,
            "quintile_count": active_config.quintile_count,
            "min_quintile_count": active_config.min_quintile_count,
            "min_positive_folds": active_config.min_positive_folds,
            "min_folds_present": active_config.min_folds_present,
        },
        "feature_count": len(FEATURE_SPECS),
        "scan_count": len(scans),
        "edge_candidate_count": len(edge_candidates),
        "edge_candidates": edge_candidates[:15],
        "reversion_candidate_count": len(reversion_candidates),
        "reversion_candidates": reversion_candidates[:10],
        "momentum_candidate_count": len(momentum_candidates),
        "momentum_candidates": momentum_candidates[:10],
        "all_scans": scans,
        "next_required_step": (
            "If an edge_candidate exists, do not UI-backtest yet. Turn the best "
            "training-only feature/horizon result into one small named research "
            "hypothesis with walkforward and then one frozen blindtest. If no "
            "candidate exists, stop strategy patching and reassess whether the "
            "current long-only spot/no-leverage/cost model can reach 3 USDC/day."
        ),
    }

    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "eth_edge_existence_scan_report.json"
    report["output_paths"] = {"report": str(report_path)}
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=_to_jsonable) + "\n",
        encoding="utf-8",
    )
    return report
