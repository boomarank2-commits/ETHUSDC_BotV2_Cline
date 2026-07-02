"""Frozen research blindtest for the selected EREM exposure candidate.

This module runs exactly one frozen blindtest for the candidate selected by the
training-only EREM exposure edge check. It does not search variants, does not
change parameters, does not touch the UI/router and does not learn from the
blindtest.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.common.paths import REPORTS_DIR
from src.research.brh_selection_edge_robustness_v2check import _safe_float
from src.research.brh_v1 import _load_full_execution, _to_jsonable
from src.research.brh_v1_diagnostics import _read_json
from src.research.erem_exposure_edge_check import (
    EREM_EXPOSURE_EDGE_VERSION,
    EremConfig,
    EremVariant,
    build_erem_variants,
    calibrate_erem_thresholds,
    simulate_erem_exposure,
)

EREM_FROZEN_BLINDTEST_VERSION = "erem_frozen_blindtest_20260702"


@dataclass(frozen=True)
class EremFrozenBlindtestConfig:
    """Configuration for the one-candidate EREM frozen research blindtest."""

    source_report_path: Path = (
        REPORTS_DIR
        / "research"
        / "erem_exposure_edge_check"
        / "erem_exposure_edge_check_report.json"
    )
    output_dir: Path = REPORTS_DIR / "research" / "erem_frozen_blindtest"
    max_top1_avoided_block_share: float = 0.50


def _variant_by_id(variant_id: str) -> EremVariant:
    for variant in build_erem_variants():
        if variant.variant_id == variant_id:
            return variant
    msg = f"unknown EREM variant id: {variant_id}"
    raise ValueError(msg)


def _gatekeeper_candidate(report: dict[str, Any]) -> EremVariant:
    if report.get("status") != "erem_training_edge_found":
        msg = "EREM training-only check did not find an eligible candidate"
        raise ValueError(msg)
    if not (report.get("decision_summary") or {}).get(
        "erem_frozen_blindtest_conditionally_allowed"
    ):
        msg = "EREM training-only check did not authorize a frozen blindtest"
        raise ValueError(msg)
    best = report.get("best_training_only_variant")
    if not best:
        msg = "EREM training-only report has no best candidate"
        raise ValueError(msg)
    return _variant_by_id(best["variant_id"])


def _return_to_maxdd_ratio(pnl_usdc: float | None, maxdd_usdc: float | None) -> float | None:
    if pnl_usdc is None or maxdd_usdc is None or maxdd_usdc <= 0:
        return None
    return pnl_usdc / maxdd_usdc


def _decision_summary(
    metrics: dict[str, Any],
    config: EremFrozenBlindtestConfig,
) -> dict[str, Any]:
    erem_pnl = _safe_float(metrics.get("erem_pnl_usdc"))
    buyhold_pnl = _safe_float(metrics.get("buy_hold_pnl_usdc"))
    erem_maxdd = _safe_float(metrics.get("erem_maxdd_usdc"))
    buyhold_maxdd = _safe_float(metrics.get("buy_hold_maxdd_usdc"))
    top1 = _safe_float(metrics.get("top1_avoided_block_share"))
    erem_ratio = _return_to_maxdd_ratio(erem_pnl, erem_maxdd)
    buyhold_ratio = _return_to_maxdd_ratio(buyhold_pnl, buyhold_maxdd)
    return_not_worse = (
        erem_pnl is not None and buyhold_pnl is not None and erem_pnl >= buyhold_pnl
    )
    drawdown_better = (
        erem_maxdd is not None
        and buyhold_maxdd is not None
        and erem_maxdd < buyhold_maxdd
    )
    concentration_ok = top1 is not None and top1 <= config.max_top1_avoided_block_share
    ratio_better = (
        erem_ratio is not None
        and buyhold_ratio is not None
        and erem_ratio > buyhold_ratio
    )
    robust_blindtest_edge = (
        return_not_worse and drawdown_better and concentration_ok and ratio_better
    )
    if robust_blindtest_edge:
        recommendation = (
            "Do not UI-backtest yet. The EREM research blindtest is robust enough "
            "to justify a separate minimal router-integration patch, followed by "
            "one UI full-backtest through the shared activity_first_router path."
        )
    else:
        recommendation = (
            "Do not integrate and do not UI-backtest. EREM did not confirm a robust "
            "drawdown-avoidance edge in the frozen blindtest."
        )
    return {
        "return_not_worse_than_buy_hold": return_not_worse,
        "drawdown_better_than_buy_hold": drawdown_better,
        "top1_avoided_block_concentration_ok": concentration_ok,
        "return_to_maxdd_ratio_better_than_buy_hold": ratio_better,
        "erem_return_to_maxdd_ratio": erem_ratio,
        "buy_hold_return_to_maxdd_ratio": buyhold_ratio,
        "robust_blindtest_edge": robust_blindtest_edge,
        "router_integration_allowed_now": robust_blindtest_edge,
        "ui_full_backtest_allowed_now": False,
        "recommended_next_step": recommendation,
    }


def run_erem_frozen_blindtest(
    config: EremFrozenBlindtestConfig | None = None,
) -> dict[str, Any]:
    """Run exactly one frozen EREM research blindtest."""
    active_config = config or EremFrozenBlindtestConfig()
    source_report = _read_json(active_config.source_report_path)
    variant = _gatekeeper_candidate(source_report)
    execution, training_start, blindtest_start, blindtest_end = _load_full_execution()
    erem_config = EremConfig()
    thresholds = calibrate_erem_thresholds(
        execution,
        training_start,
        blindtest_start - pd.Timedelta(hours=1),
        variant,
    )
    metrics = simulate_erem_exposure(
        execution,
        variant,
        thresholds,
        blindtest_start,
        blindtest_end,
        erem_config,
    )
    report: dict[str, Any] = {
        "strategy_version": EREM_FROZEN_BLINDTEST_VERSION,
        "depends_on_strategy_versions": [EREM_EXPOSURE_EDGE_VERSION],
        "status": "erem_frozen_blindtest_completed",
        "research_only": True,
        "runs_new_blindtest": True,
        "runs_ui_backtest": False,
        "searches_variants": False,
        "changes_strategy_parameters": False,
        "uses_blindtest_for_selection": False,
        "candidate_variant": asdict(variant),
        "candidate_source": {
            "source_report_path": str(active_config.source_report_path),
            "training_only_best_variant": source_report.get("best_training_only_variant"),
        },
        "lookahead_safety_notes": [
            "Candidate was selected by the prior training-only EREM edge check.",
            "Thresholds are calibrated on training_start through blindtest_start - 1h.",
            "Blindtest is evaluated exactly once for this fixed candidate.",
            "No parameters or variants are selected using blindtest results.",
        ],
        "data_range": {
            "training_start": training_start.isoformat(),
            "blindtest_start": blindtest_start.isoformat(),
            "blindtest_end": blindtest_end.isoformat(),
        },
        "candidate_thresholds": asdict(thresholds),
        "blindtest_metrics": metrics,
        "decision_summary": _decision_summary(metrics, active_config),
    }
    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "erem_frozen_blindtest_report.json"
    report["output_paths"] = {"report": str(report_path)}
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=_to_jsonable) + "\n",
        encoding="utf-8",
    )
    return report
