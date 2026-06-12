"""UI-readable backtest summary built from existing reports."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.backtest.buy_hold_benchmark import load_buy_hold_benchmark_report
from src.backtest.strategy_v0_report import load_strategy_v0_report
from src.backtest.strategy_v1_report import load_strategy_v1_report
from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.data.data_preparation_report import load_data_preparation_report
from src.data.train_blind_split_report import load_train_blind_split_report

BACKTEST_SUMMARY_FILENAME = "backtest_summary.json"


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

    def __post_init__(self) -> None:
        get_run_report_dir(self.run_id)


def _get_backtest_summary_path(run_id: str) -> Path:
    return get_run_report_dir(run_id) / BACKTEST_SUMMARY_FILENAME


def build_backtest_summary(run_id: str) -> BacktestSummary:
    """Build a compact summary from existing technical reports."""
    get_run_report_dir(run_id)
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
        )

    split_report = load_train_blind_split_report(run_id)
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
