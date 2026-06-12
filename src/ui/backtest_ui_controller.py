"""UI controller for running the benchmark pipeline without UI dependencies."""

from dataclasses import dataclass

from src.backtest.preparation_pipeline import run_backtest_preparation_pipeline
from src.reports.backtest_summary import BacktestSummary, load_backtest_summary


@dataclass(frozen=True)
class BacktestUiResult:
    """UI-friendly result for a backtest benchmark run."""

    success: bool
    run_id: str | None
    status: str
    message: str
    start_capital: float | None
    final_capital: float | None
    total_pnl: float | None
    total_pnl_pct: float | None
    trade_count: int | None
    training_start: str | None
    training_end: str | None
    blindtest_start: str | None
    blindtest_end: str | None
    report_path: str | None


def _result_from_summary(summary: BacktestSummary, report_path: str) -> BacktestUiResult:
    return BacktestUiResult(
        success=summary.status == "completed",
        run_id=summary.run_id,
        status=summary.status,
        message=summary.message,
        start_capital=summary.start_capital,
        final_capital=summary.final_capital,
        total_pnl=summary.total_pnl,
        total_pnl_pct=summary.total_pnl_pct,
        trade_count=summary.trade_count,
        training_start=summary.training_start,
        training_end=summary.training_end,
        blindtest_start=summary.blindtest_start,
        blindtest_end=summary.blindtest_end,
        report_path=report_path,
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
            start_capital=None,
            final_capital=None,
            total_pnl=None,
            total_pnl_pct=None,
            trade_count=None,
            training_start=None,
            training_end=None,
            blindtest_start=None,
            blindtest_end=None,
            report_path=None,
        )
    except Exception as error:  # noqa: BLE001
        return BacktestUiResult(
            success=False,
            run_id=None,
            status="failed",
            message=str(error),
            start_capital=None,
            final_capital=None,
            total_pnl=None,
            total_pnl_pct=None,
            trade_count=None,
            training_start=None,
            training_end=None,
            blindtest_start=None,
            blindtest_end=None,
            report_path=None,
        )
