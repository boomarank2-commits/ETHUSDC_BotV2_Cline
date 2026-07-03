"""Frozen research blindtest for one EREM hysteresis/minhold candidate."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.common.paths import REPORTS_DIR
from src.research.brh_v1 import _load_full_execution, _to_jsonable
from src.research.brh_v1_diagnostics import _read_json
from src.research.erem_exposure_edge_check import (
    EremConfig,
    calibrate_erem_thresholds,
    simulate_erem_exposure,
)
from src.research.erem_hysteresis_minhold_scan import (
    EREM_HYSTERESIS_MINHOLD_VERSION,
    EremHysteresisVariant,
    fixed_erem_variant,
    simulate_erem_hysteresis,
)

EREM_HYSTERESIS_FROZEN_VERSION = "erem_hysteresis_frozen_blindtest_20260703"


@dataclass(frozen=True)
class EremHysteresisFrozenConfig:
    """Configuration for the one-candidate frozen research blindtest."""

    source_report_path: Path = (
        REPORTS_DIR
        / "research"
        / "erem_hysteresis_minhold_scan"
        / "erem_hysteresis_minhold_scan_report.json"
    )
    output_dir: Path = REPORTS_DIR / "research" / "erem_hysteresis_frozen_blindtest"
    max_top2_avoided_block_share: float = 0.65


def _overlay_from_report(report: dict[str, Any]) -> EremHysteresisVariant:
    if report.get("status") != "erem_hysteresis_training_candidate_found":
        msg = "EREM hysteresis training-only scan did not find a candidate"
        raise ValueError(msg)
    if not (report.get("decision_summary") or {}).get(
        "frozen_research_blindtest_conditionally_allowed"
    ):
        msg = "EREM hysteresis training-only scan did not authorize frozen blindtest"
        raise ValueError(msg)
    best = report.get("best_training_only_variant")
    if not best:
        msg = "EREM hysteresis report has no best candidate"
        raise ValueError(msg)
    overlay = best["overlay"]
    return EremHysteresisVariant(
        variant_id=str(overlay["variant_id"]),
        min_exposed_hours=int(overlay["min_exposed_hours"]),
        min_flat_hours=int(overlay["min_flat_hours"]),
    )


def _decision_summary(
    hysteresis_metrics: dict[str, Any],
    base_metrics: dict[str, Any],
    config: EremHysteresisFrozenConfig,
) -> dict[str, Any]:
    pnl = float(hysteresis_metrics["erem_pnl_usdc"])
    base_pnl = float(base_metrics["erem_pnl_usdc"])
    switch_count = int(hysteresis_metrics["switch_count"])
    base_switch_count = int(base_metrics["switch_count"])
    top2 = hysteresis_metrics.get("top2_avoided_block_share")
    switch_reduction = (
        1.0 - switch_count / base_switch_count if base_switch_count > 0 else None
    )
    positive = pnl > 0
    beats_base = pnl > base_pnl
    switch_reduced = switch_reduction is not None and switch_reduction > 0
    concentration_ok = top2 is not None and top2 <= config.max_top2_avoided_block_share
    robust_edge = positive and beats_base and switch_reduced and concentration_ok
    return {
        "positive_blindtest_pnl": positive,
        "beats_base_erem": beats_base,
        "switch_count_reduced": switch_reduced,
        "top2_avoided_block_concentration_ok": concentration_ok,
        "switch_reduction_pct": switch_reduction,
        "hysteresis_minus_base_pnl_usdc": pnl - base_pnl,
        "robust_frozen_edge": robust_edge,
        "router_integration_allowed_now": robust_edge,
        "ui_full_backtest_allowed_now": False,
        "recommended_next_step": (
            "Build a minimal router integration for this fixed hysteresis overlay, "
            "then run one UI/full backtest through the shared path."
            if robust_edge
            else (
                "Do not integrate. The frozen blindtest did not prove the "
                "hysteresis overlay improves EREM out-of-sample."
            )
        ),
    }


def run_erem_hysteresis_frozen_blindtest(
    config: EremHysteresisFrozenConfig | None = None,
) -> dict[str, Any]:
    """Run exactly one frozen blindtest for the selected hysteresis overlay."""
    active_config = config or EremHysteresisFrozenConfig()
    source_report = _read_json(active_config.source_report_path)
    overlay = _overlay_from_report(source_report)
    execution, training_start, blindtest_start, blindtest_end = _load_full_execution()
    base_variant = fixed_erem_variant()
    erem_config = EremConfig()
    thresholds = calibrate_erem_thresholds(
        execution,
        training_start,
        blindtest_start - pd.Timedelta(hours=1),
        base_variant,
    )
    base_metrics = simulate_erem_exposure(
        execution,
        base_variant,
        thresholds,
        blindtest_start,
        blindtest_end,
        erem_config,
    )
    hysteresis_metrics = simulate_erem_hysteresis(
        execution,
        base_variant,
        thresholds,
        overlay,
        blindtest_start,
        blindtest_end,
        erem_config,
    )
    report: dict[str, Any] = {
        "strategy_version": EREM_HYSTERESIS_FROZEN_VERSION,
        "depends_on_strategy_versions": [EREM_HYSTERESIS_MINHOLD_VERSION],
        "status": "erem_hysteresis_frozen_blindtest_completed",
        "research_only": True,
        "runs_new_blindtest": True,
        "runs_ui_backtest": False,
        "searches_variants": False,
        "changes_strategy_parameters": False,
        "uses_blindtest_for_selection": False,
        "base_variant": asdict(base_variant),
        "candidate_overlay": asdict(overlay),
        "candidate_source": {
            "source_report_path": str(active_config.source_report_path),
            "training_only_best_variant": source_report.get(
                "best_training_only_variant"
            ),
        },
        "data_range": {
            "training_start": training_start.isoformat(),
            "blindtest_start": blindtest_start.isoformat(),
            "blindtest_end": blindtest_end.isoformat(),
        },
        "thresholds_calibrated_on_training_only": asdict(thresholds),
        "base_erem_blindtest_metrics": base_metrics,
        "hysteresis_blindtest_metrics": hysteresis_metrics,
        "decision_summary": _decision_summary(
            hysteresis_metrics,
            base_metrics,
            active_config,
        ),
        "lookahead_safety_notes": [
            "Candidate overlay was selected by the prior training-only scan.",
            "Thresholds are calibrated on training_start through blindtest_start - 1h.",
            "Blindtest is evaluated exactly once for this fixed overlay.",
            "No parameters or variants are selected using blindtest results.",
        ],
    }
    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "erem_hysteresis_frozen_blindtest_report.json"
    report["output_paths"] = {"report": str(report_path)}
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=_to_jsonable) + "\n",
        encoding="utf-8",
    )
    return report
