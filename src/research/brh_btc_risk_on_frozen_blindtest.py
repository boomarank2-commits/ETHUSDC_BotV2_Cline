"""Frozen research blindtest for the BRH broad BTC-risk-on candidate.

This module consumes the strict training-only gatekeeper result and, only when
that gatekeeper selected the never-blindtested broad variant
``brh_btc_risk_on_72h``, runs exactly one frozen research blindtest.

It does not search variants, does not change parameters, does not touch the
router and does not run the UI full backtest.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.common.paths import REPORTS_DIR
from src.research.brh_selection_edge_robustness_v2check import (
    BRH_SELECTION_EDGE_ROBUSTNESS_VERSION,
    RISK_ON_BASELINE_VARIANT_ID,
    _safe_float,
)
from src.research.brh_v1 import (
    BRH_V1_VERSION,
    BrhConfig,
    BrhTrade,
    BrhVariant,
    _load_full_execution,
    _summary_dict,
    _to_jsonable,
    calibrate_brh_thresholds,
    simulate_brh_variant,
    summarize_brh_trades,
)
from src.research.brh_v1_diagnostics import (
    _full_period_buy_hold,
    _read_json,
    concentration_metrics,
)

BRH_BTC_RISK_ON_FROZEN_BLINDTEST_VERSION = (
    "brh_btc_risk_on_72h_frozen_blindtest_20260702"
)


@dataclass(frozen=True)
class BrhBtcRiskOnFrozenBlindtestConfig:
    """Configuration for the one-candidate frozen research blindtest."""

    gatekeeper_report_path: Path = (
        REPORTS_DIR
        / "research"
        / "brh_selection_edge_robustness_v2check"
        / "brh_selection_edge_robustness_v2check_report.json"
    )
    output_dir: Path = REPORTS_DIR / "research" / "brh_btc_risk_on_frozen_blindtest"
    candidate_variant_id: str = RISK_ON_BASELINE_VARIANT_ID


def _trade_frame(trades: list[BrhTrade]) -> pd.DataFrame:
    return pd.DataFrame([asdict(trade) for trade in trades])


def _monthly_pnl(trades: list[BrhTrade]) -> list[dict[str, Any]]:
    if not trades:
        return []
    frame = _trade_frame(trades)
    frame["exit_time"] = pd.to_datetime(frame["exit_time"], utc=True)
    frame["month"] = frame["exit_time"].dt.strftime("%Y-%m")
    grouped = frame.groupby("month", sort=True)["net_pnl_usdc"].agg(["sum", "count"])
    return [
        {
            "month": str(index),
            "pnl_usdc": float(row["sum"]),
            "trade_count": int(row["count"]),
        }
        for index, row in grouped.iterrows()
    ]


def _daily_pnl(trades: list[BrhTrade]) -> dict[str, Any]:
    if not trades:
        return {
            "positive_days": 0,
            "negative_days": 0,
            "neutral_days": 0,
            "best_day_pnl_usdc": 0.0,
            "worst_day_pnl_usdc": 0.0,
        }
    frame = _trade_frame(trades)
    frame["exit_time"] = pd.to_datetime(frame["exit_time"], utc=True)
    frame["day"] = frame["exit_time"].dt.date.astype(str)
    by_day = frame.groupby("day", sort=True)["net_pnl_usdc"].sum()
    return {
        "positive_days": int((by_day > 0).sum()),
        "negative_days": int((by_day < 0).sum()),
        "neutral_days": int((by_day == 0).sum()),
        "best_day_pnl_usdc": float(by_day.max()),
        "worst_day_pnl_usdc": float(by_day.min()),
    }


def _gatekeeper_candidate(report: dict[str, Any], expected_variant_id: str) -> dict[str, Any]:
    if report.get("status") != "new_training_only_candidate_found":
        msg = "gatekeeper did not authorize a new training-only candidate"
        raise ValueError(msg)
    if not (report.get("decision_summary") or {}).get(
        "research_blindtest_conditionally_allowed"
    ):
        msg = "gatekeeper did not conditionally allow a research blindtest"
        raise ValueError(msg)
    best = report.get("best_training_only_variant_after_robustness_gatekeeper")
    if not best:
        msg = "gatekeeper report has no best candidate"
        raise ValueError(msg)
    if best.get("variant_id") != expected_variant_id:
        msg = (
            "gatekeeper selected a different candidate: "
            f"{best.get('variant_id')} != {expected_variant_id}"
        )
        raise ValueError(msg)
    if best.get("already_blindtested_in_v1"):
        msg = "gatekeeper candidate was already blindtested in v1"
        raise ValueError(msg)
    return best


def _decision_summary(
    blindtest_summary: dict[str, Any],
    concentration: dict[str, Any],
    strategy_minus_buy_hold_usdc_per_day: float | None,
) -> dict[str, Any]:
    pnl = _safe_float(blindtest_summary.get("pnl_usdc")) or 0.0
    usdc_per_day = _safe_float(blindtest_summary.get("usdc_per_day")) or 0.0
    trades = int(blindtest_summary.get("trades") or 0)
    median = _safe_float(blindtest_summary.get("median_trade_net_pnl"))
    leave_two = _safe_float(concentration.get("leave_two_out_profit_factor"))
    top2 = _safe_float((concentration.get("top_trade_pnl_share") or {}).get("2"))
    positive_blindtest_edge = pnl > 0 and usdc_per_day > 0 and trades > 0
    robust_blindtest_edge = (
        positive_blindtest_edge
        and median is not None
        and median > 0
        and leave_two is not None
        and leave_two >= 1.10
        and top2 is not None
        and top2 <= 0.60
        and strategy_minus_buy_hold_usdc_per_day is not None
        and strategy_minus_buy_hold_usdc_per_day > 0
    )
    if robust_blindtest_edge:
        recommendation = (
            "Do not run UI full yet. This research blindtest is positive enough "
            "to justify a separate patch that prepares minimal router integration "
            "for this exact candidate, then one UI full-backtest through the shared "
            "activity_first_router path."
        )
    elif positive_blindtest_edge:
        recommendation = (
            "Do not integrate yet. The candidate is positive but not robust enough "
            "by the research-blindtest robustness checks."
        )
    else:
        recommendation = (
            "Do not integrate and do not UI-backtest. The frozen research blindtest "
            "did not confirm the training-only candidate."
        )
    return {
        "positive_blindtest_edge": positive_blindtest_edge,
        "robust_blindtest_edge": robust_blindtest_edge,
        "ui_full_backtest_allowed_now": False,
        "router_integration_allowed_now": robust_blindtest_edge,
        "recommended_next_step": recommendation,
    }


def run_brh_btc_risk_on_frozen_blindtest(
    config: BrhBtcRiskOnFrozenBlindtestConfig | None = None,
) -> dict[str, Any]:
    """Run exactly one frozen research blindtest for the gatekeeper candidate."""
    active_config = config or BrhBtcRiskOnFrozenBlindtestConfig()
    gatekeeper_report = _read_json(active_config.gatekeeper_report_path)
    gatekeeper_candidate = _gatekeeper_candidate(
        gatekeeper_report,
        active_config.candidate_variant_id,
    )
    execution, training_start, blindtest_start, blindtest_end = _load_full_execution()
    brh_config = BrhConfig()
    variant = BrhVariant(active_config.candidate_variant_id)
    thresholds = calibrate_brh_thresholds(
        execution,
        training_start,
        blindtest_start - pd.Timedelta(hours=1),
    )
    blindtest_trades = simulate_brh_variant(
        execution,
        variant,
        thresholds,
        brh_config,
        blindtest_start,
        blindtest_end,
    )
    blindtest_summary = _summary_dict(
        summarize_brh_trades(
            blindtest_trades,
            blindtest_start,
            blindtest_end,
            brh_config.position_size_usdc,
        )
    )
    blindtest_trade_frame = _trade_frame(blindtest_trades)
    blindtest_concentration = concentration_metrics(blindtest_trade_frame)
    buy_hold = _full_period_buy_hold(execution, blindtest_start, blindtest_end, brh_config)
    blindtest_days = max((blindtest_end - blindtest_start).total_seconds() / 86400.0, 1.0)
    buy_hold_pnl = _safe_float(buy_hold.get("pnl_usdc"))
    buy_hold_usdc_per_day = (
        buy_hold_pnl / blindtest_days if buy_hold_pnl is not None else None
    )
    strategy_usdc_per_day = _safe_float(blindtest_summary.get("usdc_per_day"))
    strategy_minus_buy_hold_usdc_per_day = (
        strategy_usdc_per_day - buy_hold_usdc_per_day
        if strategy_usdc_per_day is not None and buy_hold_usdc_per_day is not None
        else None
    )
    decision = _decision_summary(
        blindtest_summary,
        blindtest_concentration,
        strategy_minus_buy_hold_usdc_per_day,
    )
    report: dict[str, Any] = {
        "strategy_version": BRH_BTC_RISK_ON_FROZEN_BLINDTEST_VERSION,
        "depends_on_strategy_versions": [
            BRH_V1_VERSION,
            BRH_SELECTION_EDGE_ROBUSTNESS_VERSION,
        ],
        "status": "frozen_research_blindtest_completed",
        "research_only": True,
        "runs_new_blindtest": True,
        "runs_ui_backtest": False,
        "changes_strategy_parameters": False,
        "searches_variants": False,
        "uses_blindtest_for_selection": False,
        "candidate_variant_id": active_config.candidate_variant_id,
        "candidate_source": {
            "gatekeeper_report_path": str(active_config.gatekeeper_report_path),
            "gatekeeper_candidate": gatekeeper_candidate,
        },
        "lookahead_safety_notes": [
            "Candidate was selected by the prior training-only gatekeeper.",
            "This runner verifies the gatekeeper selected exactly brh_btc_risk_on_72h.",
            "Thresholds are calibrated on training_start through blindtest_start - 1h.",
            "Blindtest is evaluated exactly once for this fixed candidate.",
            "No variants or parameters are selected using blindtest results.",
        ],
        "data_range": {
            "training_start": training_start.isoformat(),
            "blindtest_start": blindtest_start.isoformat(),
            "blindtest_end": blindtest_end.isoformat(),
            "blindtest_days": blindtest_days,
        },
        "candidate_thresholds": asdict(thresholds),
        "blindtest_summary": blindtest_summary,
        "blindtest_concentration": blindtest_concentration,
        "blindtest_daily_pnl": _daily_pnl(blindtest_trades),
        "blindtest_monthly_pnl": _monthly_pnl(blindtest_trades),
        "blindtest_buy_hold_baseline": {
            **buy_hold,
            "usdc_per_day": buy_hold_usdc_per_day,
            "strategy_minus_buy_hold_usdc_per_day": strategy_minus_buy_hold_usdc_per_day,
        },
        "blindtest_trades": [asdict(trade) for trade in blindtest_trades],
        "decision_summary": decision,
    }
    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "brh_btc_risk_on_frozen_blindtest_report.json"
    trades_path = active_config.output_dir / "brh_btc_risk_on_frozen_blindtest_trades.csv"
    report["output_paths"] = {
        "report": str(report_path),
        "trades": str(trades_path),
    }
    pd.DataFrame(report["blindtest_trades"]).to_csv(trades_path, index=False)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=_to_jsonable) + "\n",
        encoding="utf-8",
    )
    return report
