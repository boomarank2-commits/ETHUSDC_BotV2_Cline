"""Strict training-only BRH/ERV selection robustness gatekeeper.

This is not BRH-v2 as a strategy. It is the stricter gatekeeper requested after
the BRH window-selection edge check.

The question is deliberately narrow:

    Does any BRH/ERV-v1 variant still deserve one future frozen research
    blindtest after adding missing baselines, concentration controls and a
    no-repeat rule for the already consumed v1 blindtest candidate?

The module uses only BRH-v1 training/walkforward artifacts and cuts market data
before the blindtest boundary. It does not run a blindtest, does not alter the
router and does not integrate anything into the UI.
"""

from __future__ import annotations

import hashlib
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
    _load_full_execution,
    _to_jsonable,
)
from src.research.brh_v1_diagnostics import (
    _full_period_buy_hold,
    _read_json,
    _read_validation_trades,
    concentration_metrics,
)
from src.research.brh_window_selection_edge import (
    BRH_WINDOW_SELECTION_EDGE_VERSION,
    WindowReturn,
    _fold_selected_trades,
    _mean_or_none,
    _thresholds_from_fold,
    _window_return_for_signal,
    baseline_risk_on_windows,
)

BRH_SELECTION_EDGE_ROBUSTNESS_VERSION = (
    "brh_selection_edge_robustness_v2check_20260702"
)
ALREADY_BLINDTESTED_VARIANT_IDS = frozenset({"erv_risk_on_orderflow_cooldown_72h"})
RISK_ON_BASELINE_VARIANT_ID = "brh_btc_risk_on_72h"


@dataclass(frozen=True)
class BrhSelectionRobustnessConfig:
    """Configuration for the strict BRH/ERV training-only gatekeeper."""

    source_report_path: Path = (
        REPORTS_DIR / "research" / "brh_v1" / "brh_v1_research_report.json"
    )
    source_validation_trades_path: Path = (
        REPORTS_DIR / "research" / "brh_v1" / "brh_v1_validation_trades.csv"
    )
    output_dir: Path = REPORTS_DIR / "research" / "brh_selection_edge_robustness_v2check"
    hold_hours: int = 72
    random_seed: int = 20260702
    random_baseline_sample_multiplier: int = 10
    min_random_baseline_windows: int = 20
    top_trim_count: int = 2
    min_total_validation_trades: int = 48
    min_average_trades_per_fold: float = 4.0
    min_positive_folds: int = 6
    min_positive_edge_folds: int = 5
    min_profit_factor: float = 1.25
    max_profit_factor_for_selection: float = 3.0
    min_cost_robust_profit_factor: float = 1.15
    min_median_trade_pnl_usdc: float = 0.0
    min_leave_one_out_profit_factor: float = 1.40
    min_leave_two_out_profit_factor: float = 1.30
    max_top1_pnl_share: float = 0.30
    max_top2_pnl_share: float = 0.45
    min_worst_fold_pnl_usdc: float = 0.0
    min_trimmed_edge_vs_random_usdc: float = 0.0
    min_trimmed_edge_vs_risk_on_usdc: float = 0.0
    require_strategy_beats_buy_hold_per_day: bool = True


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and value == "inf":
        return float("inf")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pnls_from_trades(trades: pd.DataFrame) -> list[float]:
    if trades.empty:
        return []
    return [float(value) for value in trades["net_pnl_usdc"].dropna()]


def _net_returns_from_trades(trades: pd.DataFrame) -> list[float]:
    if trades.empty:
        return []
    return [float(value) for value in trades["net_return"].dropna()]


def _window_pnls(windows: list[WindowReturn]) -> list[float]:
    return [window.net_pnl_usdc for window in windows]


def _window_returns(windows: list[WindowReturn]) -> list[float]:
    return [window.net_return for window in windows]


