"""Technical preparation pipeline for future backtest runs."""

from dataclasses import dataclass

from src.backtest.buy_hold_benchmark import (
    build_buy_hold_benchmark_report,
    save_buy_hold_benchmark_report,
)
from src.backtest.run_finalizer import mark_backtest_run_completed, mark_backtest_run_failed
from src.backtest.run_initializer import initialize_backtest_run
from src.backtest.run_progress import BacktestRunProgress, save_run_progress
from src.data.data_preparation_report import (
    build_data_preparation_report,
    save_data_preparation_report,
)
from src.data.local_candle_loader import load_local_candle_dataset_from_catalog
from src.data.train_blind_split import build_train_blind_split
from src.data.train_blind_split_report import (
    build_train_blind_split_report,
    save_train_blind_split_report,
)


@dataclass(frozen=True)
class PreparationPipelineResult:
    """Technical result of the preparation pipeline."""

    run_id: str
    status: str
    data_preparation_report_path: str
    train_blind_split_report_path: str
    buy_hold_benchmark_report_path: str | None
    progress_path: str
    error: str | None


def _save_progress(
    run_id: str,
    status: str,
    stage: str,
    progress_pct: float,
    message: str | None = None,
    error: str | None = None,
) -> str:
    progress_path = save_run_progress(
        BacktestRunProgress(
            run_id=run_id,
            status=status,
            stage=stage,
            progress_pct=progress_pct,
            message=message,
            error=error,
        )
    )
    return str(progress_path)


def run_backtest_preparation_pipeline(
    time_budget_minutes: int | None = None,
) -> PreparationPipelineResult:
    """Run technical preparation without trades, PnL, signals or optimization."""
    run_id = ""
    data_report_path = ""
    split_report_path = ""
    benchmark_report_path: str | None = None
    progress_path = ""
    try:
        request = initialize_backtest_run(time_budget_minutes=time_budget_minutes)
        run_id = request.run_id
        progress_path = _save_progress(run_id, "initialized", "initialized", 0.0)
        progress_path = _save_progress(run_id, "running", "data_preparation", 25.0)

        dataset = load_local_candle_dataset_from_catalog()
        data_report = build_data_preparation_report(run_id)
        data_report_path = str(save_data_preparation_report(data_report))
        if not data_report.usable_for_backtest:
            error = data_report.reason or "data is not usable for backtest preparation"
            mark_backtest_run_failed(run_id, error)
            progress_path = _save_progress(run_id, "failed", "data_preparation", 100.0, error=error)
            return PreparationPipelineResult(
                run_id, "failed", data_report_path, "", None, progress_path, error
            )

        progress_path = _save_progress(run_id, "running", "train_blind_split", 75.0)
        split = build_train_blind_split(dataset)
        split_report = build_train_blind_split_report(run_id, split)
        split_report_path = str(save_train_blind_split_report(split_report))
        benchmark_report = build_buy_hold_benchmark_report(run_id, split)
        benchmark_report_path = str(save_buy_hold_benchmark_report(benchmark_report))
        progress_path = _save_progress(run_id, "completed", "completed", 100.0)
        mark_backtest_run_completed(run_id)
        return PreparationPipelineResult(
            run_id,
            "completed",
            data_report_path,
            split_report_path,
            benchmark_report_path,
            progress_path,
            None,
        )
    except Exception as error:  # noqa: BLE001
        error_message = str(error)
        if run_id:
            try:
                mark_backtest_run_failed(run_id, error_message)
                progress_path = _save_progress(
                    run_id, "failed", "failed", 100.0, error=error_message
                )
            except Exception:  # noqa: BLE001
                pass
        return PreparationPipelineResult(
            run_id,
            "failed",
            data_report_path,
            split_report_path,
            benchmark_report_path,
            progress_path,
            error_message,
        )
