"""EREM post-mortem diagnostics after the first real UI full backtest.

This module deliberately does not search a new strategy.  It answers two
smaller forensic questions raised after the real EREM UI run:

1. How much of EREM's loss comes from switching costs / churn?
2. Does EREM beat ETH buy-and-hold risk-adjusted over the whole available
   cycle, not just the final 365-day bear blindtest?

The scan is research-only.  It does not run a new blindtest, does not alter the
router, does not select variants and must not be used as a live/paper signal.
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
from src.research.erem_exposure_edge_check import (
    EREM_EXPOSURE_EDGE_VERSION,
    EremConfig,
    EremThresholds,
    EremVariant,
    _desired_exposure_changes,
    _max_drawdown_from_curve,
    calibrate_erem_thresholds,
    simulate_erem_exposure,
)
from src.research.erem_frozen_blindtest import EREM_FROZEN_BLINDTEST_VERSION

EREM_POSTMORTEM_CYCLE_VERSION = "erem_postmortem_cycle_scan_20260703"
EREM_FIXED_VARIANT_ID = "erem_btc_drawdown_q35_or_ema_below0"


@dataclass(frozen=True)
class EremPostmortemConfig:
    """Configuration for EREM post-mortem diagnostics."""

    output_dir: Path = REPORTS_DIR / "research" / "erem_postmortem_cycle_scan"
    position_size_usdc: float = 100.0
    fee_rate_per_side: float = 0.0010
    slippage_rate_per_side: float = 0.0001
    phase_lookback_hours: int = 24 * 30
    bull_return_threshold: float = 0.10
    bear_return_threshold: float = -0.10
    min_bull_participation: float = 0.60
    min_bear_loss_avoidance: float = 0.40
    max_erem_to_buyhold_drawdown_ratio: float = 0.60
    max_switch_cost_share_of_bull_positive_pnl: float = 0.20
    switch_cost_problem_share_of_loss: float = 0.40
    switch_cost_problem_share_of_bull_positive_pnl: float = 0.50

    @property
    def erem_config(self) -> EremConfig:
        return EremConfig(
            position_size_usdc=self.position_size_usdc,
            fee_rate_per_side=self.fee_rate_per_side,
            slippage_rate_per_side=self.slippage_rate_per_side,
        )

    @property
    def zero_cost_erem_config(self) -> EremConfig:
        return EremConfig(
            position_size_usdc=self.position_size_usdc,
            fee_rate_per_side=0.0,
            slippage_rate_per_side=0.0,
        )


def fixed_erem_variant() -> EremVariant:
    """Return the single already-tested EREM variant."""
    return EremVariant(
        EREM_FIXED_VARIANT_ID,
        btc_drawdown_quantile=0.35,
        use_btc_ema_filter=True,
    )


def _price_series(frame: pd.DataFrame) -> pd.Series:
    if "close" in frame.columns:
        return frame["close"].astype(float)
    return frame["open"].astype(float)


def classify_market_phases(
    execution: pd.DataFrame,
    config: EremPostmortemConfig,
) -> pd.Series:
    """Classify each closed 1h row as bull, bear, chop or warmup."""
    prices = _price_series(execution)
    returns = prices / prices.shift(config.phase_lookback_hours) - 1.0
    phases = pd.Series("chop", index=execution.index, dtype="object")
    phases.loc[returns.isna()] = "warmup"
    phases.loc[returns >= config.bull_return_threshold] = "bull"
    phases.loc[returns <= config.bear_return_threshold] = "bear"
    return phases


def build_erem_equity_curve(
    execution: pd.DataFrame,
    variant: EremVariant,
    thresholds: EremThresholds,
    start: pd.Timestamp,
    end: pd.Timestamp,
    config: EremConfig,
) -> pd.DataFrame:
    """Build an hourly EREM-vs-buyhold curve using the existing EREM logic."""
    frame = execution.loc[(execution.index >= start) & (execution.index <= end)]
    columns = [
        "end_time",
        "erem_equity",
        "buy_hold_equity",
        "erem_delta_usdc",
        "buy_hold_delta_usdc",
        "eth_return",
        "exposed",
        "switch_cost_usdc",
    ]
    if len(frame) < 2:
        return pd.DataFrame(columns=columns)

    changes = _desired_exposure_changes(execution, start, end, variant, thresholds)
    opens = frame["open"].astype(float)
    index = list(frame.index)
    one_way_cost = config.one_way_cost_ret
    erem_equity = config.position_size_usdc
    buyhold_equity = config.position_size_usdc * (1.0 - one_way_cost)
    exposed = False
    rows: list[dict[str, Any]] = []

    for pos in range(len(index) - 1):
        now = index[pos]
        current_open = float(opens.iloc[pos])
        next_open = float(opens.iloc[pos + 1])
        interval_switch_cost = 0.0
        erem_before = erem_equity
        buyhold_before = buyhold_equity

        if now in changes and changes[now] != exposed:
            interval_switch_cost = erem_equity * one_way_cost
            erem_equity -= interval_switch_cost
            exposed = changes[now]

        if exposed:
            erem_equity *= next_open / current_open
        buyhold_equity *= next_open / current_open

        rows.append(
            {
                "start_time": now,
                "end_time": index[pos + 1],
                "erem_equity": erem_equity,
                "buy_hold_equity": buyhold_equity,
                "erem_delta_usdc": erem_equity - erem_before,
                "buy_hold_delta_usdc": buyhold_equity - buyhold_before,
                "eth_return": next_open / current_open - 1.0,
                "exposed": exposed,
                "switch_cost_usdc": interval_switch_cost,
            }
        )

    final_time = index[-1]
    if exposed:
        final_cost = erem_equity * one_way_cost
        erem_equity -= final_cost
        rows.append(
            {
                "start_time": final_time,
                "end_time": final_time,
                "erem_equity": erem_equity,
                "buy_hold_equity": buyhold_equity,
                "erem_delta_usdc": -final_cost,
                "buy_hold_delta_usdc": 0.0,
                "eth_return": 0.0,
                "exposed": exposed,
                "switch_cost_usdc": final_cost,
            }
        )

    final_buyhold_cost = buyhold_equity * one_way_cost
    buyhold_equity -= final_buyhold_cost
    rows.append(
        {
            "start_time": final_time,
            "end_time": final_time,
            "erem_equity": erem_equity,
            "buy_hold_equity": buyhold_equity,
            "erem_delta_usdc": 0.0,
            "buy_hold_delta_usdc": -final_buyhold_cost,
            "eth_return": 0.0,
            "exposed": exposed,
            "switch_cost_usdc": 0.0,
        }
    )
    return pd.DataFrame(rows).set_index("start_time")


def flat_period_attribution(
    execution: pd.DataFrame,
    variant: EremVariant,
    thresholds: EremThresholds,
    start: pd.Timestamp,
    end: pd.Timestamp,
    position_size_usdc: float,
) -> dict[str, Any]:
    """Attribute out-of-market windows to avoided losses or missed gains."""
    frame = execution.loc[(execution.index >= start) & (execution.index <= end)]
    if len(frame) < 2:
        return {
            "flat_block_count": 0,
            "avoided_losses_usdc": 0.0,
            "missed_gains_usdc": 0.0,
            "flat_blocks": [],
        }
    changes = _desired_exposure_changes(execution, start, end, variant, thresholds)
    opens = frame["open"].astype(float)
    index = list(frame.index)
    exposed = False
    flat_start_time: pd.Timestamp | None = index[0]
    flat_start_price: float | None = float(opens.iloc[0])
    flat_blocks: list[dict[str, Any]] = []

    def close_flat(end_time: pd.Timestamp, end_price: float) -> None:
        nonlocal flat_start_time, flat_start_price
        if flat_start_time is None or flat_start_price is None or flat_start_price <= 0:
            return
        price_return = end_price / flat_start_price - 1.0
        missed_gain = max(0.0, price_return) * position_size_usdc
        avoided_loss = max(0.0, -price_return) * position_size_usdc
        flat_blocks.append(
            {
                "start": flat_start_time.isoformat(),
                "end": end_time.isoformat(),
                "start_price": flat_start_price,
                "end_price": end_price,
                "price_return": price_return,
                "missed_gain_usdc": missed_gain,
                "avoided_loss_usdc": avoided_loss,
            }
        )
        flat_start_time = None
        flat_start_price = None

    for pos, now in enumerate(index):
        current_open = float(opens.iloc[pos])
        if now in changes and changes[now] != exposed:
            if changes[now]:
                close_flat(now, current_open)
            else:
                flat_start_time = now
                flat_start_price = current_open
            exposed = changes[now]

    if not exposed:
        close_flat(index[-1], float(opens.iloc[-1]))

    return {
        "flat_block_count": len(flat_blocks),
        "avoided_losses_usdc": float(
            sum(block["avoided_loss_usdc"] for block in flat_blocks)
        ),
        "missed_gains_usdc": float(
            sum(block["missed_gain_usdc"] for block in flat_blocks)
        ),
        "flat_blocks": flat_blocks,
    }


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _annualized_return(final_equity: float, initial_equity: float, days: float) -> float:
    if final_equity <= 0 or initial_equity <= 0 or days <= 0:
        return math.nan
    return (final_equity / initial_equity) ** (365.0 / days) - 1.0


def _annualized_sharpe(equity_values: list[float]) -> float | None:
    if len(equity_values) < 3:
        return None
    returns = pd.Series(equity_values).pct_change().replace([np.inf, -np.inf], np.nan)
    returns = returns.dropna()
    if len(returns) < 2:
        return None
    std = float(returns.std(ddof=1))
    if std <= 0:
        return None
    return float(returns.mean() / std * math.sqrt(24 * 365))


def _curve_metrics(curve: pd.DataFrame, column: str, start_capital: float, days: float):
    values = [start_capital, *[float(value) for value in curve[column].dropna()]]
    final_equity = values[-1] if values else start_capital
    maxdd_usdc, maxdd_pct = _max_drawdown_from_curve(values)
    annual_return = _annualized_return(final_equity, start_capital, days)
    return {
        "final_equity": float(final_equity),
        "pnl_usdc": float(final_equity - start_capital),
        "annualized_return": float(annual_return),
        "maxdd_usdc": float(maxdd_usdc),
        "maxdd_pct": float(maxdd_pct),
        "calmar": (
            float(annual_return / maxdd_pct)
            if maxdd_pct and maxdd_pct > 0 and not math.isnan(annual_return)
            else None
        ),
        "sharpe": _annualized_sharpe(values),
    }


def phase_participation_summary(
    execution: pd.DataFrame,
    curve: pd.DataFrame,
    config: EremPostmortemConfig,
) -> dict[str, Any]:
    """Summarize EREM and buy-and-hold PnL by 30d market phase."""
    if curve.empty:
        return {}
    phases = classify_market_phases(execution, config)
    curve = curve.copy()
    curve["phase"] = phases.reindex(curve.index).fillna("warmup")
    result: dict[str, Any] = {}
    for phase in ("bull", "bear", "chop", "warmup"):
        rows = curve[curve["phase"] == phase]
        erem_pnl = float(rows["erem_delta_usdc"].sum()) if not rows.empty else 0.0
        buyhold_pnl = (
            float(rows["buy_hold_delta_usdc"].sum()) if not rows.empty else 0.0
        )
        buyhold_positive_pnl = (
            float(rows.loc[rows["buy_hold_delta_usdc"] > 0, "buy_hold_delta_usdc"].sum())
            if not rows.empty
            else 0.0
        )
        result[phase] = {
            "hours": int(len(rows)),
            "exposed_hours": int(rows["exposed"].sum()) if not rows.empty else 0,
            "erem_pnl_usdc": erem_pnl,
            "buy_hold_pnl_usdc": buyhold_pnl,
            "buy_hold_positive_pnl_usdc": buyhold_positive_pnl,
            "erem_participation_vs_buy_hold": (
                _ratio(erem_pnl, buyhold_pnl) if buyhold_pnl > 0 else None
            ),
            "erem_loss_avoidance_vs_buy_hold": (
                1.0 - _ratio(erem_pnl, buyhold_pnl)
                if buyhold_pnl < 0
                else None
            ),
        }
    return result


def switch_cost_attribution(
    execution: pd.DataFrame,
    variant: EremVariant,
    thresholds: EremThresholds,
    start: pd.Timestamp,
    end: pd.Timestamp,
    config: EremPostmortemConfig,
) -> dict[str, Any]:
    """Compare EREM with real costs versus zero-cost EREM."""
    actual = simulate_erem_exposure(
        execution,
        variant,
        thresholds,
        start,
        end,
        config.erem_config,
    )
    zero_cost = simulate_erem_exposure(
        execution,
        variant,
        thresholds,
        start,
        end,
        config.zero_cost_erem_config,
    )
    cost_impact = float(zero_cost["erem_pnl_usdc"] - actual["erem_pnl_usdc"])
    flat = flat_period_attribution(
        execution,
        variant,
        thresholds,
        start,
        end,
        config.position_size_usdc,
    )
    loss_abs = abs(float(actual["erem_pnl_usdc"]))
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "actual_erem_pnl_usdc": actual["erem_pnl_usdc"],
        "zero_cost_erem_pnl_usdc": zero_cost["erem_pnl_usdc"],
        "cost_impact_usdc": cost_impact,
        "cost_share_of_actual_loss": (
            cost_impact / loss_abs if actual["erem_pnl_usdc"] < 0 and loss_abs > 0 else None
        ),
        "actual_switch_count": actual["switch_count"],
        "zero_cost_switch_count": zero_cost["switch_count"],
        "actual_time_in_market_pct": actual["time_in_market_pct"],
        "avoided_losses_usdc": flat["avoided_losses_usdc"],
        "missed_gains_usdc": flat["missed_gains_usdc"],
        "flat_block_count": flat["flat_block_count"],
        "flat_blocks_sample": flat["flat_blocks"][:10],
    }


def _pass_criteria(
    cycle_metrics: dict[str, Any],
    phases: dict[str, Any],
    cost_attribution: dict[str, Any],
    config: EremPostmortemConfig,
) -> dict[str, Any]:
    erem_calmar = cycle_metrics["erem"]["calmar"]
    buyhold_calmar = cycle_metrics["buy_hold"]["calmar"]
    bull = phases.get("bull", {})
    bear = phases.get("bear", {})
    bull_participation = bull.get("erem_participation_vs_buy_hold")
    bear_loss_avoidance = bear.get("erem_loss_avoidance_vs_buy_hold")
    erem_maxdd = cycle_metrics["erem"]["maxdd_usdc"]
    buyhold_maxdd = cycle_metrics["buy_hold"]["maxdd_usdc"]
    bull_positive_pnl = float(bull.get("buy_hold_positive_pnl_usdc") or 0.0)
    cost_impact = float(cost_attribution["cost_impact_usdc"])
    criteria = {
        "p1_erem_calmar_above_buy_hold": (
            erem_calmar is not None
            and buyhold_calmar is not None
            and erem_calmar > buyhold_calmar
        ),
        "p2_bull_participation_at_least_60pct": (
            bull_participation is not None
            and bull_participation >= config.min_bull_participation
        ),
        "p3_bear_loss_avoidance_at_least_40pct": (
            bear_loss_avoidance is not None
            and bear_loss_avoidance >= config.min_bear_loss_avoidance
        ),
        "p4_erem_maxdd_below_60pct_buy_hold": (
            buyhold_maxdd > 0
            and erem_maxdd
            < buyhold_maxdd * config.max_erem_to_buyhold_drawdown_ratio
        ),
        "p5_switch_cost_below_20pct_bull_positive_pnl": (
            bull_positive_pnl > 0
            and cost_impact
            < bull_positive_pnl * config.max_switch_cost_share_of_bull_positive_pnl
        ),
    }
    criteria["all_passed"] = all(criteria.values())
    criteria["bull_participation"] = bull_participation
    criteria["bear_loss_avoidance"] = bear_loss_avoidance
    criteria["erem_to_buyhold_maxdd_ratio"] = (
        erem_maxdd / buyhold_maxdd if buyhold_maxdd > 0 else None
    )
    criteria["switch_cost_share_of_bull_positive_pnl"] = (
        cost_impact / bull_positive_pnl if bull_positive_pnl > 0 else None
    )
    return criteria


def _decision_summary(
    pass_criteria: dict[str, Any],
    blindtest_cost: dict[str, Any],
    full_cost: dict[str, Any],
    config: EremPostmortemConfig,
) -> dict[str, Any]:
    blindtest_cost_share = blindtest_cost.get("cost_share_of_actual_loss")
    full_bull_cost_share = pass_criteria.get("switch_cost_share_of_bull_positive_pnl")
    switch_cost_problem = (
        (
            blindtest_cost_share is not None
            and blindtest_cost_share > config.switch_cost_problem_share_of_loss
        )
        or (
            full_bull_cost_share is not None
            and full_bull_cost_share
            > config.switch_cost_problem_share_of_bull_positive_pnl
        )
    )
    if pass_criteria["all_passed"]:
        recommendation = (
            "EREM cycle participation passed. Do not trade yet; ask for one "
            "separate review of risk-adjusted beta-management as the project goal."
        )
    elif switch_cost_problem:
        recommendation = (
            "EREM remains non-takeover. If EREM is revisited at all, only a "
            "separate research-only hysteresis/min-hold diagnostic is allowed; "
            "no UI/full rerun and no blindtest tuning."
        )
    else:
        recommendation = (
            "Archive EREM as defensive benchmark. Do not tune EREM gates. Move to "
            "a new research-only profit-alpha existence scan."
        )
    return {
        "cycle_participation_passed": pass_criteria["all_passed"],
        "switch_cost_problem_detected": switch_cost_problem,
        "blindtest_cost_share_of_loss": blindtest_cost_share,
        "full_period_cost_share_of_loss": full_cost.get("cost_share_of_actual_loss"),
        "recommended_next_step": recommendation,
        "ui_full_backtest_allowed_now": False,
        "router_integration_allowed_now": False,
        "frozen_blindtest_allowed_now": False,
    }


def run_erem_postmortem_cycle_scan(
    config: EremPostmortemConfig | None = None,
) -> dict[str, Any]:
    """Run EREM switch-cost and cycle-participation diagnostics."""
    active_config = config or EremPostmortemConfig()
    execution, training_start, blindtest_start, blindtest_end = _load_full_execution()
    variant = fixed_erem_variant()
    thresholds = calibrate_erem_thresholds(
        execution,
        training_start,
        blindtest_start - pd.Timedelta(hours=1),
        variant,
    )
    start = training_start
    end = blindtest_end
    curve = build_erem_equity_curve(
        execution,
        variant,
        thresholds,
        start,
        end,
        active_config.erem_config,
    )
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    phases = phase_participation_summary(execution.loc[start:end], curve, active_config)
    cycle_metrics = {
        "erem": _curve_metrics(
            curve,
            "erem_equity",
            active_config.position_size_usdc,
            days,
        ),
        "buy_hold": _curve_metrics(
            curve,
            "buy_hold_equity",
            active_config.position_size_usdc,
            days,
        ),
    }
    full_cost = switch_cost_attribution(
        execution,
        variant,
        thresholds,
        start,
        end,
        active_config,
    )
    blindtest_cost = switch_cost_attribution(
        execution,
        variant,
        thresholds,
        blindtest_start,
        blindtest_end,
        active_config,
    )
    criteria = _pass_criteria(cycle_metrics, phases, full_cost, active_config)
    decision = _decision_summary(criteria, blindtest_cost, full_cost, active_config)
    status = (
        "erem_cycle_participation_passed"
        if criteria["all_passed"]
        else "erem_cycle_participation_failed"
    )
    report: dict[str, Any] = {
        "strategy_version": EREM_POSTMORTEM_CYCLE_VERSION,
        "depends_on_strategy_versions": [
            EREM_EXPOSURE_EDGE_VERSION,
            EREM_FROZEN_BLINDTEST_VERSION,
            "erem_defensive_router_v1_1_hourly_aligned_20260702",
        ],
        "status": status,
        "research_only": True,
        "postmortem_only": True,
        "runs_new_blindtest": False,
        "runs_ui_backtest": False,
        "searches_variants": False,
        "changes_strategy_parameters": False,
        "uses_blindtest_for_selection": False,
        "candidate_variant": asdict(variant),
        "thresholds_calibrated_on_training_only": asdict(thresholds),
        "data_range": {
            "training_start": training_start.isoformat(),
            "blindtest_start": blindtest_start.isoformat(),
            "blindtest_end": blindtest_end.isoformat(),
            "full_cycle_start": start.isoformat(),
            "full_cycle_end": end.isoformat(),
        },
        "config": {
            key: str(value) if isinstance(value, Path) else _to_jsonable(value)
            for key, value in asdict(active_config).items()
        },
        "cycle_metrics": cycle_metrics,
        "phase_participation": phases,
        "full_period_switch_cost_attribution": full_cost,
        "blindtest_switch_cost_attribution": blindtest_cost,
        "pass_criteria": criteria,
        "decision_summary": decision,
        "lookahead_safety_notes": [
            "No variants are searched.",
            "The fixed EREM candidate is the already-tested UI candidate.",
            "Thresholds are calibrated on training only.",
            "Blindtest values are post-mortem diagnostics, not parameter selection.",
            "No router or UI decision is changed by this report.",
        ],
    }
    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "erem_postmortem_cycle_scan_report.json"
    report["output_paths"] = {"report": str(report_path)}
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=_to_jsonable) + "\n",
        encoding="utf-8",
    )
    return report