def trim_top_positive_values(values: list[float], count: int) -> list[float]:
    """Return values after removing the largest positive observations."""
    if count <= 0:
        return list(values)
    positive_indices = [
        index for index, value in sorted(enumerate(values), key=lambda item: item[1], reverse=True)
        if value > 0
    ][:count]
    if not positive_indices:
        return list(values)
    remove = set(positive_indices)
    return [value for index, value in enumerate(values) if index not in remove]


def _trimmed_mean_or_none(values: list[float], trim_count: int) -> float | None:
    if len(values) <= trim_count:
        return None
    trimmed = trim_top_positive_values(values, trim_count)
    if not trimmed:
        return None
    return float(np.mean(trimmed))


def _positive_fold_count(edges: list[float | None], allow_zero: bool = False) -> int:
    if allow_zero:
        return sum(edge is not None and edge >= 0 for edge in edges)
    return sum(edge is not None and edge > 0 for edge in edges)


def _deterministic_sample(
    windows: list[WindowReturn],
    sample_size: int,
    seed: int,
    key: str,
) -> list[WindowReturn]:
    if sample_size <= 0 or sample_size >= len(windows):
        return list(windows)
    digest = hashlib.sha256(f"{seed}:{key}".encode("utf-8")).digest()
    derived_seed = int.from_bytes(digest[:8], "big") % (2**32)
    rng = np.random.default_rng(derived_seed)
    indices = sorted(rng.choice(len(windows), size=sample_size, replace=False).tolist())
    return [windows[index] for index in indices]


def unconditional_eth_windows(
    execution: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    config: BrhSelectionRobustnessConfig,
    brh_config: BrhConfig,
    enforce_non_overlap: bool = True,
) -> list[WindowReturn]:
    """Build unconditional ETH 72h windows from closed BRH availability rows."""
    signal_frame = execution.loc[(execution.index >= start) & (execution.index <= end)]
    signal_frame = signal_frame[
        signal_frame["brh_signal_update_bar"].fillna(False).astype(bool)
    ]
    windows: list[WindowReturn] = []
    next_entry_allowed_at = start
    for signal_time, _ in signal_frame.iterrows():
        if enforce_non_overlap and signal_time < next_entry_allowed_at:
            continue
        window = _window_return_for_signal(
            execution,
            signal_time,
            end,
            config.hold_hours,
            brh_config,
        )
        if window is None:
            continue
        windows.append(window)
        if enforce_non_overlap:
            next_entry_allowed_at = pd.Timestamp(window.exit_time)
    return windows


def _summary_from_values(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "sum": 0.0,
            "win_rate": None,
        }
    return {
        "count": len(values),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "sum": float(np.sum(values)),
        "win_rate": float(np.mean([value > 0 for value in values])),
    }


