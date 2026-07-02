"""Training-only ETH Regime Exposure Management edge check.

EREM is intentionally not another BRH/ERV trade-alpha variant. It asks a
different question:

    Can a simple BTC risk-off filter reduce ETH buy-and-hold drawdown in a
    distributed, non-concentrated way?

This module is diagnostic-only. It uses only the 730-day training/walkforward
area, does not touch the blindtest, does not integrate into the router and does
not run the UI backtest.
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
from src.research.brh_v1 import _load_full_execution, _to_jsonable
from src.research.erh_v1 import build_walkforward_windows

EREM_EXPOSURE_EDGE_VERSION = "erem_exposure_edge_check_20260702"


@dataclass(frozen=True)
class EremVariant:
    """One simple BTC risk-off exposure-management definition."""

    variant_id: str
    btc_drawdown_quantile: float
    use_btc_ema_filter: bool = False


@dataclass(frozen=True)
class EremThresholds:
    """Training-only thresholds for one EREM fold."""

    btc_drawdown_threshold: float
    btc_ema_threshold: float = 0.0


@dataclass(frozen=True)
class EremConfig:
    """Configuration for the training-only EREM exposure edge check."""

    output_dir: Path = REPORTS_DIR / "research" / "erem_exposure_edge_check"
    position_size_usdc: float = 100.0
    val_days: int = 120
    purge_days: int = 7
    fold_count: int = 6
    fee_rate_per_side: float = 0.0010
    slippage_rate_per_side: float = 0.0001
    min_positive_folds: int = 5
    min_maxdd_improvement_folds: int = 5
    min_drawdown_reduction_pct: float = 0.25
    max_top1_avoided_block_share: float = 0.40
    max_top2_avoided_block_share: float = 0.60
    min_time_in_market_pct: float = 0.40
    max_time_in_market_pct: float = 0.85

    @property
    def one_way_cost_ret(self) -> float:
        return self.fee_rate_per_side + self.slippage_rate_per_side


def build_erem_variants() -> list[EremVariant]:
    """Return the intentionally tiny EREM risk-off variant set."""
    return [
        EremVariant("erem_btc_drawdown_q20", btc_drawdown_quantile=0.20),
        EremVariant("erem_btc_drawdown_q35", btc_drawdown_quantile=0.35),
        EremVariant(
            "erem_btc_drawdown_q20_or_ema_below0",
            btc_drawdown_quantile=0.20,
            use_btc_ema_filter=True,
        ),
        EremVariant(
            "erem_btc_drawdown_q35_or_ema_below0",
            btc_drawdown_quantile=0.35,
            use_btc_ema_filter=True,
        ),
    ]


def _signal_rows(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["brh_signal_update_bar"].fillna(False).astype(bool)]


def calibrate_erem_thresholds(
    execution: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    variant: EremVariant,
) -> EremThresholds:
    """Calibrate risk-off thresholds from the fold training interval only."""
    calibration = execution.loc[(execution.index >= start) & (execution.index <= end)]
    calibration = _signal_rows(calibration)
    values = calibration["btc_4h_drawdown_from_20d_high"].replace(
        [np.inf, -np.inf],
        np.nan,
    ).dropna()
    if values.empty:
        msg = "cannot calibrate EREM threshold; no valid BTC drawdown values"
        raise ValueError(msg)
    return EremThresholds(
        btc_drawdown_threshold=float(values.quantile(variant.btc_drawdown_quantile)),
        btc_ema_threshold=0.0,
    )


def erem_risk_off(
    row: pd.Series,
    variant: EremVariant,
    thresholds: EremThresholds,
) -> bool:
    """Return whether a closed feature row indicates BTC risk-off."""
    required_columns = ["btc_4h_drawdown_from_20d_high", "btc_4h_close_vs_ema20"]
    if any(pd.isna(row[column]) for column in required_columns):
        return False
    drawdown_off = (
        float(row["btc_4h_drawdown_from_20d_high"])
        < thresholds.btc_drawdown_threshold
    )
    ema_off = (
        variant.use_btc_ema_filter
        and float(row["btc_4h_close_vs_ema20"]) < thresholds.btc_ema_threshold
    )
    return drawdown_off or ema_off


def _max_drawdown_from_curve(equity_curve: list[float]) -> tuple[float, float]:
    if not equity_curve:
        return 0.0, 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        max_dd = max(max_dd, peak - value)
    return max_dd, max_dd / equity_curve[0] if equity_curve[0] > 0 else math.nan


def _top_share(values: list[float], count: int) -> float | None:
    positive = sorted([value for value in values if value > 0], reverse=True)
    total = float(sum(positive))
    if total <= 0:
        return None
    return float(sum(positive[:count]) / total)


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.mean(values))


def _last_signal_at_or_before(
    execution: pd.DataFrame,
    timestamp: pd.Timestamp,
) -> tuple[pd.Timestamp, pd.Series] | None:
    signals = _signal_rows(execution.loc[execution.index <= timestamp])
    if signals.empty:
        return None
    signal_time = signals.index[-1]
    return signal_time, signals.iloc[-1]


def _desired_exposure_changes(
    execution: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    variant: EremVariant,
    thresholds: EremThresholds,
) -> dict[pd.Timestamp, bool]:
    """Build lookahead-safe exposure changes applied at the next 1h open."""
    frame = execution.loc[(execution.index >= start) & (execution.index <= end)]
    if frame.empty:
        return {}
    changes: dict[pd.Timestamp, bool] = {}
    initial_signal = _last_signal_at_or_before(execution, start)
    if initial_signal is not None:
        _, initial_row = initial_signal
        changes[frame.index[0]] = not erem_risk_off(initial_row, variant, thresholds)

    full_index = execution.index
    signal_frame = _signal_rows(frame)
    for signal_time, row in signal_frame.iterrows():
        signal_pos = int(full_index.get_loc(signal_time))
        apply_pos = signal_pos + 1
        if apply_pos >= len(full_index):
            continue
        apply_time = full_index[apply_pos]
        if apply_time < start or apply_time > end:
            continue
        changes[apply_time] = not erem_risk_off(row, variant, thresholds)
    return changes


def simulate_erem_exposure(
    execution: pd.DataFrame,
    variant: EremVariant,
    thresholds: EremThresholds,
    start: pd.Timestamp,
    end: pd.Timestamp,
    config: EremConfig,
) -> dict[str, Any]:
    """Simulate continuous ETH exposure with risk-off flat periods."""
    frame = execution.loc[(execution.index >= start) & (execution.index <= end)]
    if len(frame) < 2:
        return {
            "erem_pnl_usdc": 0.0,
            "buy_hold_pnl_usdc": 0.0,
            "erem_usdc_per_day": 0.0,
            "buy_hold_usdc_per_day": 0.0,
            "strategy_minus_buy_hold_usdc_per_day": 0.0,
            "erem_maxdd_usdc": 0.0,
            "buy_hold_maxdd_usdc": 0.0,
            "erem_maxdd_pct": 0.0,
            "buy_hold_maxdd_pct": 0.0,
            "time_in_market_pct": 0.0,
            "switch_count": 0,
            "avoided_loss_blocks": [],
            "top1_avoided_block_share": None,
            "top2_avoided_block_share": None,
        }

    changes = _desired_exposure_changes(execution, start, end, variant, thresholds)
    opens = frame["open"].astype(float)
    index = list(frame.index)
    one_way_cost = config.one_way_cost_ret
    erem_equity = config.position_size_usdc
    buyhold_equity = config.position_size_usdc * (1.0 - one_way_cost)
    erem_curve = [erem_equity]
    buyhold_curve = [buyhold_equity]
    exposed = False
    exposed_periods = 0
    switch_count = 0
    flat_block_start_price: float | None = float(opens.iloc[0])
    avoided_blocks: list[float] = []

    for pos in range(len(index) - 1):
        now = index[pos]
        current_open = float(opens.iloc[pos])
        next_open = float(opens.iloc[pos + 1])
        if now in changes and changes[now] != exposed:
            if changes[now]:
                if flat_block_start_price is not None:
                    avoided_blocks.append(
                        max(0.0, (flat_block_start_price / current_open - 1.0))
                        * config.position_size_usdc
                    )
                    flat_block_start_price = None
                erem_equity *= 1.0 - one_way_cost
            else:
                erem_equity *= 1.0 - one_way_cost
                flat_block_start_price = current_open
            exposed = changes[now]
            switch_count += 1

        if exposed:
            erem_equity *= next_open / current_open
            exposed_periods += 1
        buyhold_equity *= next_open / current_open
        erem_curve.append(erem_equity)
        buyhold_curve.append(buyhold_equity)

    final_open = float(opens.iloc[-1])
    if exposed:
        erem_equity *= 1.0 - one_way_cost
        erem_curve[-1] = erem_equity
    elif flat_block_start_price is not None:
        avoided_blocks.append(
            max(0.0, (flat_block_start_price / final_open - 1.0))
            * config.position_size_usdc
        )
    buyhold_equity *= 1.0 - one_way_cost
    buyhold_curve[-1] = buyhold_equity
    erem_maxdd_usdc, erem_maxdd_pct = _max_drawdown_from_curve(erem_curve)
    buyhold_maxdd_usdc, buyhold_maxdd_pct = _max_drawdown_from_curve(buyhold_curve)
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    erem_pnl = erem_equity - config.position_size_usdc
    buyhold_pnl = buyhold_equity - config.position_size_usdc
    time_in_market = exposed_periods / max(len(index) - 1, 1)
    return {
        "erem_pnl_usdc": float(erem_pnl),
        "buy_hold_pnl_usdc": float(buyhold_pnl),
        "erem_usdc_per_day": float(erem_pnl / days),
        "buy_hold_usdc_per_day": float(buyhold_pnl / days),
        "strategy_minus_buy_hold_usdc_per_day": float((erem_pnl - buyhold_pnl) / days),
        "erem_maxdd_usdc": float(erem_maxdd_usdc),
        "buy_hold_maxdd_usdc": float(buyhold_maxdd_usdc),
        "erem_maxdd_pct": float(erem_maxdd_pct),
        "buy_hold_maxdd_pct": float(buyhold_maxdd_pct),
        "time_in_market_pct": float(time_in_market),
        "switch_count": switch_count,
        "avoided_loss_blocks": avoided_blocks,
        "top1_avoided_block_share": _top_share(avoided_blocks, 1),
        "top2_avoided_block_share": _top_share(avoided_blocks, 2),
    }


def _aggregate_fold_results(folds: list[dict[str, Any]]) -> dict[str, Any]:
    if not folds:
        return {}
    totals = {
        "erem_pnl_usdc": float(sum(fold["metrics"]["erem_pnl_usdc"] for fold in folds)),
        "buy_hold_pnl_usdc": float(
            sum(fold["metrics"]["buy_hold_pnl_usdc"] for fold in folds)
        ),
    }
    days = sum(fold["days"] for fold in folds)
    avoided_blocks = [
        value
        for fold in folds
        for value in fold["metrics"].get("avoided_loss_blocks", [])
    ]
    time_weights = [fold["days"] for fold in folds]
    time_in_market = np.average(
        [fold["metrics"]["time_in_market_pct"] for fold in folds],
        weights=time_weights,
    )
    maxdd_improvement_folds = sum(
        fold["maxdd_improvement_passed"] for fold in folds
    )
    positive_folds = sum(fold["return_improvement_passed"] for fold in folds)
    return {
        **totals,
        "days": float(days),
        "erem_usdc_per_day": float(totals["erem_pnl_usdc"] / max(days, 1.0)),
        "buy_hold_usdc_per_day": float(totals["buy_hold_pnl_usdc"] / max(days, 1.0)),
        "strategy_minus_buy_hold_usdc_per_day": float(
            (totals["erem_pnl_usdc"] - totals["buy_hold_pnl_usdc"]) / max(days, 1.0)
        ),
        "positive_return_improvement_folds": int(positive_folds),
        "maxdd_improvement_folds": int(maxdd_improvement_folds),
        "mean_erem_maxdd_pct": _mean_or_none(
            [fold["metrics"]["erem_maxdd_pct"] for fold in folds]
        ),
        "mean_buy_hold_maxdd_pct": _mean_or_none(
            [fold["metrics"]["buy_hold_maxdd_pct"] for fold in folds]
        ),
        "time_in_market_pct": float(time_in_market),
        "switch_count": int(sum(fold["metrics"]["switch_count"] for fold in folds)),
        "avoided_loss_block_count": int(len(avoided_blocks)),
        "top1_avoided_block_share": _top_share(avoided_blocks, 1),
        "top2_avoided_block_share": _top_share(avoided_blocks, 2),
    }


def _eligibility_reasons(aggregate: dict[str, Any], config: EremConfig) -> list[str]:
    reasons: list[str] = []
    if aggregate["strategy_minus_buy_hold_usdc_per_day"] <= 0:
        reasons.append("does_not_beat_buy_hold_per_day")
    if aggregate["positive_return_improvement_folds"] < config.min_positive_folds:
        reasons.append("positive_return_improvement_folds_below_minimum")
    if aggregate["maxdd_improvement_folds"] < config.min_maxdd_improvement_folds:
        reasons.append("maxdd_improvement_folds_below_minimum")
    top1 = aggregate["top1_avoided_block_share"]
    top2 = aggregate["top2_avoided_block_share"]
    if top1 is None or top1 > config.max_top1_avoided_block_share:
        reasons.append("top1_avoided_block_share_above_limit")
    if top2 is None or top2 > config.max_top2_avoided_block_share:
        reasons.append("top2_avoided_block_share_above_limit")
    if aggregate["time_in_market_pct"] < config.min_time_in_market_pct:
        reasons.append("time_in_market_below_minimum")
    if aggregate["time_in_market_pct"] > config.max_time_in_market_pct:
        reasons.append("time_in_market_above_maximum")
    return reasons


def evaluate_erem_variant(
    execution: pd.DataFrame,
    variant: EremVariant,
    windows: list[dict[str, str]],
    training_start: pd.Timestamp,
    config: EremConfig,
) -> dict[str, Any]:
    """Evaluate one EREM variant over training-only walkforward folds."""
    fold_reports: list[dict[str, Any]] = []
    for window in windows:
        train_end = pd.Timestamp(window["train_end"])
        validation_start = pd.Timestamp(window["validation_start"])
        validation_end = pd.Timestamp(window["validation_end"])
        thresholds = calibrate_erem_thresholds(
            execution,
            training_start,
            train_end,
            variant,
        )
        metrics = simulate_erem_exposure(
            execution,
            variant,
            thresholds,
            validation_start,
            validation_end,
            config,
        )
        days = max((validation_end - validation_start).total_seconds() / 86400.0, 1.0)
        maxdd_limit = metrics["buy_hold_maxdd_pct"] * (
            1.0 - config.min_drawdown_reduction_pct
        )
        fold_reports.append(
            {
                **window,
                "thresholds": asdict(thresholds),
                "days": days,
                "metrics": metrics,
                "return_improvement_passed": metrics[
                    "strategy_minus_buy_hold_usdc_per_day"
                ]
                > 0,
                "maxdd_improvement_passed": metrics["erem_maxdd_pct"] < maxdd_limit,
                "maxdd_limit_pct": maxdd_limit,
            }
        )
    aggregate = _aggregate_fold_results(fold_reports)
    reasons = _eligibility_reasons(aggregate, config) if aggregate else ["no_folds"]
    score = None
    if not reasons:
        score = (
            aggregate["strategy_minus_buy_hold_usdc_per_day"]
            + max(
                0.0,
                (aggregate["mean_buy_hold_maxdd_pct"] or 0.0)
                - (aggregate["mean_erem_maxdd_pct"] or 0.0),
            )
        )
    return {
        "variant": asdict(variant),
        "folds": fold_reports,
        "aggregate": {
            **aggregate,
            "eligible_for_frozen_blindtest": not reasons,
            "rejection_reasons": reasons,
            "selection_score": score,
        },
    }


def run_erem_exposure_edge_check(config: EremConfig | None = None) -> dict[str, Any]:
    """Run the EREM training-only exposure-management diagnostic."""
    active_config = config or EremConfig()
    execution, training_start, blindtest_start, blindtest_end = _load_full_execution()
    execution = execution.loc[
        (execution.index >= training_start) & (execution.index < blindtest_start)
    ]
    windows = build_walkforward_windows(training_start, blindtest_start, active_config)
    variants = build_erem_variants()
    variant_reports = [
        evaluate_erem_variant(
            execution,
            variant,
            windows,
            training_start,
            active_config,
        )
        for variant in variants
    ]
    passing = [
        report
        for report in variant_reports
        if report["aggregate"]["eligible_for_frozen_blindtest"]
    ]
    best = None
    if passing:
        best = max(
            passing,
            key=lambda report: (
                report["aggregate"]["selection_score"],
                report["aggregate"]["strategy_minus_buy_hold_usdc_per_day"],
            ),
        )
    status = "erem_training_edge_found" if best is not None else "no_erem_training_edge"
    report_out: dict[str, Any] = {
        "strategy_version": EREM_EXPOSURE_EDGE_VERSION,
        "status": status,
        "research_only": True,
        "training_only": True,
        "runs_new_blindtest": False,
        "runs_ui_backtest": False,
        "uses_blindtest_for_selection": False,
        "data_sources_used": [
            "ETHUSDC closed 1h execution candles",
            "BTCUSDC closed 4h risk-off features from existing ERH/BRH feature frame",
        ],
        "data_range": {
            "training_start": training_start.isoformat(),
            "blindtest_start_not_used": blindtest_start.isoformat(),
            "blindtest_end_not_used": blindtest_end.isoformat(),
        },
        "config": {
            key: str(value) if isinstance(value, Path) else _to_jsonable(value)
            for key, value in asdict(active_config).items()
        },
        "variant_count": len(variant_reports),
        "passing_variant_count": len(passing),
        "best_training_only_variant": {
            "variant_id": best["variant"]["variant_id"],
            "aggregate": best["aggregate"],
        }
        if best is not None
        else None,
        "variants": variant_reports,
        "decision_summary": {
            "brh_erv_line_closed": True,
            "erem_frozen_blindtest_conditionally_allowed": best is not None,
            "ui_full_backtest_allowed_now": False,
            "recommended_next_step": (
                "Build exactly one frozen research blindtest for the selected EREM "
                "variant; no UI/router integration yet."
                if best is not None
                else (
                    "Do not UI-backtest. EREM did not show distributed training-only "
                    "drawdown-avoidance edge; ask external review or reassess project "
                    "constraints."
                )
            ),
        },
    }
    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "erem_exposure_edge_check_report.json"
    report_out["output_paths"] = {"report": str(report_path)}
    report_path.write_text(
        json.dumps(report_out, indent=2, sort_keys=True, default=_to_jsonable) + "\n",
        encoding="utf-8",
    )
    return report_out
