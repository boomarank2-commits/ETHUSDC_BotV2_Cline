"""Technical preparation pipeline for future backtest runs."""

from dataclasses import dataclass
from typing import Callable

from src.backtest.buy_hold_benchmark import (
    build_buy_hold_benchmark_report,
    save_buy_hold_benchmark_report,
)
from src.backtest.run_finalizer import mark_backtest_run_completed, mark_backtest_run_failed
from src.backtest.run_initializer import initialize_backtest_run
from src.backtest.run_progress import BacktestRunProgress, save_run_progress
from src.backtest.strategy_v0_report import (
    build_strategy_v0_training_blindtest_report,
    save_strategy_v0_report,
)
from src.backtest.strategy_v1_report import (
    build_strategy_v1_training_blindtest_report,
    save_strategy_v1_report,
)
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
from src.reports.backtest_summary import build_backtest_summary, save_backtest_summary


@dataclass(frozen=True)
class PreparationPipelineResult:
    """Technical result of the preparation pipeline."""

    run_id: str
    status: str
    data_preparation_report_path: str
    train_blind_split_report_path: str
    buy_hold_benchmark_report_path: str | None
    strategy_v0_report_path: str | None
    strategy_v1_report_path: str | None
    backtest_summary_path: str | None
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


def _emit_progress(
    progress_callback: Callable[[dict], None] | None,
    phase: str,
    progress_pct: float,
    detail: str,
    **extra: object,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        {
            "phase": phase,
            "progress_pct": progress_pct,
            "detail": detail,
            **extra,
        }
    )


def run_backtest_preparation_pipeline(
    time_budget_minutes: int | None = None,
    stake_quote_amount: float = 100.0,
    profile: str = "normal",
    progress_callback: Callable[[dict], None] | None = None,
) -> PreparationPipelineResult:
    """Run technical preparation without trades, PnL, signals or optimization."""
    run_id = ""
    data_report_path = ""
    split_report_path = ""
    benchmark_report_path: str | None = None
    strategy_v0_report_path: str | None = None
    strategy_v1_report_path: str | None = None
    summary_path: str | None = None
    progress_path = ""
    try:
        request = initialize_backtest_run(time_budget_minutes=time_budget_minutes)
        run_id = request.run_id
        _emit_progress(
            progress_callback, "run_initialized", 0.0, "Backtest-Lauf initialisiert", run_id=run_id
        )
        progress_path = _save_progress(run_id, "initialized", "initialized", 0.0)
        _emit_progress(
            progress_callback,
            "data_preparation_started",
            10.0,
            "Datenvorbereitung läuft",
            run_id=run_id,
        )
        progress_path = _save_progress(run_id, "running", "data_preparation", 25.0)

        dataset = load_local_candle_dataset_from_catalog()
        data_report = build_data_preparation_report(run_id)
        data_report_path = str(save_data_preparation_report(data_report))
        _emit_progress(
            progress_callback,
            "data_preparation_completed",
            20.0,
            "Datenvorbereitung abgeschlossen",
            run_id=run_id,
            candle_count=len(dataset.candles),
        )
        if not data_report.usable_for_backtest:
            error = data_report.reason or "data is not usable for backtest preparation"
            summary_path = str(save_backtest_summary(build_backtest_summary(run_id)))
            mark_backtest_run_failed(run_id, error)
            progress_path = _save_progress(run_id, "failed", "data_preparation", 100.0, error=error)
            _emit_progress(progress_callback, "failed", 100.0, error, run_id=run_id, error=error)
            return PreparationPipelineResult(
                run_id,
                "failed",
                data_report_path,
                "",
                None,
                None,
                None,
                summary_path,
                progress_path,
                error,
            )

        _emit_progress(
            progress_callback, "split_started", 35.0, "Train/Blindtest Split startet", run_id=run_id
        )
        progress_path = _save_progress(run_id, "running", "train_blind_split", 75.0)
        split = build_train_blind_split(dataset)
        split_report = build_train_blind_split_report(run_id, split)
        split_report_path = str(save_train_blind_split_report(split_report))
        _emit_progress(
            progress_callback,
            "split_completed",
            45.0,
            "Train/Blindtest Split abgeschlossen",
            run_id=run_id,
        )
        _emit_progress(
            progress_callback,
            "buyhold_started",
            50.0,
            "Buy-and-Hold Benchmark läuft",
            run_id=run_id,
        )
        benchmark_report = build_buy_hold_benchmark_report(run_id, split)
        benchmark_report_path = str(save_buy_hold_benchmark_report(benchmark_report))
        _emit_progress(
            progress_callback,
            "strategy_v0_started",
            60.0,
            "Strategy V0 Vergleich läuft",
            run_id=run_id,
        )
        strategy_v0_report = build_strategy_v0_training_blindtest_report(run_id, split)
        strategy_v0_report_path = str(save_strategy_v0_report(strategy_v0_report))
        strategy_v1_report = build_strategy_v1_training_blindtest_report(
            run_id,
            split,
            stake_quote_amount=stake_quote_amount,
            profile=profile,
            progress_callback=progress_callback,
        )
        strategy_v1_report_path = str(save_strategy_v1_report(strategy_v1_report))
        _emit_progress(
            progress_callback, "summary_started", 90.0, "Reports werden gespeichert", run_id=run_id
        )
        summary_path = str(save_backtest_summary(build_backtest_summary(run_id)))
        progress_path = _save_progress(run_id, "completed", "completed", 100.0)
        mark_backtest_run_completed(run_id)
        _emit_progress(
            progress_callback, "completed", 100.0, "Backtest abgeschlossen", run_id=run_id
        )
        return PreparationPipelineResult(
            run_id,
            "completed",
            data_report_path,
            split_report_path,
            benchmark_report_path,
            strategy_v0_report_path,
            strategy_v1_report_path,
            summary_path,
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
                _emit_progress(
                    progress_callback,
                    "failed",
                    100.0,
                    error_message,
                    run_id=run_id,
                    error=error_message,
                )
            except Exception:  # noqa: BLE001
                pass
            try:
                summary_path = str(save_backtest_summary(build_backtest_summary(run_id)))
            except Exception:  # noqa: BLE001
                summary_path = None
        return PreparationPipelineResult(
            run_id,
            "failed",
            data_report_path,
            split_report_path,
            benchmark_report_path,
            strategy_v0_report_path,
            strategy_v1_report_path,
            summary_path,
            progress_path,
            error_message,
        )
