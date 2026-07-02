"""Post-mortem diagnostics for BRH/ERV-v1.

This module is intentionally diagnostic-only. It consumes the already produced
BRH-v1 research report and validation trade ledger. It does not select a new
variant, does not run a second variant blindtest and does not alter BRH-v1.

The goal is to explain why BRH-v1 looked strong in training/walkforward but
only weakly positive in the single frozen blindtest.
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
from src.research.brh_v1 import (
    BRH_V1_VERSION,
    BrhConfig,
    BrhThresholds,
    _load_full_execution,
    _to_jsonable,
    calibrate_brh_thresholds,
)
from src.research.erh_v1 import _net_return, _profit_factor

BRH_V1_DIAGNOSTIC_VERSION = "brh_v1_attribution_decay_diagnostics_20260702"


@dataclass(frozen=True)
class BrhDiagnosticConfig:
    """Configuration for the BRH-v1 post-mortem diagnostic."""

    source_report_path: Path = REPORTS_DIR / "research" / "brh_v1" / "brh_v1_research_report.json"
    source_validation_trades_path: Path = (
        REPORTS_DIR / "research" / "brh_v1" / "brh_v1_validation_trades.csv"
    )
    output_dir: Path = REPORTS_DIR / "research" / "brh_v1_diag"
    horizons_hours: tuple[int, ...] = (6, 12, 24, 36, 48, 60, 72)
    top_trade_counts: tuple[int, ...] = (1, 2, 3)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        msg = (
            f"missing BRH-v1 report: {path}. Run "
            "python scripts\\run_brh_v1_research.py first."
        )
        raise FileNotFoundError(msg)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_validation_trades(path: Path) -> pd.DataFrame:
    if not path.exists():
        msg = (
            f"missing BRH-v1 validation trades: {path}. Run "
            "python scripts\\run_brh_v1_research.py first."
        )
        raise FileNotFoundError(msg)
    frame = pd.read_csv(path)
    return _normalise_trade_frame(frame)


def _normalise_trade_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.copy()
    for column in ("signal_time", "entry_time", "exit_time"):
        if column in result.columns:
            result[column] = pd.to_datetime(result[column], utc=True)
    numeric_columns = [
        "hold_hours",
        "entry_price",
        "exit_price",
        "net_return",
        "net_pnl_usdc",
        "fees_and_slippage_ret",
        "mfe_ret",
        "mae_ret",
        "btc_drawdown_at_signal",
        "btc_ema_at_signal",
        "ethbtc_ret_6_at_signal",
        "eth_dist_to_high_at_signal",
        "eth_ofi_3sum_at_signal",
    ]
    for column in numeric_columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def _blindtest_trade_frame(report: dict[str, Any]) -> pd.DataFrame:
    return _normalise_trade_frame(pd.DataFrame(report.get("blindtest_trades", [])))


def _top_share(pnls: pd.Series, count: int) -> float | None:
    if pnls.empty:
        return None
    total = float(pnls.sum())
    if total <= 0:
        return None
    positive = pnls[pnls > 0].sort_values(ascending=False)
    if positive.empty:
        return None
    return float(positive.head(count).sum() / total)


def _gini(values: pd.Series) -> float | None:
    if values.empty:
        return None
    absolute = np.sort(np.abs(values.to_numpy(dtype=float)))
    total = float(absolute.sum())
    if total <= 0:
        return None
    n = len(absolute)
    weighted = float(np.sum((np.arange(1, n + 1) * absolute)))
    return (2.0 * weighted) / (n * total) - (n + 1.0) / n


def _remove_largest_winners(pnls: pd.Series, count: int) -> list[float]:
    ordered_indices = pnls[pnls > 0].sort_values(ascending=False).head(count).index
    return [float(value) for index, value in pnls.items() if index not in ordered_indices]


def concentration_metrics(trades: pd.DataFrame) -> dict[str, Any]:
    """Return concentration and leave-out metrics for a trade ledger."""
    if trades.empty:
        return {
            "trade_count": 0,
            "total_pnl_usdc": 0.0,
            "median_trade_pnl_usdc": None,
            "profit_factor": None,
            "top_trade_pnl_share": {},
            "leave_one_out_profit_factor": None,
            "leave_two_out_profit_factor": None,
            "pnl_abs_gini": None,
        }
    pnls = trades["net_pnl_usdc"].astype(float)
    top_shares = {str(count): _top_share(pnls, count) for count in (1, 2, 3)}
    leave_one = _profit_factor(_remove_largest_winners(pnls, 1))
    leave_two = _profit_factor(_remove_largest_winners(pnls, 2))
    return {
        "trade_count": int(len(trades)),
        "total_pnl_usdc": float(pnls.sum()),
        "median_trade_pnl_usdc": float(pnls.median()),
        "profit_factor": _to_jsonable(_profit_factor([float(value) for value in pnls])),
        "top_trade_pnl_share": top_shares,
        "leave_one_out_profit_factor": _to_jsonable(leave_one),
        "leave_two_out_profit_factor": _to_jsonable(leave_two),
        "pnl_abs_gini": _gini(pnls),
    }


def _ks_two_sample(left: pd.Series, right: pd.Series) -> dict[str, Any]:
    left_values = np.sort(left.dropna().to_numpy(dtype=float))
    right_values = np.sort(right.dropna().to_numpy(dtype=float))
    if len(left_values) == 0 or len(right_values) == 0:
        return {
            "statistic": None,
            "approx_p_value": None,
            "n_left": len(left_values),
            "n_right": len(right_values),
        }
    combined = np.sort(np.concatenate([left_values, right_values]))
    left_cdf = np.searchsorted(left_values, combined, side="right") / len(left_values)
    right_cdf = np.searchsorted(right_values, combined, side="right") / len(right_values)
    statistic = float(np.max(np.abs(left_cdf - right_cdf)))
    effective_n = math.sqrt(
        (len(left_values) * len(right_values))
        / (len(left_values) + len(right_values))
    )
    approx_p = min(1.0, max(0.0, 2.0 * math.exp(-2.0 * (effective_n * statistic) ** 2)))
    return {
        "statistic": statistic,
        "approx_p_value": approx_p,
        "n_left": int(len(left_values)),
        "n_right": int(len(right_values)),
    }


def _feature_stats(values: pd.Series) -> dict[str, Any]:
    clean = values.replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return {"count": 0, "mean": None, "median": None, "std": None, "p20": None, "p80": None}
    return {
        "count": int(len(clean)),
        "mean": float(clean.mean()),
        "median": float(clean.median()),
        "std": float(clean.std(ddof=0)),
        "p20": float(clean.quantile(0.20)),
        "p80": float(clean.quantile(0.80)),
    }


def distribution_shift_metrics(
    execution: pd.DataFrame,
    training_start: pd.Timestamp,
    blindtest_start: pd.Timestamp,
    blindtest_end: pd.Timestamp,
    thresholds: BrhThresholds,
) -> dict[str, Any]:
    """Compare core feature distributions in training and blindtest."""
    signal_rows = execution[execution["brh_signal_update_bar"].fillna(False).astype(bool)]
    train = signal_rows[
        (signal_rows.index >= training_start) & (signal_rows.index < blindtest_start)
    ]
    blind = signal_rows[
        (signal_rows.index >= blindtest_start) & (signal_rows.index <= blindtest_end)
    ]
    features = [
        "btc_4h_drawdown_from_20d_high",
        "btc_4h_close_vs_ema20",
        "ethbtc_4h_ret_6",
        "eth_4h_dist_to_20d_high",
        "eth_of_ofi_4h_3sum",
    ]
    by_feature: dict[str, Any] = {}
    for feature in features:
        by_feature[feature] = {
            "training": _feature_stats(train[feature]),
            "blindtest": _feature_stats(blind[feature]),
            "ks_two_sample": _ks_two_sample(train[feature], blind[feature]),
        }
    training_days = max((blindtest_start - training_start).total_seconds() / 86400.0, 1.0)
    blind_days = max((blindtest_end - blindtest_start).total_seconds() / 86400.0, 1.0)
    train_risk_on = train["btc_4h_drawdown_from_20d_high"] >= thresholds.btc_drawdown_q80
    blind_risk_on = blind["btc_4h_drawdown_from_20d_high"] >= thresholds.btc_drawdown_q80
    return {
        "features": by_feature,
        "risk_on_definition": "btc_4h_drawdown_from_20d_high >= selected_training_q80",
        "risk_on_threshold": thresholds.btc_drawdown_q80,
        "training_risk_on_bars": int(train_risk_on.sum()),
        "blindtest_risk_on_bars": int(blind_risk_on.sum()),
        "training_risk_on_bars_per_day": float(train_risk_on.sum() / training_days),
        "blindtest_risk_on_bars_per_day": float(blind_risk_on.sum() / blind_days),
        "risk_on_bars_per_day_ratio_blind_over_train": (
            float((blind_risk_on.sum() / blind_days) / (train_risk_on.sum() / training_days))
            if train_risk_on.sum() > 0
            else None
        ),
    }


def _position_for_timestamp(index: pd.Index, timestamp: pd.Timestamp) -> int | None:
    try:
        return int(index.get_loc(timestamp))
    except KeyError:
        return None


def horizon_decay_metrics(
    trades: pd.DataFrame,
    execution: pd.DataFrame,
    horizons_hours: tuple[int, ...],
    cost_config: BrhConfig,
) -> dict[str, Any]:
    """Calculate fixed-horizon return/MFE/MAE diagnostics for existing trades."""
    if trades.empty:
        return {"trade_count": 0, "by_horizon": {}}
    rows_by_horizon: dict[int, list[dict[str, float]]] = {horizon: [] for horizon in horizons_hours}
    full_index = execution.index
    for _, trade in trades.iterrows():
        entry_time = pd.Timestamp(trade["entry_time"])
        entry_pos = _position_for_timestamp(full_index, entry_time)
        if entry_pos is None:
            continue
        entry_price = float(trade["entry_price"])
        for horizon in horizons_hours:
            exit_pos = entry_pos + horizon
            if exit_pos >= len(execution):
                continue
            exit_price = float(execution.iloc[exit_pos]["open"])
            net_ret, _ = _net_return(
                entry_price,
                exit_price,
                cost_config.trading_cost_config,
            )
            path = execution.iloc[entry_pos:exit_pos]
            mfe = max(0.0, float(path["high"].max()) / entry_price - 1.0) if not path.empty else 0.0
            mae = min(0.0, float(path["low"].min()) / entry_price - 1.0) if not path.empty else 0.0
            rows_by_horizon[horizon].append(
                {
                    "net_return": net_ret,
                    "net_pnl_usdc": net_ret * cost_config.position_size_usdc,
                    "mfe_ret": mfe,
                    "mae_ret": mae,
                }
            )
    by_horizon: dict[str, Any] = {}
    for horizon, rows in rows_by_horizon.items():
        frame = pd.DataFrame(rows)
        if frame.empty:
            by_horizon[str(horizon)] = {
                "trade_count": 0,
                "mean_net_pnl_usdc": None,
                "median_net_pnl_usdc": None,
                "mean_mfe_ret": None,
                "mean_mae_ret": None,
                "win_rate": None,
            }
            continue
        by_horizon[str(horizon)] = {
            "trade_count": int(len(frame)),
            "mean_net_pnl_usdc": float(frame["net_pnl_usdc"].mean()),
            "median_net_pnl_usdc": float(frame["net_pnl_usdc"].median()),
            "mean_mfe_ret": float(frame["mfe_ret"].mean()),
            "mean_mae_ret": float(frame["mae_ret"].mean()),
            "win_rate": float((frame["net_pnl_usdc"] > 0).mean()),
        }
    return {"trade_count": int(len(trades)), "by_horizon": by_horizon}


def _full_period_buy_hold(
    execution: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    config: BrhConfig,
) -> dict[str, Any]:
    window = execution.loc[(execution.index >= start) & (execution.index <= end)]
    if window.empty:
        return {"net_return": None, "pnl_usdc": None}
    net_ret, _ = _net_return(
        float(window.iloc[0]["open"]),
        float(window.iloc[-1]["close"]),
        config.trading_cost_config,
    )
    return {
        "net_return": net_ret,
        "pnl_usdc": net_ret * config.position_size_usdc,
    }


def selected_window_attribution(
    trades: pd.DataFrame,
    execution: pd.DataFrame,
    config: BrhConfig,
) -> dict[str, Any]:
    """Confirm fixed spot holds are selected ETH exposure, not intra-window alpha."""
    if trades.empty:
        return {
            "trade_count": 0,
            "mean_signal_minus_same_window_eth": None,
            "note": "no trades",
        }
    differences: list[float] = []
    for _, trade in trades.iterrows():
        net_ret, _ = _net_return(
            float(trade["entry_price"]),
            float(trade["exit_price"]),
            config.trading_cost_config,
        )
        differences.append(float(trade["net_return"]) - net_ret)
    return {
        "trade_count": int(len(trades)),
        "mean_signal_minus_same_window_eth": float(np.mean(differences)),
        "max_abs_signal_minus_same_window_eth": float(np.max(np.abs(differences))),
        "interpretation": (
            "A fixed spot long has no intra-window alpha by construction; edge "
            "can only come from selecting better ETH exposure windows."
        ),
    }


def variant_selection_metrics(
    report: dict[str, Any],
    validation_trades: pd.DataFrame,
) -> dict[str, Any]:
    """Inspect training-only selection bias and fold rank stability."""
    variants = report.get("variants", [])
    selected = report.get("selected_variant") or {}
    selected_variant_id = selected.get("variant_id")
    variant_rows: list[dict[str, Any]] = []
    for item in variants:
        variant_id = item["variant"]["variant_id"]
        trades = validation_trades[validation_trades["variant_id"] == variant_id]
        row = {
            "variant_id": variant_id,
            "eligible_for_blindtest": bool(item.get("eligible_for_blindtest")),
            "positive_folds": int(item.get("positive_folds", 0)),
            "validation_summary": item.get("validation_summary", {}),
            "concentration": concentration_metrics(trades),
            "selected": variant_id == selected_variant_id,
        }
        variant_rows.append(row)

    fold_winners: dict[str, str] = {}
    for fold_index in range(6):
        best_variant = None
        best_pnl = -math.inf
        for item in variants:
            folds = item.get("folds", [])
            if fold_index >= len(folds):
                continue
            pnl = float(folds[fold_index]["validation_summary"]["pnl_usdc"])
            if pnl > best_pnl:
                best_pnl = pnl
                best_variant = item["variant"]["variant_id"]
        if best_variant is not None:
            fold_winners[str(fold_index + 1)] = best_variant

    jaccard_pairs: list[float] = []
    variant_ids = [item["variant"]["variant_id"] for item in variants]
    entry_sets = {
        variant_id: set(
            validation_trades.loc[
                validation_trades["variant_id"] == variant_id, "entry_time"
            ].astype(str)
        )
        for variant_id in variant_ids
    }
    for left_index, left_id in enumerate(variant_ids):
        for right_id in variant_ids[left_index + 1 :]:
            union = entry_sets[left_id] | entry_sets[right_id]
            if not union:
                continue
            jaccard_pairs.append(len(entry_sets[left_id] & entry_sets[right_id]) / len(union))

    return {
        "selection_rule_in_v1": "highest_training_profit_factor_then_pnl",
        "selected_variant_id": selected_variant_id,
        "fold_winners_by_pnl": fold_winners,
        "mean_pairwise_entry_jaccard": float(np.mean(jaccard_pairs)) if jaccard_pairs else None,
        "max_pairwise_entry_jaccard": float(np.max(jaccard_pairs)) if jaccard_pairs else None,
        "variants": variant_rows,
    }


def _thresholds_from_report(report: dict[str, Any]) -> BrhThresholds:
    raw = report.get("selected_thresholds")
    if raw is None:
        msg = "BRH-v1 report has no selected_thresholds; cannot run diagnostics."
        raise ValueError(msg)
    return BrhThresholds(**raw)


def verify_blindtest_threshold_source(
    report: dict[str, Any],
    execution: pd.DataFrame,
    training_start: pd.Timestamp,
    blindtest_start: pd.Timestamp,
) -> dict[str, Any]:
    """Verify selected blindtest thresholds were calibrated on training only."""
    reported = _thresholds_from_report(report)
    recalculated = calibrate_brh_thresholds(
        execution,
        training_start,
        blindtest_start - pd.Timedelta(hours=1),
    )
    diffs = {
        field: abs(float(getattr(reported, field)) - float(getattr(recalculated, field)))
        for field in asdict(reported)
    }
    return {
        "blindtest_quantile_thresholds_source": "training_only",
        "matches_recalculated_training_only_thresholds": all(
            value < 1e-12 for value in diffs.values()
        ),
        "max_abs_threshold_diff": max(diffs.values()) if diffs else None,
        "reported_thresholds": asdict(reported),
        "recalculated_training_only_thresholds": asdict(recalculated),
        "threshold_abs_diffs": diffs,
    }


def build_decision_summary(
    distribution_shift: dict[str, Any],
    selected_training_concentration: dict[str, Any] | None,
    blind_concentration: dict[str, Any],
    training_horizon_decay: dict[str, Any],
    blind_horizon_decay: dict[str, Any],
) -> dict[str, Any]:
    """Summarize what the diagnostic suggests without creating v2."""
    risk_ratio = distribution_shift.get("risk_on_bars_per_day_ratio_blind_over_train")
    blind_top2 = (blind_concentration.get("top_trade_pnl_share") or {}).get("2")
    training_leave_two = (
        selected_training_concentration or {}
    ).get("leave_two_out_profit_factor")
    blind_72 = (blind_horizon_decay.get("by_horizon") or {}).get("72", {})
    blind_24 = (blind_horizon_decay.get("by_horizon") or {}).get("24", {})
    horizon_decay_supported = (
        blind_24.get("mean_net_pnl_usdc") is not None
        and blind_72.get("mean_net_pnl_usdc") is not None
        and blind_24["mean_net_pnl_usdc"] > blind_72["mean_net_pnl_usdc"]
    )
    concentration_supported = (
        (isinstance(blind_top2, float) and blind_top2 > 0.75)
        or (
            isinstance(training_leave_two, (int, float))
            and not math.isinf(float(training_leave_two))
            and float(training_leave_two) < 1.30
        )
    )
    regime_shift_supported = isinstance(risk_ratio, float) and risk_ratio < 0.50
    findings = []
    if regime_shift_supported:
        findings.append("risk_on_availability_dropped_sharply_in_blindtest")
    if horizon_decay_supported:
        findings.append("shorter_horizons_outperformed_72h_for_existing_blind_trades")
    if concentration_supported:
        findings.append("pnl_concentration_or_leave_two_out_fragility_detected")
    if not findings:
        findings.append("no_single_dominant_decay_cause_detected")
    return {
        "diagnostic_findings": findings,
        "regime_shift_supported": regime_shift_supported,
        "horizon_decay_supported": horizon_decay_supported,
        "concentration_supported": concentration_supported,
        "archive_current_brh_v1": True,
        "v2_allowed_now": False,
        "recommended_next_step": (
            "Do not build BRH-v2 from this diagnostic alone. Use the report to "
            "decide whether an external review should specify one training-only "
            "v2 selection rule; no second blindtest or UI integration is allowed."
        ),
    }


def run_brh_v1_diagnostics(config: BrhDiagnosticConfig | None = None) -> dict[str, Any]:
    """Run BRH-v1 post-mortem diagnostics only."""
    active_config = config or BrhDiagnosticConfig()
    report = _read_json(active_config.source_report_path)
    validation_trades = _read_validation_trades(active_config.source_validation_trades_path)
    blindtest_trades = _blindtest_trade_frame(report)
    brh_config = BrhConfig()
    execution, training_start, blindtest_start, blindtest_end = _load_full_execution()
    selected_thresholds = _thresholds_from_report(report)
    selected_variant_id = (report.get("selected_variant") or {}).get("variant_id")
    selected_training_trades = validation_trades[
        validation_trades["variant_id"] == selected_variant_id
    ]

    threshold_verification = verify_blindtest_threshold_source(
        report,
        execution,
        training_start,
        blindtest_start,
    )
    distribution_shift = distribution_shift_metrics(
        execution,
        training_start,
        blindtest_start,
        blindtest_end,
        selected_thresholds,
    )
    training_concentration = concentration_metrics(selected_training_trades)
    blind_concentration = concentration_metrics(blindtest_trades)
    training_horizon_decay = horizon_decay_metrics(
        selected_training_trades,
        execution,
        active_config.horizons_hours,
        brh_config,
    )
    blind_horizon_decay = horizon_decay_metrics(
        blindtest_trades,
        execution,
        active_config.horizons_hours,
        brh_config,
    )
    training_window_attribution = selected_window_attribution(
        selected_training_trades,
        execution,
        brh_config,
    )
    blind_window_attribution = selected_window_attribution(
        blindtest_trades,
        execution,
        brh_config,
    )
    selection = variant_selection_metrics(report, validation_trades)
    buy_hold = {
        "training_full_period": _full_period_buy_hold(
            execution,
            training_start,
            blindtest_start - pd.Timedelta(hours=1),
            brh_config,
        ),
        "blindtest_full_period": _full_period_buy_hold(
            execution,
            blindtest_start,
            blindtest_end,
            brh_config,
        ),
    }
    decision_summary = build_decision_summary(
        distribution_shift,
        training_concentration,
        blind_concentration,
        training_horizon_decay,
        blind_horizon_decay,
    )

    diagnostic_report: dict[str, Any] = {
        "strategy_version": BRH_V1_DIAGNOSTIC_VERSION,
        "diagnoses_strategy_version": BRH_V1_VERSION,
        "status": "diagnostic_complete",
        "research_only": True,
        "changes_strategy_parameters": False,
        "runs_new_blindtest": False,
        "evaluates_alternative_blindtest_variants": False,
        "uses_blindtest_for_selection": False,
        "data_range": {
            "training_start": training_start.isoformat(),
            "blindtest_start": blindtest_start.isoformat(),
            "blindtest_end": blindtest_end.isoformat(),
        },
        "selected_variant_id": selected_variant_id,
        "threshold_source_verification": threshold_verification,
        "distribution_shift": distribution_shift,
        "selected_variant_training_concentration": training_concentration,
        "selected_variant_blindtest_concentration": blind_concentration,
        "selected_variant_training_horizon_decay": training_horizon_decay,
        "selected_variant_blindtest_horizon_decay": blind_horizon_decay,
        "same_window_eth_attribution": {
            "training": training_window_attribution,
            "blindtest": blind_window_attribution,
        },
        "buy_and_hold_reference": buy_hold,
        "training_selection_forensics": selection,
        "decision_summary": decision_summary,
        "next_required_step": decision_summary["recommended_next_step"],
    }

    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "brh_v1_diagnostic_report.json"
    diagnostic_report["output_paths"] = {"report": str(report_path)}
    report_path.write_text(
        json.dumps(diagnostic_report, indent=2, sort_keys=True, default=_to_jsonable)
        + "\n",
        encoding="utf-8",
    )
    return diagnostic_report
