"""Research-only BEV-L v1 BTC/ETHBTC volatility-divergence existence scan.

BEV-L v1 asks a different profit-alpha question than BELL:

    If BTC volatility is compressed but ETHBTC volatility expands in a positive
    ETHBTC direction, does ETHUSDC show stable forward edge?

This module only scans the 730-day training window.  It does not build a
strategy, does not touch the router, and does not run a blindtest.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import REPORTS_DIR
from src.research.erh_v1 import (
    ErhConfig,
    _net_return,
    build_walkforward_windows,
    latest_train_blind_window,
    load_1m_candles,
    resample_closed_candles,
)

BEV_L_V1_VERSION = "bev_l_v1_volatility_divergence_scan_20260703"


@dataclass(frozen=True)
class BevConfig:
    """Configuration for the BEV-L v1 existence scan."""

    output_dir: Path = REPORTS_DIR / "research" / "bev_l_v1_divergence_scan"
    horizons_hours: tuple[int, ...] = (12, 24, 48)
    val_days: int = 120
    purge_days: int = 7
    fold_count: int = 6
    percentile_lookback_hours: int = 24 * 60
    min_percentile_history_hours: int = 24 * 30
    min_q5_validation_count: int = 24
    min_passing_folds: int = 5
    min_q5_minus_q1_net_return: float = 0.003
    trading_cost_config: ErhConfig = ErhConfig(position_size_usdc=100.0)


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


def rolling_prior_percentile(
    series: pd.Series,
    lookback: int,
    min_periods: int,
) -> pd.Series:
    """Return each value's percentile versus prior history only."""
    values = series.astype(float).to_numpy()
    percentiles: list[float] = []
    for index, value in enumerate(values):
        if np.isnan(value):
            percentiles.append(np.nan)
            continue
        start = max(0, index - lookback)
        history = values[start:index]
        history = history[~np.isnan(history)]
        if len(history) < min_periods:
            percentiles.append(np.nan)
            continue
        percentiles.append(float(np.mean(history <= value)))
    return pd.Series(percentiles, index=series.index)


def build_bev_feature_frame(
    eth_1m: pd.DataFrame,
    btc_1m: pd.DataFrame,
    ethbtc_1m: pd.DataFrame,
    config: BevConfig,
) -> pd.DataFrame:
    """Build lookahead-safe closed-1h BEV-L features."""
    eth_1h = resample_closed_candles(eth_1m, "1h")
    btc_1h = resample_closed_candles(btc_1m, "1h").reindex(eth_1h.index)
    ethbtc_1h = resample_closed_candles(ethbtc_1m, "1h").reindex(eth_1h.index)
    frame = eth_1h[["open", "high", "low", "close"]].copy()
    btc_logret = np.log(btc_1h["close"] / btc_1h["close"].shift(1))
    ethbtc_logret = np.log(ethbtc_1h["close"] / ethbtc_1h["close"].shift(1))
    frame["btc_rv_24h"] = np.sqrt(
        btc_logret.pow(2).rolling(24, min_periods=24).sum()
    )
    frame["ethbtc_rv_24h"] = np.sqrt(
        ethbtc_logret.pow(2).rolling(24, min_periods=24).sum()
    )
    frame["btc_rv_percentile_60d"] = rolling_prior_percentile(
        frame["btc_rv_24h"],
        config.percentile_lookback_hours,
        config.min_percentile_history_hours,
    )
    frame["ethbtc_rv_percentile_60d"] = rolling_prior_percentile(
        frame["ethbtc_rv_24h"],
        config.percentile_lookback_hours,
        config.min_percentile_history_hours,
    )
    frame["divergence_score"] = (
        frame["ethbtc_rv_percentile_60d"] - frame["btc_rv_percentile_60d"]
    )
    ethbtc_close = ethbtc_1h["close"]
    frame["ethbtc_ret_24h"] = ethbtc_close / ethbtc_close.shift(24) - 1.0
    return frame.dropna(subset=["open", "high", "low", "close"])


