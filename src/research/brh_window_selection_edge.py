"""Training-only BRH window-selection edge check.

This is a pre-v2 diagnostic. It asks one narrow question:

    Did BRH-v1 select ETHUSDC exposure windows that were better than simple
    BTC-risk-on windows inside the same training walkforward folds?

The check uses only BRH-v1 training/validation artifacts and market data before
the blindtest. It does not run a new blindtest, does not select a live/router
candidate and does not change BRH-v1.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import REPORTS_DIR
from src.research.brh_v1 import (
    BRH_V1_VERSION,
    BrhConfig,
    BrhThresholds,
    _load_full_execution,
    _to_jsonable,
)
from src.research.brh_v1_diagnostics import _read_json, _read_validation_trades
from src.research.erh_v1 import _net_return

BRH_WINDOW_SELECTION_EDGE_VERSION = "brh_window_selection_edge_check_20260702"


@dataclass(frozen=True)
class BrhWindowSelectionEdgeConfig:
    """Configuration for the training-only BRH window-selection check."""

    source_report_path: Path = REPORTS_DIR / "research" / "brh_v1" / "brh_v1_research_report.json"
    source_validation_trades_path: Path = (
        REPORTS_DIR / "research" / "brh_v1" / "brh_v1_validation_trades.csv"
    )
    output_dir: Path = REPORTS_DIR / "research" / "brh_window_selection_edge"
    hold_hours: int = 72
    min_positive_edge_folds: int = 5
    min_aggregate_edge_after_cost: float = 0.0
    min_worst_fold_edge_after_cost: float = -0.005


@dataclass(frozen=True)
class WindowReturn:
    """One hypothetical 72h risk-on window return."""

    signal_time: str
    entry_time: str
    exit_time: str
    net_return: float
    net_pnl_usdc: float


def _thresholds_from_fold(fold: dict[str, Any]) -> BrhThresholds:
    return BrhThresholds(**fold["thresholds"])


def _fold_windows(report: dict[str, Any]) -> list[dict[str, Any]]:
    variants = report.get("variants", [])
    if not variants:
        return []
    return list(variants[0].get("folds", []))


def _required_risk_on_columns_present(row: pd.Series) -> bool:
    required_columns = [
        "btc_4h_drawdown_from_20d_high",
        "usdc_dev",
        "basis_usdt_4h",
    ]
    return not any(pd.isna(row[column]) for column in required_columns)


def risk_on_signal_passes(
    row: pd.Series,
    thresholds: BrhThresholds,
    config: BrhConfig,
) -> bool:
    """Return whether a row is a simple BTC-risk-on baseline signal."""
    if not _required_risk_on_columns_present(row):
        return False
    if float(row["btc_4h_drawdown_from_20d_high"]) < thresholds.btc_drawdown_q80:
        return False
    if float(row["usdc_dev"]) > config.max_usdc_dev:
        return False
    return abs(float(row["basis_usdt_4h"])) <= config.max_basis_abs


def _window_return_for_signal(
    execution: pd.DataFrame,
    signal_time: pd.Timestamp,
    end: pd.Timestamp,
    hold_hours: int,
    config: BrhConfig,
) -> WindowReturn | None:
    full_index = execution.index
    try:
        signal_pos = int(full_index.get_loc(signal_time))
    except KeyError:
        return None
    entry_pos = signal_pos + 1
    exit_pos = entry_pos + hold_hours
    if exit_pos >= len(execution):
        return None
    entry_time = full_index[entry_pos]
    exit_time = full_index[exit_pos]
    if exit_time > end:
        return None
    entry_price = float(execution.iloc[entry_pos]["open"])
    exit_price = float(execution.iloc[exit_pos]["open"])
    net_return, _ = _net_return(
        entry_price,
        exit_price,
        config.trading_cost_config,
    )
    return WindowReturn(
        signal_time=signal_time.isoformat(),
        entry_time=entry_time.isoformat(),
        exit_time=exit_time.isoformat(),
        net_return=net_return,
        net_pnl_usdc=net_return * config.position_size_usdc,
    )


def baseline_risk_on_windows(
    execution: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    thresholds: BrhThresholds,
    config: BrhConfig,
    hold_hours: int,
    enforce_non_overlap: bool = False,
) -> list[WindowReturn]:
    """Build simple BTC-risk-on baseline windows inside one validation fold."""
    signal_frame = execution.loc[(execution.index >= start) & (execution.index <= end)]
    signal_frame = signal_frame[
        signal_frame["brh_signal_update_bar"].fillna(False).astype(bool)
    ]
    windows: list[WindowReturn] = []
    next_entry_allowed_at = start
    for signal_time, row in signal_frame.iterrows():
        if enforce_non_overlap and signal_time < next_entry_allowed_at:
            continue
        if not risk_on_signal_passes(row, thresholds, config):
            continue
        window = _window_return_for_signal(
            execution,
            signal_time,
            end,
            hold_hours,
            config,
        )
        if window is None:
            continue
        windows.append(window)
        if enforce_non_overlap:
            next_entry_allowed_at = pd.Timestamp(window.exit_time)
    return windows


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.mean(values))


def _window_summary(windows: list[WindowReturn]) -> dict[str, Any]:
    returns = [window.net_return for window in windows]
    pnls = [window.net_pnl_usdc for window in windows]
    return {
        "window_count": len(windows),
        "mean_net_return": _mean_or_none(returns),
        "mean_net_pnl_usdc": _mean_or_none(pnls),
        "median_net_pnl_usdc": float(np.median(pnls)) if pnls else None,
        "win_rate": float(np.mean([pnl > 0 for pnl in pnls])) if pnls else None,
    }


def _selected_trade_summary(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {
            "trade_count": 0,
            "mean_net_return": None,
            "mean_net_pnl_usdc": None,
            "median_net_pnl_usdc": None,
            "win_rate": None,
        }
    return {
        "trade_count": int(len(trades)),
        "mean_net_return": float(trades["net_return"].mean()),
        "mean_net_pnl_usdc": float(trades["net_pnl_usdc"].mean()),
        "median_net_pnl_usdc": float(trades["net_pnl_usdc"].median()),
        "win_rate": float((trades["net_pnl_usdc"] > 0).mean()),
    }


def _fold_selected_trades(
    validation_trades: pd.DataFrame,
    variant_id: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    trades = validation_trades[validation_trades["variant_id"] == variant_id]
    return trades[(trades["signal_time"] >= start) & (trades["signal_time"] <= end)]


def variant_window_selection_edge(
    execution: pd.DataFrame,
    validation_trades: pd.DataFrame,
    variant_report: dict[str, Any],
    config: BrhWindowSelectionEdgeConfig,
    brh_config: BrhConfig,
) -> dict[str, Any]:
    """Calculate selected-vs-risk-on edge for one BRH-v1 variant."""
    variant_id = variant_report["variant"]["variant_id"]
    fold_reports: list[dict[str, Any]] = []
    selected_returns: list[float] = []
    baseline_returns: list[float] = []
    non_overlap_returns: list[float] = []
    fold_edges: list[float] = []

    for fold in variant_report.get("folds", []):
        val_start = pd.Timestamp(fold["validation_start"])
        val_end = pd.Timestamp(fold["validation_end"])
        thresholds = _thresholds_from_fold(fold)
        selected_trades = _fold_selected_trades(
            validation_trades,
            variant_id,
            val_start,
            val_end,
        )
        baseline_windows = baseline_risk_on_windows(
            execution,
            val_start,
            val_end,
            thresholds,
            brh_config,
            config.hold_hours,
            enforce_non_overlap=False,
        )
        non_overlap_windows = baseline_risk_on_windows(
            execution,
            val_start,
            val_end,
            thresholds,
            brh_config,
            config.hold_hours,
            enforce_non_overlap=True,
        )
        selected_summary = _selected_trade_summary(selected_trades)
        baseline_summary = _window_summary(baseline_windows)
        non_overlap_summary = _window_summary(non_overlap_windows)
        selected_mean = selected_summary["mean_net_return"]
        baseline_mean = baseline_summary["mean_net_return"]
        edge = (
            float(selected_mean - baseline_mean)
            if selected_mean is not None and baseline_mean is not None
            else None
        )
        if edge is not None:
            fold_edges.append(edge)
        selected_returns.extend(float(value) for value in selected_trades["net_return"])
        baseline_returns.extend(window.net_return for window in baseline_windows)
        non_overlap_returns.extend(window.net_return for window in non_overlap_windows)
        fold_reports.append(
            {
                "fold_index": fold["fold_index"],
                "validation_start": fold["validation_start"],
                "validation_end": fold["validation_end"],
                "selected_windows": selected_summary,
                "risk_on_all_windows_baseline": baseline_summary,
                "risk_on_non_overlap_baseline": non_overlap_summary,
                "selection_edge_after_cost_return": edge,
                "selection_edge_after_cost_usdc": edge * brh_config.position_size_usdc
                if edge is not None
                else None,
            }
        )

    selected_mean_all = _mean_or_none(selected_returns)
    baseline_mean_all = _mean_or_none(baseline_returns)
    non_overlap_mean_all = _mean_or_none(non_overlap_returns)
    aggregate_edge = (
        float(selected_mean_all - baseline_mean_all)
        if selected_mean_all is not None and baseline_mean_all is not None
        else None
    )
    aggregate_non_overlap_edge = (
        float(selected_mean_all - non_overlap_mean_all)
        if selected_mean_all is not None and non_overlap_mean_all is not None
        else None
    )
    positive_edge_folds = sum(edge > 0 for edge in fold_edges)
    worst_fold_edge = min(fold_edges) if fold_edges else None
    pass_check = (
        aggregate_edge is not None
        and aggregate_edge > config.min_aggregate_edge_after_cost
        and positive_edge_folds >= config.min_positive_edge_folds
        and worst_fold_edge is not None
        and worst_fold_edge > config.min_worst_fold_edge_after_cost
    )
    return {
        "variant_id": variant_id,
        "eligible_for_blindtest_in_brh_v1": bool(
            variant_report.get("eligible_for_blindtest")
        ),
        "folds": fold_reports,
        "aggregate": {
            "selected_window_mean_net_return": selected_mean_all,
            "selected_window_mean_pnl_usdc": selected_mean_all * brh_config.position_size_usdc
            if selected_mean_all is not None
            else None,
            "baseline_all_risk_on_mean_net_return": baseline_mean_all,
            "baseline_all_risk_on_mean_pnl_usdc": baseline_mean_all
            * brh_config.position_size_usdc
            if baseline_mean_all is not None
            else None,
            "baseline_non_overlap_risk_on_mean_net_return": non_overlap_mean_all,
            "baseline_non_overlap_risk_on_mean_pnl_usdc": non_overlap_mean_all
            * brh_config.position_size_usdc
            if non_overlap_mean_all is not None
            else None,
            "window_selection_edge_after_cost_return": aggregate_edge,
            "window_selection_edge_after_cost_usdc": aggregate_edge
            * brh_config.position_size_usdc
            if aggregate_edge is not None
            else None,
            "non_overlap_selection_edge_after_cost_return": aggregate_non_overlap_edge,
            "non_overlap_selection_edge_after_cost_usdc": aggregate_non_overlap_edge
            * brh_config.position_size_usdc
            if aggregate_non_overlap_edge is not None
            else None,
            "folds_with_positive_selection_edge": positive_edge_folds,
            "worst_fold_selection_edge_after_cost_return": worst_fold_edge,
            "worst_fold_selection_edge_after_cost_usdc": worst_fold_edge
            * brh_config.position_size_usdc
            if worst_fold_edge is not None
            else None,
            "passes_window_selection_edge_check": pass_check,
        },
    }


def run_brh_window_selection_edge_check(
    config: BrhWindowSelectionEdgeConfig | None = None,
) -> dict[str, Any]:
    """Run the BRH training-only window-selection edge pre-check."""
    active_config = config or BrhWindowSelectionEdgeConfig()
    report = _read_json(active_config.source_report_path)
    validation_trades = _read_validation_trades(active_config.source_validation_trades_path)
    execution, training_start, blindtest_start, blindtest_end = _load_full_execution()
    execution = execution.loc[
        (execution.index >= training_start) & (execution.index < blindtest_start)
    ]
    brh_config = BrhConfig()

    variant_reports = [
        variant_window_selection_edge(
            execution,
            validation_trades,
            variant_report,
            active_config,
            brh_config,
        )
        for variant_report in report.get("variants", [])
    ]
    eligible_variant_reports = [
        item for item in variant_reports if item["eligible_for_blindtest_in_brh_v1"]
    ]
    passing_variants = [
        item
        for item in eligible_variant_reports
        if item["aggregate"]["passes_window_selection_edge_check"]
    ]
    selected_v1_id = (report.get("selected_variant") or {}).get("variant_id")
    selected_v1_report = next(
        (item for item in variant_reports if item["variant_id"] == selected_v1_id),
        None,
    )
    best_variant = None
    if passing_variants:
        best_variant = max(
            passing_variants,
            key=lambda item: (
                item["aggregate"]["window_selection_edge_after_cost_return"],
                item["aggregate"]["folds_with_positive_selection_edge"],
            ),
        )

    check_passed = bool(passing_variants)
    report_out: dict[str, Any] = {
        "strategy_version": BRH_WINDOW_SELECTION_EDGE_VERSION,
        "diagnoses_strategy_version": BRH_V1_VERSION,
        "status": "window_selection_edge_found" if check_passed else "no_window_selection_edge",
        "research_only": True,
        "training_only": True,
        "runs_new_blindtest": False,
        "uses_blindtest_for_selection": False,
        "evaluates_alternative_blindtest_variants": False,
        "data_range": {
            "training_start": training_start.isoformat(),
            "blindtest_start_not_used": blindtest_start.isoformat(),
            "blindtest_end_not_used": blindtest_end.isoformat(),
        },
        "decision_thresholds": {
            "min_aggregate_edge_after_cost": active_config.min_aggregate_edge_after_cost,
            "min_positive_edge_folds": active_config.min_positive_edge_folds,
            "min_worst_fold_edge_after_cost": active_config.min_worst_fold_edge_after_cost,
            "decision_baseline": "all BTC-risk-on windows in the same validation folds",
        },
        "selected_v1_variant_id": selected_v1_id,
        "selected_v1_window_selection_edge": selected_v1_report["aggregate"]
        if selected_v1_report is not None
        else None,
        "variant_count": len(variant_reports),
        "eligible_variant_count": len(eligible_variant_reports),
        "passing_variant_count": len(passing_variants),
        "passing_variants": [
            {
                "variant_id": item["variant_id"],
                "aggregate": item["aggregate"],
            }
            for item in passing_variants
        ],
        "best_training_only_variant_by_window_selection_edge": {
            "variant_id": best_variant["variant_id"],
            "aggregate": best_variant["aggregate"],
        }
        if best_variant is not None
        else None,
        "variants": variant_reports,
        "decision_summary": {
            "brh_v2_conditionally_allowed": check_passed,
            "current_brh_v1_remains_archived": True,
            "recommended_next_step": (
                "A BRH/ERV-v2 selection-rule research pass is conditionally allowed, "
                "but still no UI/router integration and no blindtest until a separate "
                "training-only v2 runner passes robust concentration gates."
                if check_passed
                else (
                    "Close the BRH/ERV line. The variants did not select training "
                    "windows better than the simple BTC-risk-on baseline."
                )
            ),
        },
    }

    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "brh_window_selection_edge_report.json"
    report_out["output_paths"] = {"report": str(report_path)}
    report_path.write_text(
        json.dumps(report_out, indent=2, sort_keys=True, default=_to_jsonable) + "\n",
        encoding="utf-8",
    )
    return report_out
