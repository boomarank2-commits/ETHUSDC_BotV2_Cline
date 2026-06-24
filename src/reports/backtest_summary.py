"""UI-readable backtest summary built from existing reports."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.backtest.buy_hold_benchmark import load_buy_hold_benchmark_report
from src.backtest.run_request_io import load_backtest_run_request
from src.backtest.strategy_v0_report import load_strategy_v0_report
from src.backtest.strategy_v1_report import load_strategy_v1_report
from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.data.data_preparation_report import load_data_preparation_report
from src.data.train_blind_split_report import load_train_blind_split_report
from src.router.activity_first_router_report import load_activity_first_router_report
from src.router.cluster_router_report import load_cluster_router_report

BACKTEST_SUMMARY_FILENAME = "backtest_summary.json"
TARGET_QUOTE_PER_DAY = 3.0


def _best_router_training_quote_per_day(
    rejection_summary: dict[str, Any],
    selected_setups: list[dict[str, Any]],
) -> float:
    values = [float(row.get("training_quote_per_day", 0.0)) for row in selected_setups]
    for key in (
        "best_found_candidate",
        "best_activity_candidate",
        "best_edge_candidate",
        "best_balanced_candidate",
        "best_fee_survivor_candidate",
        "best_target_candidate",
    ):
        candidate = rejection_summary.get(key)
        if isinstance(candidate, dict):
            values.append(float(candidate.get("training_quote_per_day") or 0.0))
            values.append(float(candidate.get("expected_usdc_per_day") or 0.0))
    return max(values, default=0.0)


def _load_cluster_router_diagnostics(run_id: str) -> dict[str, Any]:
    path = get_run_report_dir(run_id) / "cluster_router_diagnostics.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class BacktestSummary:
    """Compact technical summary for later UI display."""

    run_id: str
    status: str
    symbol: str
    quote_asset: str
    start_capital: float
    final_capital: float | None
    total_pnl: float | None
    total_pnl_pct: float | None
    trade_count: int | None
    training_start: str | None
    training_end: str | None
    blindtest_start: str | None
    blindtest_end: str | None
    candle_count: int | None
    detected_gaps: int | None
    usable_for_backtest: bool
    message: str
    quote_per_day: float | None = None
    selected_family: str | None = None
    selected_candidate_name: str | None = None
    positive_days: int | None = None
    negative_days: int | None = None
    best_day_pnl: float | None = None
    worst_day_pnl: float | None = None
    no_robust_positive_candidate: bool = False
    candidate_space_status: str | None = None
    best_final_training_score: float | None = None
    best_training_quote_per_day: float | None = None
    target_feasibility_status: str | None = None
    target_min_training_ratio: float | None = None
    run_type: str = "full_backtest"

    def __post_init__(self) -> None:
        get_run_report_dir(self.run_id)


def _get_backtest_summary_path(run_id: str) -> Path:
    return get_run_report_dir(run_id) / BACKTEST_SUMMARY_FILENAME


def build_backtest_summary(run_id: str) -> BacktestSummary:
    """Build a compact summary from existing technical reports."""
    get_run_report_dir(run_id)
    try:
        run_type = load_backtest_run_request(run_id).run_type
    except FileNotFoundError:
        run_type = "full_backtest"
    data_report = load_data_preparation_report(run_id)
    if not data_report.usable_for_backtest:
        return BacktestSummary(
            run_id=run_id,
            status="failed",
            symbol=data_report.symbol,
            quote_asset="USDC",
            start_capital=100.0,
            final_capital=None,
            total_pnl=None,
            total_pnl_pct=None,
            trade_count=None,
            training_start=None,
            training_end=None,
            blindtest_start=None,
            blindtest_end=None,
            candle_count=data_report.candle_count,
            detected_gaps=data_report.detected_gaps,
            usable_for_backtest=False,
            message=data_report.reason or "data is not usable for backtest",
            run_type=run_type,
        )

    split_report = load_train_blind_split_report(run_id)
    try:
        activity_report = load_activity_first_router_report(run_id)
        target_status = activity_report.target_feasibility_status
        diagnostic_only = bool(activity_report.router_artifact.get("diagnostic_only"))
        if activity_report.blindtest_quote_per_day >= TARGET_QUOTE_PER_DAY and not diagnostic_only:
            target_status = "blindtest_target_reached"
        selected_name = None
        if activity_report.selected_setups:
            selected_name = str(activity_report.selected_setups[0].get("candidate_id"))
        if diagnostic_only:
            message = "Activity First Router diagnostic completed - no trade_allowed candidate"
        else:
            message = "Activity First Router training+blindtest completed"
        return BacktestSummary(
            run_id=run_id,
            status="completed",
            symbol=activity_report.symbol,
            quote_asset=activity_report.quote_asset,
            start_capital=activity_report.start_capital_reference,
            final_capital=activity_report.blindtest_final_capital_reference,
            total_pnl=activity_report.blindtest_total_net_pnl,
            total_pnl_pct=(
                activity_report.blindtest_total_net_pnl
                / activity_report.start_capital_reference
                * 100
            ),
            trade_count=activity_report.blindtest_trade_count,
            training_start=split_report.training_start,
            training_end=split_report.training_end,
            blindtest_start=split_report.blindtest_start,
            blindtest_end=split_report.blindtest_end,
            candle_count=data_report.candle_count,
            detected_gaps=data_report.detected_gaps,
            usable_for_backtest=True,
            message=message,
            quote_per_day=activity_report.blindtest_quote_per_day,
            selected_family="activity_first_router",
            selected_candidate_name=selected_name,
            positive_days=activity_report.positive_days,
            negative_days=activity_report.negative_days,
            best_day_pnl=activity_report.best_day_pnl,
            worst_day_pnl=activity_report.worst_day_pnl,
            no_robust_positive_candidate=activity_report.trade_allowed_setup_count == 0,
            candidate_space_status=activity_report.candidate_space_status,
            best_final_training_score=None,
            best_training_quote_per_day=activity_report.best_training_quote_per_day,
            target_feasibility_status=target_status,
            target_min_training_ratio=(
                activity_report.blindtest_quote_per_day / TARGET_QUOTE_PER_DAY
            ),
            run_type=str(activity_report.router_artifact.get("run_type") or run_type),
        )
    except FileNotFoundError:
        pass

    try:
        cluster_router_report = load_cluster_router_report(run_id)
        diagnostics = _load_cluster_router_diagnostics(run_id)
        if cluster_router_report.blindtest_quote_per_day >= TARGET_QUOTE_PER_DAY:
            target_status = "blindtest_target_reached"
        else:
            target_status = str(diagnostics.get("target_math_status") or "target_out_of_reach_current_space")
        optimizer_status = str(cluster_router_report.rejection_summary.get("optimizer_status") or "")
        if cluster_router_report.trade_allowed_setup_count == 0 and optimizer_status in {
            "optimizer_failed_to_find_target_relevant_search_space",
            "optimizer_search_space_failed",
        }:
            candidate_status = optimizer_status
        elif cluster_router_report.trade_allowed_setup_count == 0:
            candidate_status = "router_too_inactive"
        elif cluster_router_report.blindtest_total_net_pnl > 0:
            candidate_status = "router_built_blindtest_positive"
        elif cluster_router_report.blindtest_gross_pnl > 0:
            candidate_status = "blindtest_negative_after_costs"
        else:
            candidate_status = "router_failed_generalization"
        return BacktestSummary(
            run_id=run_id,
            status="completed",
            symbol=cluster_router_report.symbol,
            quote_asset=cluster_router_report.quote_asset,
            start_capital=cluster_router_report.start_capital_reference,
            final_capital=cluster_router_report.final_capital_reference,
            total_pnl=cluster_router_report.blindtest_total_net_pnl,
            total_pnl_pct=cluster_router_report.blindtest_total_net_pnl
            / cluster_router_report.start_capital_reference
            * 100,
            trade_count=cluster_router_report.blindtest_trade_count,
            training_start=split_report.training_start,
            training_end=split_report.training_end,
            blindtest_start=split_report.blindtest_start,
            blindtest_end=split_report.blindtest_end,
            candle_count=data_report.candle_count,
            detected_gaps=data_report.detected_gaps,
            usable_for_backtest=True,
            message="Cluster Router training+blindtest completed",
            quote_per_day=cluster_router_report.blindtest_quote_per_day,
            selected_family="cluster_router",
            selected_candidate_name=f"{cluster_router_report.router_setup_count} frozen setup(s)",
            positive_days=cluster_router_report.positive_days,
            negative_days=cluster_router_report.negative_days,
            best_day_pnl=cluster_router_report.best_day_pnl,
            worst_day_pnl=cluster_router_report.worst_day_pnl,
            no_robust_positive_candidate=cluster_router_report.trade_allowed_setup_count == 0,
            candidate_space_status=candidate_status,
            best_final_training_score=None,
            best_training_quote_per_day=_best_router_training_quote_per_day(
                cluster_router_report.rejection_summary,
                cluster_router_report.selected_setups,
            ),
            target_feasibility_status=target_status,
            target_min_training_ratio=cluster_router_report.blindtest_quote_per_day
            / TARGET_QUOTE_PER_DAY,
            run_type=str(cluster_router_report.router_artifact.get("run_type") or run_type),
        )
    except FileNotFoundError:
        pass

    try:
        strategy_v1_report = load_strategy_v1_report(run_id)
        return BacktestSummary(
            run_id=run_id,
            status="completed",
            symbol=strategy_v1_report.symbol,
            quote_asset=strategy_v1_report.quote_asset,
            start_capital=strategy_v1_report.start_capital_reference,
            final_capital=strategy_v1_report.blindtest_final_capital_reference,
            total_pnl=strategy_v1_report.blindtest_total_net_pnl,
            total_pnl_pct=strategy_v1_report.blindtest_total_net_pnl_pct,
            trade_count=strategy_v1_report.blindtest_trade_count,
            training_start=split_report.training_start,
            training_end=split_report.training_end,
            blindtest_start=split_report.blindtest_start,
            blindtest_end=split_report.blindtest_end,
            candle_count=data_report.candle_count,
            detected_gaps=data_report.detected_gaps,
            usable_for_backtest=True,
            message="Strategy V1 training+blindtest completed",
            quote_per_day=strategy_v1_report.blindtest_quote_per_day,
            selected_family=strategy_v1_report.selected_candidate.family,
            selected_candidate_name=strategy_v1_report.selected_candidate.name,
            positive_days=strategy_v1_report.positive_days,
            negative_days=strategy_v1_report.negative_days,
            best_day_pnl=strategy_v1_report.best_day_pnl,
            worst_day_pnl=strategy_v1_report.worst_day_pnl,
            no_robust_positive_candidate=strategy_v1_report.no_robust_positive_candidate,
            candidate_space_status=strategy_v1_report.candidate_space_status,
            best_final_training_score=strategy_v1_report.best_final_training_score,
            best_training_quote_per_day=strategy_v1_report.best_training_quote_per_day,
            target_feasibility_status=strategy_v1_report.target_feasibility_status,
            target_min_training_ratio=strategy_v1_report.target_min_training_ratio,
        )
    except FileNotFoundError:
        pass

    try:
        strategy_report = load_strategy_v0_report(run_id)
        return BacktestSummary(
            run_id=run_id,
            status="completed",
            symbol=strategy_report.symbol,
            quote_asset=strategy_report.quote_asset,
            start_capital=strategy_report.start_capital,
            final_capital=strategy_report.blindtest_final_capital,
            total_pnl=strategy_report.blindtest_total_pnl,
            total_pnl_pct=strategy_report.blindtest_total_pnl_pct,
            trade_count=strategy_report.blindtest_trade_count,
            training_start=split_report.training_start,
            training_end=split_report.training_end,
            blindtest_start=split_report.blindtest_start,
            blindtest_end=split_report.blindtest_end,
            candle_count=data_report.candle_count,
            detected_gaps=data_report.detected_gaps,
            usable_for_backtest=True,
            message="Strategy V0 training+blindtest completed",
        )
    except FileNotFoundError:
        pass

    benchmark_report = load_buy_hold_benchmark_report(run_id)
    return BacktestSummary(
        run_id=run_id,
        status="completed",
        symbol=benchmark_report.symbol,
        quote_asset=benchmark_report.quote_asset,
        start_capital=benchmark_report.start_capital,
        final_capital=benchmark_report.final_capital,
        total_pnl=benchmark_report.total_pnl,
        total_pnl_pct=benchmark_report.total_pnl_pct,
        trade_count=benchmark_report.trade_count,
        training_start=split_report.training_start,
        training_end=split_report.training_end,
        blindtest_start=split_report.blindtest_start,
        blindtest_end=split_report.blindtest_end,
        candle_count=data_report.candle_count,
        detected_gaps=data_report.detected_gaps,
        usable_for_backtest=True,
        message="completed",
    )


def save_backtest_summary(summary: BacktestSummary) -> Path:
    """Save a compact backtest summary as readable JSON."""
    report_dir = ensure_run_report_dir(summary.run_id)
    summary_path = report_dir / BACKTEST_SUMMARY_FILENAME
    content = json.dumps(asdict(summary), indent=2, sort_keys=True)
    summary_path.write_text(f"{content}\n", encoding="utf-8")
    return summary_path


def load_backtest_summary(run_id: str) -> BacktestSummary:
    """Load and validate a compact backtest summary."""
    raw_summary: dict[str, Any] = json.loads(
        _get_backtest_summary_path(run_id).read_text(encoding="utf-8")
    )
    return BacktestSummary(**raw_summary)