def _forward_net_return(
    execution: pd.DataFrame,
    signal_time: pd.Timestamp,
    horizon_hours: int,
    config: BevConfig,
) -> float | None:
    full_index = execution.index
    signal_pos = int(full_index.get_loc(signal_time))
    entry_pos = signal_pos + 1
    exit_pos = entry_pos + horizon_hours
    if exit_pos >= len(execution):
        return None
    entry_price = float(execution.iloc[entry_pos]["open"])
    exit_price = float(execution.iloc[exit_pos]["open"])
    net_return, _ = _net_return(entry_price, exit_price, config.trading_cost_config)
    return net_return


def _train_quintile_thresholds(train: pd.Series) -> list[float]:
    values = train.replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return []
    return [float(values.quantile(q)) for q in (0.2, 0.4, 0.6, 0.8)]


def _assign_quintile(value: float, thresholds: list[float]) -> int | None:
    if pd.isna(value) or len(thresholds) != 4:
        return None
    return int(np.searchsorted(thresholds, value, side="right"))


def scan_bev_fold(
    execution: pd.DataFrame,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    validation_start: pd.Timestamp,
    validation_end: pd.Timestamp,
    horizon_hours: int,
    config: BevConfig,
) -> dict[str, Any]:
    """Scan one fold/horizon for the BEV-L divergence structure."""
    train = execution.loc[(execution.index >= train_start) & (execution.index <= train_end)]
    thresholds = _train_quintile_thresholds(train["divergence_score"])
    validation = execution.loc[
        (execution.index >= validation_start) & (execution.index <= validation_end)
    ]
    rows: list[dict[str, Any]] = []
    for timestamp, row in validation.iterrows():
        if float(row.get("ethbtc_ret_24h", np.nan)) <= 0:
            continue
        forward = _forward_net_return(execution, timestamp, horizon_hours, config)
        if forward is None:
            continue
        quintile = _assign_quintile(float(row["divergence_score"]), thresholds)
        if quintile is None:
            continue
        rows.append(
            {
                "quintile": quintile,
                "forward_net_return": forward,
            }
        )
    if not rows:
        return {
            "thresholds": thresholds,
            "row_count": 0,
            "quintiles": [],
            "fold_passed": False,
            "rejection_reason": "no_positive_ethbtc_direction_rows",
        }
    frame = pd.DataFrame(rows)
    quintiles = []
    for quintile, group in frame.groupby("quintile", sort=True):
        returns = group["forward_net_return"]
        quintiles.append(
            {
                "quintile": int(quintile),
                "count": int(len(group)),
                "mean_net_return": float(returns.mean()),
                "median_net_return": float(returns.median()),
                "win_rate": float((returns > 0).mean()),
            }
        )
    by_quintile = {row["quintile"]: row for row in quintiles}
    q1 = by_quintile.get(0)
    q5 = by_quintile.get(4)
    best = max(quintiles, key=lambda row: row["mean_net_return"])
    q5_minus_q1 = (
        q5["mean_net_return"] - q1["mean_net_return"]
        if q1 is not None and q5 is not None
        else None
    )
    rejection_reasons: list[str] = []
    if q5 is None or q5["count"] < config.min_q5_validation_count:
        rejection_reasons.append("q5_count_below_minimum")
    if q5 is None or q5["mean_net_return"] <= 0:
        rejection_reasons.append("q5_mean_not_positive")
    if best["quintile"] != 4:
        rejection_reasons.append("q5_not_best_quintile")
    if q5_minus_q1 is None or q5_minus_q1 < config.min_q5_minus_q1_net_return:
        rejection_reasons.append("q5_minus_q1_below_minimum")
    return {
        "thresholds": thresholds,
        "row_count": int(len(frame)),
        "quintiles": quintiles,
        "best_quintile": best,
        "q5_minus_q1_net_return": q5_minus_q1,
        "fold_passed": not rejection_reasons,
        "rejection_reasons": rejection_reasons,
    }