def _fold_report(
    execution: pd.DataFrame,
    validation_trades: pd.DataFrame,
    variant_id: str,
    fold: dict[str, Any],
    config: BrhSelectionRobustnessConfig,
    brh_config: BrhConfig,
) -> dict[str, Any]:
    val_start = pd.Timestamp(fold["validation_start"])
    val_end = pd.Timestamp(fold["validation_end"])
    selected_trades = _fold_selected_trades(
        validation_trades,
        variant_id,
        val_start,
        val_end,
    )
    thresholds = _thresholds_from_fold(fold)
    risk_on_windows = baseline_risk_on_windows(
        execution,
        val_start,
        val_end,
        thresholds,
        brh_config,
        config.hold_hours,
        enforce_non_overlap=True,
    )
    all_unconditional_windows = unconditional_eth_windows(
        execution,
        val_start,
        val_end,
        config,
        brh_config,
        enforce_non_overlap=True,
    )
    requested_random_count = max(
        len(selected_trades) * config.random_baseline_sample_multiplier,
        config.min_random_baseline_windows,
    )
    random_windows = _deterministic_sample(
        all_unconditional_windows,
        requested_random_count,
        config.random_seed,
        f"{variant_id}:{fold['fold_index']}",
    )
    selected_pnls = _pnls_from_trades(selected_trades)
    selected_returns = _net_returns_from_trades(selected_trades)
    risk_on_pnls = _window_pnls(risk_on_windows)
    random_pnls = _window_pnls(random_windows)
    selected_mean_pnl = _mean_or_none(selected_pnls)
    risk_on_mean_pnl = _mean_or_none(risk_on_pnls)
    random_mean_pnl = _mean_or_none(random_pnls)
    edge_vs_risk_on = (
        float(selected_mean_pnl - risk_on_mean_pnl)
        if selected_mean_pnl is not None and risk_on_mean_pnl is not None
        else None
    )
    edge_vs_random = (
        float(selected_mean_pnl - random_mean_pnl)
        if selected_mean_pnl is not None and random_mean_pnl is not None
        else None
    )
    return {
        "fold_index": fold["fold_index"],
        "validation_start": fold["validation_start"],
        "validation_end": fold["validation_end"],
        "selected": {
            "pnl_usdc": _summary_from_values(selected_pnls),
            "net_return": _summary_from_values(selected_returns),
        },
        "risk_on_non_overlap_baseline": {
            "pnl_usdc": _summary_from_values(risk_on_pnls),
            "net_return": _summary_from_values(_window_returns(risk_on_windows)),
        },
        "random_unconditional_eth_baseline": {
            "sample_seed": config.random_seed,
            "available_window_count": len(all_unconditional_windows),
            "sampled_window_count": len(random_windows),
            "pnl_usdc": _summary_from_values(random_pnls),
            "net_return": _summary_from_values(_window_returns(random_windows)),
        },
        "edge_after_cost_usdc": {
            "selected_minus_risk_on_non_overlap": edge_vs_risk_on,
            "selected_minus_random_unconditional": edge_vs_random,
        },
    }


def _selection_score(
    aggregate: dict[str, Any],
    config: BrhSelectionRobustnessConfig,
) -> float | None:
    if not aggregate["passes_robust_gatekeeper"]:
        return None
    leave_two = _safe_float(aggregate["concentration"]["leave_two_out_profit_factor"])
    trimmed_random = _safe_float(
        aggregate["trimmed_edge_after_cost_usdc"]["selected_minus_random_unconditional"]
    )
    total_pnl = _safe_float(aggregate["validation_summary"]["pnl_usdc"]) or 0.0
    top2 = _safe_float((aggregate["concentration"]["top_trade_pnl_share"] or {}).get("2"))
    if leave_two is None or trimmed_random is None or top2 is None:
        return None
    top2_penalty = max(0.0, top2 - config.max_top2_pnl_share) * 10.0
    return float(leave_two + trimmed_random / 100.0 + total_pnl / 10000.0 - top2_penalty)


