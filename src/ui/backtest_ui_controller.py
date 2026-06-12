"""UI controller for running the benchmark pipeline without UI dependencies."""

from dataclasses import dataclass
from pathlib import Path

from src.backtest.preparation_pipeline import run_backtest_preparation_pipeline
from src.reports.backtest_summary import BacktestSummary, load_backtest_summary


@dataclass(frozen=True)
class BacktestUiResult:
    """UI-friendly result for a backtest benchmark run."""

    success: bool
    run_id: str | None
    status: str
    message: str
    symbol: str | None
    start_capital: float | None
    final_capital: float | None
    total_pnl: float | None
    total_pnl_pct: float | None
    trade_count: int | None
    candle_count: int | None
    detected_gaps: int | None
    usable_for_backtest: bool | None
    training_start: str | None
    training_end: str | None
    blindtest_start: str | None
    blindtest_end: str | None
    report_path: str | None
    report_folder: str | None
    usdt_per_day: float | None = None
    selected_family: str | None = None
    selected_candidate_name: str | None = None


def _result_from_summary(summary: BacktestSummary, report_path: str) -> BacktestUiResult:
    return BacktestUiResult(
        success=summary.status == "completed",
        run_id=summary.run_id,
        status=summary.status,
        message=summary.message,
        symbol=summary.symbol,
        start_capital=summary.start_capital,
        final_capital=summary.final_capital,
        total_pnl=summary.total_pnl,
        total_pnl_pct=summary.total_pnl_pct,
        trade_count=summary.trade_count,
        candle_count=summary.candle_count,
        detected_gaps=summary.detected_gaps,
        usable_for_backtest=summary.usable_for_backtest,
        training_start=summary.training_start,
        training_end=summary.training_end,
        blindtest_start=summary.blindtest_start,
        blindtest_end=summary.blindtest_end,
        report_path=report_path,
        report_folder=str(Path(report_path).parent),
        usdt_per_day=summary.usdt_per_day,
        selected_family=summary.selected_family,
        selected_candidate_name=summary.selected_candidate_name,
    )


def run_backtest_for_ui() -> BacktestUiResult:
    """Run the existing benchmark pipeline and return a UI-friendly result."""
    try:
        pipeline_result = run_backtest_preparation_pipeline()
        if pipeline_result.backtest_summary_path:
            summary = load_backtest_summary(pipeline_result.run_id)
            return _result_from_summary(summary, pipeline_result.backtest_summary_path)
        return BacktestUiResult(
            success=False,
            run_id=pipeline_result.run_id or None,
            status=pipeline_result.status,
            message=pipeline_result.error or "backtest pipeline failed without summary",
            symbol=None,
            start_capital=None,
            final_capital=None,
            total_pnl=None,
            total_pnl_pct=None,
            trade_count=None,
            candle_count=None,
            detected_gaps=None,
            usable_for_backtest=None,
            training_start=None,
            training_end=None,
            blindtest_start=None,
            blindtest_end=None,
            report_path=None,
            report_folder=None,
        )
    except Exception as error:  # noqa: BLE001
        return BacktestUiResult(
            success=False,
            run_id=None,
            status="failed",
            message=str(error),
            symbol=None,
            start_capital=None,
            final_capital=None,
            total_pnl=None,
            total_pnl_pct=None,
            trade_count=None,
            candle_count=None,
            detected_gaps=None,
            usable_for_backtest=None,
            training_start=None,
            training_end=None,
            blindtest_start=None,
            blindtest_end=None,
            report_path=None,
            report_folder=None,
        )