def _load_training_execution(
    config: BevConfig,
) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    eth_1m = load_1m_candles("ETHUSDC")
    training_start, blindtest_start, blindtest_end = latest_train_blind_window(eth_1m)
    window_start = training_start - pd.Timedelta(days=90)
    window_end = blindtest_start - pd.Timedelta(minutes=1)
    execution = build_bev_feature_frame(
        eth_1m.loc[(eth_1m.index >= window_start) & (eth_1m.index <= window_end)],
        load_1m_candles("BTCUSDC").loc[
            lambda frame: (frame.index >= window_start) & (frame.index <= window_end)
        ],
        load_1m_candles("ETHBTC").loc[
            lambda frame: (frame.index >= window_start) & (frame.index <= window_end)
        ],
        config,
    )
    execution = execution.loc[
        (execution.index >= training_start) & (execution.index < blindtest_start)
    ].copy()
    return execution, training_start, blindtest_start, blindtest_end


def run_bev_l_v1_divergence_scan(config: BevConfig | None = None) -> dict[str, Any]:
    """Run the BEV-L v1 training-only volatility-divergence existence scan."""
    active_config = config or BevConfig()
    execution, training_start, blindtest_start, blindtest_end = _load_training_execution(
        active_config
    )
    windows = build_walkforward_windows(training_start, blindtest_start, active_config)
    horizon_reports: list[dict[str, Any]] = []
    for horizon in active_config.horizons_hours:
        folds = []
        for window in windows:
            folds.append(
                {
                    **window,
                    **scan_bev_fold(
                        execution,
                        training_start,
                        pd.Timestamp(window["train_end"]),
                        pd.Timestamp(window["validation_start"]),
                        pd.Timestamp(window["validation_end"]),
                        horizon,
                        active_config,
                    ),
                }
            )
        passing_folds = sum(bool(fold["fold_passed"]) for fold in folds)
        horizon_reports.append(
            {
                "horizon_hours": horizon,
                "passing_folds": passing_folds,
                "existence_criterion_met": (
                    passing_folds >= active_config.min_passing_folds
                ),
                "folds": folds,
            }
        )
    passing = [
        report for report in horizon_reports if report["existence_criterion_met"]
    ]
    status = (
        "bev_l_training_divergence_edge_found"
        if passing
        else "no_bev_l_training_divergence_edge"
    )
    report: dict[str, Any] = {
        "strategy_version": BEV_L_V1_VERSION,
        "status": status,
        "research_only": True,
        "training_only": True,
        "builds_strategy": False,
        "runs_blindtest": False,
        "runs_ui_backtest": False,
        "changes_router": False,
        "uses_blindtest_for_selection": False,
        "data_range": {
            "training_start": training_start.isoformat(),
            "blindtest_start_not_used": blindtest_start.isoformat(),
            "blindtest_end_not_used": blindtest_end.isoformat(),
        },
        "data_sources_used": [
            "ETHUSDC 1m resampled to closed 1h execution bars",
            "BTCUSDC 1m resampled to closed 1h volatility context",
            "ETHBTC 1m resampled to closed 1h relative volatility/direction",
        ],
        "lookahead_safety_notes": [
            "Feature rows are closed 1h bars.",
            "Rolling percentiles compare current RV only with prior history.",
            "Quintile thresholds are calibrated only on each fold train window.",
            "Forward returns enter at next 1h open after feature availability.",
            "Blindtest remains untouched.",
        ],
        "config": {
            key: str(value) if isinstance(value, Path) else _to_jsonable(value)
            for key, value in asdict(active_config).items()
        },
        "walkforward_fold_count": len(windows),
        "horizon_reports": horizon_reports,
        "passing_horizon_count": len(passing),
        "decision_summary": {
            "frozen_blindtest_allowed_now": False,
            "ui_full_backtest_allowed_now": False,
            "router_integration_allowed_now": False,
            "recommended_next_step": (
                "If a horizon passed, build a separate fixed signal variant "
                "research runner; no UI/full yet."
                if passing
                else (
                    "Do not build a BEV-L strategy. The volatility-divergence "
                    "existence criterion failed in training."
                )
            ),
        },
    }
    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "bev_l_v1_divergence_scan_report.json"
    report["output_paths"] = {"report": str(report_path)}
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=_to_jsonable) + "\n",
        encoding="utf-8",
    )
    return report