def _variant_gatekeeper_reasons(
    variant_id: str,
    variant_report: dict[str, Any],
    aggregate: dict[str, Any],
    config: BrhSelectionRobustnessConfig,
) -> list[str]:
    reasons: list[str] = []
    summary = aggregate["validation_summary"]
    concentration = aggregate["concentration"]
    top_shares = concentration.get("top_trade_pnl_share") or {}
    pf = _safe_float(summary.get("profit_factor"))
    cost_pf = _safe_float(variant_report.get("slippage_robustness_2bp_profit_factor"))
    leave_one = _safe_float(concentration.get("leave_one_out_profit_factor"))
    leave_two = _safe_float(concentration.get("leave_two_out_profit_factor"))
    top1 = _safe_float(top_shares.get("1"))
    top2 = _safe_float(top_shares.get("2"))
    median = _safe_float(summary.get("median_trade_net_pnl"))
    total_trades = int(summary.get("trades") or 0)

    if not variant_report.get("eligible_for_blindtest"):
        reasons.append("not_eligible_in_original_brh_v1_walkforward")
    if total_trades < config.min_total_validation_trades:
        reasons.append("validation_trades_below_v2_minimum")
    if aggregate["average_trades_per_fold"] < config.min_average_trades_per_fold:
        reasons.append("average_trades_per_fold_below_minimum")
    if int(variant_report.get("positive_folds") or 0) < config.min_positive_folds:
        reasons.append("positive_folds_below_v2_minimum")
    if aggregate["worst_fold_pnl_usdc"] <= config.min_worst_fold_pnl_usdc:
        reasons.append("worst_fold_pnl_not_positive")
    if pf is None or pf < config.min_profit_factor:
        reasons.append("profit_factor_below_minimum")
    if pf is None or pf > config.max_profit_factor_for_selection:
        reasons.append("profit_factor_above_overfit_ceiling")
    if cost_pf is None or cost_pf < config.min_cost_robust_profit_factor:
        reasons.append("cost_robust_profit_factor_below_minimum")
    if median is None or median <= config.min_median_trade_pnl_usdc:
        reasons.append("median_trade_pnl_not_positive")
    if leave_one is None or leave_one < config.min_leave_one_out_profit_factor:
        reasons.append("leave_one_out_profit_factor_below_minimum")
    if leave_two is None or leave_two < config.min_leave_two_out_profit_factor:
        reasons.append("leave_two_out_profit_factor_below_minimum")
    if top1 is None or top1 > config.max_top1_pnl_share:
        reasons.append("top1_pnl_share_above_limit")
    if top2 is None or top2 > config.max_top2_pnl_share:
        reasons.append("top2_pnl_share_above_limit")
    if aggregate["positive_edge_folds_vs_random"] < config.min_positive_edge_folds:
        reasons.append("positive_edge_folds_vs_random_below_minimum")
    if (
        variant_id != RISK_ON_BASELINE_VARIANT_ID
        and aggregate["positive_edge_folds_vs_risk_on"] < config.min_positive_edge_folds
    ):
        reasons.append("positive_edge_folds_vs_risk_on_below_minimum")
    trimmed_random = aggregate["trimmed_edge_after_cost_usdc"][
        "selected_minus_random_unconditional"
    ]
    if trimmed_random is None or trimmed_random <= config.min_trimmed_edge_vs_random_usdc:
        reasons.append("trimmed_edge_vs_random_not_positive")
    trimmed_risk_on = aggregate["trimmed_edge_after_cost_usdc"][
        "selected_minus_risk_on_non_overlap"
    ]
    if (
        variant_id != RISK_ON_BASELINE_VARIANT_ID
        and (
            trimmed_risk_on is None
            or trimmed_risk_on <= config.min_trimmed_edge_vs_risk_on_usdc
        )
    ):
        reasons.append("trimmed_edge_vs_risk_on_not_positive")
    if config.require_strategy_beats_buy_hold_per_day and (
        aggregate["strategy_minus_buy_hold_usdc_per_day"] is None
        or aggregate["strategy_minus_buy_hold_usdc_per_day"] <= 0
    ):
        reasons.append("does_not_beat_training_buy_hold_usdc_per_day")
    return reasons


