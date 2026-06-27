"""UI-readable backtest summary built from existing reports."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.backtest.run_request_io import load_backtest_run_request
from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.data.data_preparation_report import load_data_preparation_report
from src.data.train_blind_split_report import load_train_blind_split_report
from src.router.activity_first_router_report import load_activity_first_router_report

BACKTEST_SUMMARY_FILENAME = "backtest_summary.json"
TARGET_QUOTE_PER_DAY = 3.0


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
        training_start=split_report.training_start,
        training_end=split_report.training_end,
        blindtest_start=split_report.blindtest_start,
        blindtest_end=split_report.blindtest_end,
        candle_count=data_report.candle_count,
        detected_gaps=data_report.detected_gaps,
        usable_for_backtest=False,
        message="Activity-First Router report missing; no alternate backtest engine is permitted",
        run_type=run_type,
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
