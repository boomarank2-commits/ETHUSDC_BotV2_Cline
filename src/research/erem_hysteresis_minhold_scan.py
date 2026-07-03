"""Training-only EREM hysteresis / minimum-state-duration scan.

The real UI full backtest proved that EREM is connected correctly but loses in
the final blindtest year because switching costs dominate the defensive edge.
This scan tests one narrow follow-up idea without touching the router:

    Can minimum exposed/flat durations reduce EREM churn without destroying the
    training-only risk-adjusted edge?

It is research-only.  It does not run a blindtest, does not integrate into the
UI and must not be used to tune the already-consumed 365-day blindtest.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import REPORTS_DIR
from src.research.brh_v1 import _load_full_execution, _to_jsonable
from src.research.erem_exposure_edge_check import (
    EREM_EXPOSURE_EDGE_VERSION,
    EremConfig,
    EremThresholds,
    EremVariant,
    _desired_exposure_changes,
    _max_drawdown_from_curve,
    _top_share,
    calibrate_erem_thresholds,
    simulate_erem_exposure,
)
from src.research.erem_frozen_blindtest import EREM_FROZEN_BLINDTEST_VERSION
from src.research.erem_postmortem_cycle_scan import EREM_POSTMORTEM_CYCLE_VERSION
from src.research.erh_v1 import build_walkforward_windows

EREM_HYSTERESIS_MINHOLD_VERSION = "erem_hysteresis_minhold_scan_20260703"
EREM_BASE_VARIANT_ID = "erem_btc_drawdown_q35_or_ema_below0"


@dataclass(frozen=True)
class EremHysteresisVariant:
    """One minimum-duration overlay on the fixed EREM signal."""

    variant_id: str
    min_exposed_hours: int
    min_flat_hours: int


@dataclass(frozen=True)
class EremHysteresisConfig:
    """Configuration for the training-only hysteresis/minhold scan."""

    output_dir: Path = REPORTS_DIR / "research" / "erem_hysteresis_minhold_scan"
    position_size_usdc: float = 100.0
    fee_rate_per_side: float = 0.0010
    slippage_rate_per_side: float = 0.0001
    val_days: int = 120
    purge_days: int = 7
    fold_count: int = 6
    min_positive_folds: int = 5
    min_beats_base_folds: int = 4
    min_switch_reduction_pct: float = 0.25
    min_strategy_minus_buyhold_usdc_per_day: float = 0.0
    max_top2_avoided_block_share: float = 0.65

    @property
    def erem_config(self) -> EremConfig:
        return EremConfig(
            position_size_usdc=self.position_size_usdc,
            fee_rate_per_side=self.fee_rate_per_side,
            slippage_rate_per_side=self.slippage_rate_per_side,
            val_days=self.val_days,
            purge_days=self.purge_days,
            fold_count=self.fold_count,
        )


def fixed_erem_variant() -> EremVariant:
    """Return the fixed EREM signal previously validated and UI-tested."""
    return EremVariant(
        EREM_BASE_VARIANT_ID,
        btc_drawdown_quantile=0.35,
        use_btc_ema_filter=True,
    )


def build_hysteresis_variants() -> list[EremHysteresisVariant]:
    """Return a small, predeclared duration grid."""
    variants: list[EremHysteresisVariant] = []
    for min_exposed in (12, 24, 48, 72):
        for min_flat in (12, 24, 48, 72):
            variants.append(
                EremHysteresisVariant(
                    variant_id=f"erem_minhold_exp{min_exposed}_flat{min_flat}",
                    min_exposed_hours=min_exposed,
                    min_flat_hours=min_flat,
                )
            )
    return variants


def hysteresis_exposure_changes(
    execution: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    base_variant: EremVariant,
    thresholds: EremThresholds,
    overlay: EremHysteresisVariant,
) -> dict[pd.Timestamp, bool]:
    """Apply minimum exposed/flat durations to the fixed EREM changes."""
    raw_changes = _desired_exposure_changes(
        execution,
        start,
        end,
        base_variant,
        thresholds,
    )
    if not raw_changes:
        return {}
    filtered: dict[pd.Timestamp, bool] = {}
    exposed = False
    last_state_change: pd.Timestamp | None = None
    first = True
    for timestamp, desired_exposed in sorted(raw_changes.items()):
        if desired_exposed == exposed:
            continue
        if first:
            filtered[timestamp] = desired_exposed
            exposed = desired_exposed
            last_state_change = timestamp
            first = False
            continue
        if last_state_change is None:
            hours_in_state = float("inf")
        else:
            hours_in_state = (timestamp - last_state_change).total_seconds() / 3600.0
        required_hours = (
            overlay.min_exposed_hours if exposed else overlay.min_flat_hours
        )
        if hours_in_state < required_hours:
            continue
        filtered[timestamp] = desired_exposed
        exposed = desired_exposed
        last_state_change = timestamp
    return filtered


def simulate_erem_hysteresis(
    execution: pd.DataFrame,
    base_variant: EremVariant,
    thresholds: EremThresholds,
    overlay: EremHysteresisVariant,
    start: pd.Timestamp,
    end: pd.Timestamp,
    config: EremConfig,
) -> dict[str, Any]:
    """Simulate fixed EREM with a minimum-duration overlay."""
    frame = execution.loc[(execution.index >= start) & (execution.index <= end)]
    if len(frame) < 2:
        return {
            "erem_pnl_usdc": 0.0,
            "buy_hold_pnl_usdc": 0.0,
            "strategy_minus_buy_hold_usdc_per_day": 0.0,
            "erem_maxdd_usdc": 0.0,
            "buy_hold_maxdd_usdc": 0.0,
            "erem_maxdd_pct": 0.0,
            "buy_hold_maxdd_pct": 0.0,
            "time_in_market_pct": 0.0,
            "switch_count": 0,
            "avoided_loss_blocks": [],
            "top2_avoided_block_share": None,
        }
    changes = hysteresis_exposure_changes(
        execution,
        start,
        end,
        base_variant,
        thresholds,
        overlay,
    )
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
        "time_in_market_pct": float(exposed_periods / max(len(index) - 1, 1)),
        "switch_count": switch_count,
        "avoided_loss_blocks": avoided_blocks,
        "top2_avoided_block_share": _top_share(avoided_blocks, 2),
    }


def _aggregate_folds(folds: list[dict[str, Any]]) -> dict[str, Any]:
    if not folds:
        return {}
    days = float(sum(fold["days"] for fold in folds))
    erem_pnl = float(sum(fold["metrics"]["erem_pnl_usdc"] for fold in folds))
    buyhold_pnl = float(sum(fold["metrics"]["buy_hold_pnl_usdc"] for fold in folds))
    base_pnl = float(sum(fold["base_metrics"]["erem_pnl_usdc"] for fold in folds))
    base_switch_count = int(
        sum(fold["base_metrics"]["switch_count"] for fold in folds)
    )
    switch_count = int(sum(fold["metrics"]["switch_count"] for fold in folds))
    avoided_blocks = [
        value
        for fold in folds
        for value in fold["metrics"].get("avoided_loss_blocks", [])
    ]
    return {
        "days": days,
        "erem_pnl_usdc": erem_pnl,
        "base_erem_pnl_usdc": base_pnl,
        "buy_hold_pnl_usdc": buyhold_pnl,
        "erem_usdc_per_day": erem_pnl / max(days, 1.0),
        "base_erem_usdc_per_day": base_pnl / max(days, 1.0),
        "buy_hold_usdc_per_day": buyhold_pnl / max(days, 1.0),
        "strategy_minus_buy_hold_usdc_per_day": (
            (erem_pnl - buyhold_pnl) / max(days, 1.0)
        ),
        "strategy_minus_base_erem_usdc_per_day": (
            (erem_pnl - base_pnl) / max(days, 1.0)
        ),
        "positive_folds": int(
            sum(fold["metrics"]["erem_pnl_usdc"] > 0 for fold in folds)
        ),
        "beats_base_folds": int(
            sum(
                fold["metrics"]["erem_pnl_usdc"]
                > fold["base_metrics"]["erem_pnl_usdc"]
                for fold in folds
            )
        ),
        "switch_count": switch_count,
        "base_switch_count": base_switch_count,
        "switch_reduction_pct": (
            1.0 - switch_count / base_switch_count if base_switch_count > 0 else None
        ),
        "mean_erem_maxdd_pct": float(
            np.mean([fold["metrics"]["erem_maxdd_pct"] for fold in folds])
        ),
        "mean_base_erem_maxdd_pct": float(
            np.mean([fold["base_metrics"]["erem_maxdd_pct"] for fold in folds])
        ),
        "top2_avoided_block_share": _top_share(avoided_blocks, 2),
    }


def _rejection_reasons(
    aggregate: dict[str, Any],
    config: EremHysteresisConfig,
) -> list[str]:
    reasons: list[str] = []
    if aggregate["positive_folds"] < config.min_positive_folds:
        reasons.append("positive_folds_below_minimum")
    if aggregate["beats_base_folds"] < config.min_beats_base_folds:
        reasons.append("beats_base_folds_below_minimum")
    if (
        aggregate["strategy_minus_buy_hold_usdc_per_day"]
        <= config.min_strategy_minus_buyhold_usdc_per_day
    ):
        reasons.append("does_not_beat_buy_hold_per_day")
    switch_reduction = aggregate["switch_reduction_pct"]
    if switch_reduction is None or switch_reduction < config.min_switch_reduction_pct:
        reasons.append("switch_reduction_below_minimum")
    top2 = aggregate["top2_avoided_block_share"]
    if top2 is None or top2 > config.max_top2_avoided_block_share:
        reasons.append("top2_avoided_block_share_above_limit")
    return reasons


def evaluate_hysteresis_variant(
    execution: pd.DataFrame,
    overlay: EremHysteresisVariant,
    windows: list[dict[str, str]],
    training_start: pd.Timestamp,
    config: EremHysteresisConfig,
) -> dict[str, Any]:
    """Evaluate one hysteresis overlay on training-only folds."""
    base_variant = fixed_erem_variant()
    fold_reports: list[dict[str, Any]] = []
    for window in windows:
        train_end = pd.Timestamp(window["train_end"])
        validation_start = pd.Timestamp(window["validation_start"])
        validation_end = pd.Timestamp(window["validation_end"])
        thresholds = calibrate_erem_thresholds(
            execution,
            training_start,
            train_end,
            base_variant,
        )
        base_metrics = simulate_erem_exposure(
            execution,
            base_variant,
            thresholds,
            validation_start,
            validation_end,
            config.erem_config,
        )
        metrics = simulate_erem_hysteresis(
            execution,
            base_variant,
            thresholds,
            overlay,
            validation_start,
            validation_end,
            config.erem_config,
        )
        days = max((validation_end - validation_start).total_seconds() / 86400.0, 1.0)
        fold_reports.append(
            {
                **window,
                "thresholds": asdict(thresholds),
                "days": days,
                "metrics": metrics,
                "base_metrics": base_metrics,
            }
        )
    aggregate = _aggregate_folds(fold_reports)
    reasons = _rejection_reasons(aggregate, config)
    score = None
    if not reasons:
        score = (
            aggregate["strategy_minus_base_erem_usdc_per_day"]
            + (aggregate["switch_reduction_pct"] or 0.0) * 0.05
            - max(
                0.0,
                aggregate["mean_erem_maxdd_pct"]
                - aggregate["mean_base_erem_maxdd_pct"],
            )
        )
    return {
        "overlay": asdict(overlay),
        "folds": fold_reports,
        "aggregate": {
            **aggregate,
            "eligible_for_frozen_research_blindtest": not reasons,
            "rejection_reasons": reasons,
            "selection_score": score,
        },
    }


def run_erem_hysteresis_minhold_scan(
    config: EremHysteresisConfig | None = None,
) -> dict[str, Any]:
    """Run the training-only EREM min-hold/min-flat overlay scan."""
    active_config = config or EremHysteresisConfig()
    execution, training_start, blindtest_start, blindtest_end = _load_full_execution()
    execution = execution.loc[
        (execution.index >= training_start) & (execution.index < blindtest_start)
    ]
    windows = build_walkforward_windows(
        training_start,
        blindtest_start,
        active_config.erem_config,
    )
    variant_reports = [
        evaluate_hysteresis_variant(
            execution,
            overlay,
            windows,
            training_start,
            active_config,
        )
        for overlay in build_hysteresis_variants()
    ]
    passing = [
        report
        for report in variant_reports
        if report["aggregate"]["eligible_for_frozen_research_blindtest"]
    ]
    best = None
    if passing:
        best = max(
            passing,
            key=lambda report: (
                report["aggregate"]["selection_score"],
                report["aggregate"]["strategy_minus_base_erem_usdc_per_day"],
            ),
        )
    status = (
        "erem_hysteresis_training_candidate_found"
        if best is not None
        else "no_erem_hysteresis_training_candidate"
    )
    report: dict[str, Any] = {
        "strategy_version": EREM_HYSTERESIS_MINHOLD_VERSION,
        "depends_on_strategy_versions": [
            EREM_EXPOSURE_EDGE_VERSION,
            EREM_FROZEN_BLINDTEST_VERSION,
            EREM_POSTMORTEM_CYCLE_VERSION,
        ],
        "status": status,
        "research_only": True,
        "training_only": True,
        "runs_new_blindtest": False,
        "runs_ui_backtest": False,
        "searches_new_signal": False,
        "changes_router": False,
        "uses_blindtest_for_selection": False,
        "base_variant": asdict(fixed_erem_variant()),
        "config": {
            key: str(value) if isinstance(value, Path) else _to_jsonable(value)
            for key, value in asdict(active_config).items()
        },
        "data_range": {
            "training_start": training_start.isoformat(),
            "blindtest_start_not_used": blindtest_start.isoformat(),
            "blindtest_end_not_used": blindtest_end.isoformat(),
        },
        "variant_count": len(variant_reports),
        "passing_variant_count": len(passing),
        "best_training_only_variant": {
            "overlay": best["overlay"],
            "aggregate": best["aggregate"],
        }
        if best is not None
        else None,
        "variants": variant_reports,
        "decision_summary": {
            "frozen_research_blindtest_conditionally_allowed": best is not None,
            "ui_full_backtest_allowed_now": False,
            "router_integration_allowed_now": False,
            "recommended_next_step": (
                "Build exactly one frozen research blindtest for the selected "
                "EREM hysteresis overlay; no UI/full and no router integration yet."
                if best is not None
                else (
                    "Do not tune EREM further. Move to a distinct profit-alpha "
                    "existence scan such as BTC->ETH lead-lag or OIA."
                )
            ),
        },
    }
    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "erem_hysteresis_minhold_scan_report.json"
    report["output_paths"] = {"report": str(report_path)}
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=_to_jsonable) + "\n",
        encoding="utf-8",
    )
    return report