def variant_robustness_gatekeeper(
    execution: pd.DataFrame,
    validation_trades: pd.DataFrame,
    variant_report: dict[str, Any],
    buy_hold_usdc_per_day: float | None,
    validation_period_days: float,
    config: BrhSelectionRobustnessConfig,
    brh_config: BrhConfig,
) -> dict[str, Any]:
    """Evaluate one BRH/ERV-v1 variant against stricter training-only gates."""
    variant_id = variant_report["variant"]["variant_id"]
    fold_reports = [
        _fold_report(
            execution,
            validation_trades,
            variant_id,
            fold,
            config,
            brh_config,
        )
        for fold in variant_report.get("folds", [])
    ]
    selected_trades = validation_trades[validation_trades["variant_id"] == variant_id]
    selected_pnls = _pnls_from_trades(selected_trades)
    random_pnls: list[float] = []
    risk_on_pnls: list[float] = []
    for fold in variant_report.get("folds", []):
        val_start = pd.Timestamp(fold["validation_start"])
        val_end = pd.Timestamp(fold["validation_end"])
        thresholds = _thresholds_from_fold(fold)
        risk_on_pnls.extend(
            _window_pnls(
                baseline_risk_on_windows(
                    execution,
                    val_start,
                    val_end,
                    thresholds,
                    brh_config,
                    config.hold_hours,
                    enforce_non_overlap=True,
                )
            )
        )
        selected_count = len(
            _fold_selected_trades(validation_trades, variant_id, val_start, val_end)
        )
        all_windows = unconditional_eth_windows(
            execution,
            val_start,
            val_end,
            config,
            brh_config,
            enforce_non_overlap=True,
        )
        requested_random_count = max(
            selected_count * config.random_baseline_sample_multiplier,
            config.min_random_baseline_windows,
        )
        random_pnls.extend(
            _window_pnls(
                _deterministic_sample(
                    all_windows,
                    requested_random_count,
                    config.random_seed,
                    f"{variant_id}:{fold['fold_index']}",
                )
            )
        )

    fold_pnls = [
        float(fold["selected"]["pnl_usdc"]["sum"])
        for fold in fold_reports
    ]
    random_edges = [
        fold["edge_after_cost_usdc"]["selected_minus_random_unconditional"]
        for fold in fold_reports
    ]
    risk_on_edges = [
        fold["edge_after_cost_usdc"]["selected_minus_risk_on_non_overlap"]
        for fold in fold_reports
    ]
    selected_mean = _mean_or_none(selected_pnls)
    risk_on_mean = _mean_or_none(risk_on_pnls)
    random_mean = _mean_or_none(random_pnls)
    trimmed_selected_mean = _trimmed_mean_or_none(selected_pnls, config.top_trim_count)
    trimmed_risk_on_mean = _trimmed_mean_or_none(risk_on_pnls, config.top_trim_count)
    trimmed_random_mean = _trimmed_mean_or_none(random_pnls, config.top_trim_count)
    validation_summary = variant_report.get("validation_summary", {})
    strategy_usdc_per_day = (
        float(validation_summary.get("pnl_usdc") or 0.0) / validation_period_days
        if validation_period_days > 0
        else None
    )
    aggregate = {
        "validation_summary": validation_summary,
        "concentration": concentration_metrics(selected_trades),
        "average_trades_per_fold": (
            len(selected_trades) / max(len(fold_reports), 1)
        ),
        "worst_fold_pnl_usdc": min(fold_pnls) if fold_pnls else None,
        "strategy_usdc_per_day": strategy_usdc_per_day,
        "buy_hold_usdc_per_day": buy_hold_usdc_per_day,
        "strategy_minus_buy_hold_usdc_per_day": (
            strategy_usdc_per_day - buy_hold_usdc_per_day
            if strategy_usdc_per_day is not None and buy_hold_usdc_per_day is not None
            else None
        ),
        "mean_after_cost_usdc": {
            "selected": selected_mean,
            "risk_on_non_overlap": risk_on_mean,
            "random_unconditional": random_mean,
        },
        "edge_after_cost_usdc": {
            "selected_minus_risk_on_non_overlap": (
                selected_mean - risk_on_mean
                if selected_mean is not None and risk_on_mean is not None
                else None
            ),
            "selected_minus_random_unconditional": (
                selected_mean - random_mean
                if selected_mean is not None and random_mean is not None
                else None
            ),
        },
        "trimmed_mean_after_cost_usdc": {
            "selected": trimmed_selected_mean,
            "risk_on_non_overlap": trimmed_risk_on_mean,
            "random_unconditional": trimmed_random_mean,
        },
        "trimmed_edge_after_cost_usdc": {
            "selected_minus_risk_on_non_overlap": (
                trimmed_selected_mean - trimmed_risk_on_mean
                if trimmed_selected_mean is not None and trimmed_risk_on_mean is not None
                else None
            ),
            "selected_minus_random_unconditional": (
                trimmed_selected_mean - trimmed_random_mean
                if trimmed_selected_mean is not None and trimmed_random_mean is not None
                else None
            ),
        },
        "positive_edge_folds_vs_random": _positive_fold_count(random_edges),
        "positive_edge_folds_vs_risk_on": _positive_fold_count(
            risk_on_edges,
            allow_zero=variant_id == RISK_ON_BASELINE_VARIANT_ID,
        ),
    }
    rejection_reasons = _variant_gatekeeper_reasons(
        variant_id,
        variant_report,
        aggregate,
        config,
    )
    aggregate["passes_robust_gatekeeper"] = not rejection_reasons
    aggregate["selection_score"] = _selection_score(aggregate, config)
    return {
        "variant_id": variant_id,
        "already_blindtested_in_v1": variant_id in ALREADY_BLINDTESTED_VARIANT_IDS,
        "eligible_for_blindtest_in_brh_v1": bool(
            variant_report.get("eligible_for_blindtest")
        ),
        "robust_gatekeeper_rejection_reasons": rejection_reasons,
        "folds": fold_reports,
        "aggregate": aggregate,
    }


