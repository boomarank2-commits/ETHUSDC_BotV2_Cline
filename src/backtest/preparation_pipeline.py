"""Technical preparation pipeline for future backtest runs."""

from dataclasses import dataclass
from time import time
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
from src.router.cluster_router_report import build_cluster_router_report, save_cluster_router_report
from src.data.data_preparation_report import (
    build_data_preparation_report,
    save_data_preparation_report,
)
from src.data.data_overview import build_data_overview_report, save_data_overview_report
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
    run_type: str
    data_preparation_report_path: str
    data_overview_report_path: str | None
    train_blind_split_report_path: str
    buy_hold_benchmark_report_path: str | None
    strategy_v0_report_path: str | None
    strategy_v1_report_path: str | None
    cluster_router_report_path: str | None
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
    started_at: float | None = None,
) -> str:
    runtime_seconds = None if started_at is None else max(0.0, time() - started_at)
    estimated_remaining_seconds = None
    if runtime_seconds is not None and 0 < progress_pct < 100:
        estimated_remaining_seconds = max(0.0, runtime_seconds / (progress_pct / 100.0) - runtime_seconds)
    progress_path = save_run_progress(
        BacktestRunProgress(
            run_id=run_id,
            status=status,
            stage=stage,
            progress_pct=progress_pct,
            message=message,
            error=error,
            runtime_seconds=runtime_seconds,
            estimated_remaining_seconds=estimated_remaining_seconds,
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
    run_type: str = "full_backtest",
    blindtest_days: int | None = None,
    training_days: int | None = None,
    progress_callback: Callable[[dict], None] | None = None,
) -> PreparationPipelineResult:
    """Run technical preparation without trades, PnL, signals or optimization."""
    if run_type not in {"full_backtest", "smoke_test"}:
        msg = "run_type must be full_backtest or smoke_test"
        raise ValueError(msg)
    if run_type == "smoke_test":
        if blindtest_days not in {1, 7, 14, 30}:
            msg = "smoke_test blindtest_days must be 1, 7, 14 or 30"
            raise ValueError(msg)
        training_days = training_days if training_days is not None else blindtest_days * 2
    else:
        blindtest_days = None
        training_days = None
    run_id = ""
    data_report_path = ""
    data_overview_path: str | None = None
    split_report_path = ""
    benchmark_report_path: str | None = None
    strategy_v0_report_path: str | None = None
    strategy_v1_report_path: str | None = None
    cluster_router_report_path: str | None = None
    summary_path: str | None = None
    progress_path = ""
    try:
        started_at = time()
        request = initialize_backtest_run(
            time_budget_minutes=time_budget_minutes,
            run_type=run_type,
            training_days=training_days,
            blindtest_days=blindtest_days,
        )
        run_id = request.run_id
        _emit_progress(
            progress_callback, "run_initialized", 0.0, "Backtest-Lauf initialisiert", run_id=run_id
        )
        progress_path = _save_progress(run_id, "initialized", "initialized", 0.0, started_at=started_at)
        _emit_progress(
            progress_callback,
            "data_preparation_started",
            10.0,
            "Datenvorbereitung läuft",
            run_id=run_id,
        )
        progress_path = _save_progress(run_id, "running", "data_preparation", 25.0, started_at=started_at)

        dataset = load_local_candle_dataset_from_catalog()
        data_report = build_data_preparation_report(run_id)
        data_report_path = str(save_data_preparation_report(data_report))
        data_overview_path = str(save_data_overview_report(build_data_overview_report(run_id)))
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
            progress_path = _save_progress(run_id, "failed", "data_preparation", 100.0, error=error, started_at=started_at)
            _emit_progress(progress_callback, "failed", 100.0, error, run_id=run_id, error=error)
            return PreparationPipelineResult(
                run_id,
                "failed",
                run_type,
                data_report_path,
                data_overview_path,
                "",
                None,
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
        progress_path = _save_progress(run_id, "running", "train_blind_split", 75.0, started_at=started_at)
        split = build_train_blind_split(dataset, training_days=training_days, blindtest_days=blindtest_days)
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
        progress_path = _save_progress(run_id, "running", "buy_hold_benchmark", 50.0, started_at=started_at)
        benchmark_report = build_buy_hold_benchmark_report(run_id, split)
        benchmark_report_path = str(save_buy_hold_benchmark_report(benchmark_report))
        progress_path = _save_progress(run_id, "running", "strategy_v0", 60.0, started_at=started_at)
        _emit_progress(
            progress_callback,
            "strategy_v0_started",
            60.0,
            "Strategy V0 Vergleich läuft",
            run_id=run_id,
        )
        strategy_v0_report = build_strategy_v0_training_blindtest_report(run_id, split)
        strategy_v0_report_path = str(save_strategy_v0_report(strategy_v0_report))
        progress_path = _save_progress(run_id, "running", "strategy_v1", 70.0, started_at=started_at)
        strategy_v1_report = build_strategy_v1_training_blindtest_report(
            run_id,
            split,
            stake_quote_amount=stake_quote_amount,
            profile=profile,
            progress_callback=progress_callback,
        )
        strategy_v1_report_path = str(save_strategy_v1_report(strategy_v1_report))
        progress_path = _save_progress(run_id, "running", "cluster_router", 89.0, started_at=started_at)

        def _cluster_progress(event: dict) -> None:
            nonlocal progress_path
            pct = float(event.get("progress_pct", 89.0))
            detail = str(event.get("detail") or "Cluster-Router Setup-Suche läuft")
            progress_path = _save_progress(run_id, "running", "cluster_router", pct, message=detail, started_at=started_at)
            if progress_callback is not None:
                progress_callback({**event, "run_id": run_id})

        cluster_router_report = build_cluster_router_report(
            run_id,
            split,
            stake_quote_amount=stake_quote_amount,
            progress_callback=_cluster_progress,
        )
        cluster_router_report.router_artifact["run_type"] = run_type
        cluster_router_report.router_artifact["smoke_test_not_performance_proof"] = run_type == "smoke_test"
        cluster_router_report.router_artifact["live_release_allowed"] = False
        cluster_router_report_path = str(save_cluster_router_report(cluster_router_report))
        _emit_progress(
            progress_callback, "summary_started", 90.0, "Reports werden gespeichert", run_id=run_id
        )
        summary_path = str(save_backtest_summary(build_backtest_summary(run_id)))
        progress_path = _save_progress(run_id, "completed", "completed", 100.0, started_at=started_at)
        mark_backtest_run_completed(run_id)
        _emit_progress(
            progress_callback, "completed", 100.0, "Backtest abgeschlossen", run_id=run_id
        )
        return PreparationPipelineResult(
            run_id,
            "completed",
            run_type,
            data_report_path,
            data_overview_path,
            split_report_path,
            benchmark_report_path,
            strategy_v0_report_path,
            strategy_v1_report_path,
            cluster_router_report_path,
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
                    run_id, "failed", "failed", 100.0, error=error_message, started_at=locals().get("started_at")
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
            run_type,
            data_report_path,
            data_overview_path,
            split_report_path,
            benchmark_report_path,
            strategy_v0_report_path,
            strategy_v1_report_path,
            cluster_router_report_path,
            summary_path,
            progress_path,
            error_message,
        )