def _validation_period(report: dict[str, Any]) -> tuple[pd.Timestamp, pd.Timestamp]:
    variants = report.get("variants", [])
    if not variants:
        msg = "BRH-v1 report has no variants; cannot run gatekeeper."
        raise ValueError(msg)
    folds = variants[0].get("folds", [])
    if not folds:
        msg = "BRH-v1 report has no folds; cannot run gatekeeper."
        raise ValueError(msg)
    return (
        pd.Timestamp(folds[0]["validation_start"]),
        pd.Timestamp(folds[-1]["validation_end"]),
    )


def run_brh_selection_edge_robustness_v2check(
    config: BrhSelectionRobustnessConfig | None = None,
) -> dict[str, Any]:
    """Run the strict training-only BRH/ERV robustness gatekeeper."""
    active_config = config or BrhSelectionRobustnessConfig()
    report = _read_json(active_config.source_report_path)
    validation_trades = _read_validation_trades(active_config.source_validation_trades_path)
    execution, training_start, blindtest_start, blindtest_end = _load_full_execution()
    execution = execution.loc[
        (execution.index >= training_start) & (execution.index < blindtest_start)
    ]
    brh_config = BrhConfig()
    validation_start, validation_end = _validation_period(report)
    validation_days = max((validation_end - validation_start).total_seconds() / 86400.0, 1.0)
    buy_hold = _full_period_buy_hold(
        execution,
        validation_start,
        validation_end,
        brh_config,
    )
    buy_hold_pnl = _safe_float(buy_hold.get("pnl_usdc"))
    buy_hold_usdc_per_day = (
        buy_hold_pnl / validation_days if buy_hold_pnl is not None else None
    )

    variant_reports = [
        variant_robustness_gatekeeper(
            execution,
            validation_trades,
            variant_report,
            buy_hold_usdc_per_day,
            validation_days,
            active_config,
            brh_config,
        )
        for variant_report in report.get("variants", [])
    ]
    passing_variants = [
        item
        for item in variant_reports
        if item["aggregate"]["passes_robust_gatekeeper"]
    ]
    best_variant = None
    if passing_variants:
        best_variant = max(
            passing_variants,
            key=lambda item: (
                item["aggregate"]["selection_score"],
                item["aggregate"]["concentration"]["leave_two_out_profit_factor"],
                item["aggregate"]["validation_summary"]["pnl_usdc"],
            ),
        )
    selected_v1_id = (report.get("selected_variant") or {}).get("variant_id")
    selected_variant_id = best_variant["variant_id"] if best_variant else None
    selected_is_repeat = selected_variant_id in ALREADY_BLINDTESTED_VARIANT_IDS

    if best_variant is None:
        status = "no_robust_selection_edge_candidate"
        recommended_next = (
            "Do not UI-backtest. The stricter gatekeeper found no BRH/ERV "
            "variant that survives missing-baseline and concentration controls."
        )
    elif selected_is_repeat:
        status = "best_candidate_already_blindtested_in_v1"
        recommended_next = (
            "Do not run a second blindtest. The best robust candidate is the "
            "already consumed v1 candidate, so the BRH/ERV line should be closed "
            "unless a new hypothesis is specified before seeing any further "
            "blindtest outcome."
        )
    else:
        status = "new_training_only_candidate_found"
        recommended_next = (
            "Do not run the UI full backtest yet. A separate frozen research "
            "blindtest runner may be built for this one never-blindtested "
            "candidate, with no parameter changes afterward."
        )

    blindtest_conditionally_allowed = (
        best_variant is not None
        and not selected_is_repeat
        and selected_variant_id is not None
    )
    report_out: dict[str, Any] = {
        "strategy_version": BRH_SELECTION_EDGE_ROBUSTNESS_VERSION,
        "diagnoses_strategy_versions": [
            BRH_V1_VERSION,
            BRH_WINDOW_SELECTION_EDGE_VERSION,
        ],
        "status": status,
        "research_only": True,
        "training_only": True,
        "runs_new_blindtest": False,
        "runs_ui_backtest": False,
        "uses_blindtest_for_selection": False,
        "evaluates_alternative_blindtest_variants": False,
        "already_blindtested_variant_ids": sorted(ALREADY_BLINDTESTED_VARIANT_IDS),
        "risk_on_baseline_variant_id": RISK_ON_BASELINE_VARIANT_ID,
        "data_range": {
            "training_start": training_start.isoformat(),
            "validation_start": validation_start.isoformat(),
            "validation_end": validation_end.isoformat(),
            "blindtest_start_not_used": blindtest_start.isoformat(),
            "blindtest_end_not_used": blindtest_end.isoformat(),
        },
        "gatekeeper_config": {
            key: str(value) if isinstance(value, Path) else _to_jsonable(value)
            for key, value in active_config.__dict__.items()
        },
        "baseline_fairness": {
            "adds_random_unconditional_eth_72h_baseline": True,
            "adds_full_period_eth_buy_hold_baseline": True,
            "keeps_risk_on_non_overlap_baseline": True,
            "buy_hold_validation_period": {
                **buy_hold,
                "usdc_per_day": buy_hold_usdc_per_day,
                "validation_days": validation_days,
            },
        },
        "selected_v1_variant_id": selected_v1_id,
        "variant_count": len(variant_reports),
        "passing_variant_count": len(passing_variants),
        "passing_variants": [
            {
                "variant_id": item["variant_id"],
                "already_blindtested_in_v1": item["already_blindtested_in_v1"],
                "aggregate": item["aggregate"],
            }
            for item in passing_variants
        ],
        "best_training_only_variant_after_robustness_gatekeeper": {
            "variant_id": best_variant["variant_id"],
            "already_blindtested_in_v1": best_variant["already_blindtested_in_v1"],
            "aggregate": best_variant["aggregate"],
        }
        if best_variant is not None
        else None,
        "variants": variant_reports,
        "decision_summary": {
            "brh_erv_line_closed_now": best_variant is None or selected_is_repeat,
            "research_blindtest_conditionally_allowed": blindtest_conditionally_allowed,
            "ui_full_backtest_allowed_now": False,
            "current_brh_v1_remains_archived": True,
            "recommended_next_step": recommended_next,
        },
    }

    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = (
        active_config.output_dir / "brh_selection_edge_robustness_v2check_report.json"
    )
    report_out["output_paths"] = {"report": str(report_path)}
    report_path.write_text(
        json.dumps(report_out, indent=2, sort_keys=True, default=_to_jsonable) + "\n",
        encoding="utf-8",
    )
    return report_out
