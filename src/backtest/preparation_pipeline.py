"""Technical preparation pipeline for future backtest runs."""

from dataclasses import dataclass
from threading import Event, Thread
from time import time
from typing import Callable

from src.backtest.run_finalizer import mark_backtest_run_completed, mark_backtest_run_failed
from src.backtest.run_initializer import initialize_backtest_run
from src.backtest.run_progress import BacktestRunProgress, save_run_progress
from src.data.data_overview import build_data_overview_report, save_data_overview_report
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
from src.router import build_activity_first_router_report
from src.router.activity_first_router_report import save_activity_first_router_report


@dataclass(frozen=True)
class PreparationPipelineResult:
    """Technical result of the preparation pipeline."""

    run_id: str
    status: str
    run_type: str
    data_preparation_report_path: str
    data_overview_report_path: str | None
    train_blind_split_report_path: str
    backtest_summary_path: str | None
    progress_path: str
    error: str | None
    activity_first_router_report_path: str | None = None


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


def _start_heartbeat_progress(
    run_id: str,
    progress_callback: Callable[[dict], None] | None,
    started_at: float,
    stage: str,
    base_pct: float,
    max_pct: float,
    detail: str,
) -> Event:
    """Keep long UI stages visibly alive without changing the backtest path."""
    stop_event = Event()

    def _heartbeat() -> None:
        tick = 0
        while not stop_event.wait(10.0):
            tick += 1
            pct = min(max_pct, base_pct + tick * 0.25)
            message = f"{detail} - läuft weiter; längere Smoke-Dauer braucht entsprechend länger"
            try:
                _save_progress(
                    run_id,
                    "running",
                    stage,
                    pct,
                    message=message,
                    started_at=started_at,
                )
            except PermissionError:
                continue
            _emit_progress(
                progress_callback,
                stage,
                pct,
                message,
                run_id=run_id,
            )

    Thread(target=_heartbeat, daemon=True).start()
    return stop_event


def run_backtest_preparation_pipeline(
    time_budget_minutes: int | None = None,
    stake_quote_amount: float = 100.0,
    profile: str = "normal",
    run_type: str = "full_backtest",
    blindtest_days: int | None = None,
    training_days: int | None = None,
    progress_callback: Callable[[dict], None] | None = None,
) -> PreparationPipelineResult:
    """Run the one shared Activity-First pipeline for Full and Smoke."""
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
    activity_first_router_report_path: str | None = None
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
            progress_callback,
            "run_initialized",
            0.0,
            "Backtest-Lauf initialisiert",
            run_id=run_id,
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
            progress_path = _save_progress(
                run_id,
                "failed",
                "data_preparation",
                100.0,
                error=error,
                started_at=started_at,
            )
            _emit_progress(progress_callback, "failed", 100.0, error, run_id=run_id, error=error)
            return PreparationPipelineResult(
                run_id=run_id,
                status="failed",
                run_type=run_type,
                data_preparation_report_path=data_report_path,
                data_overview_report_path=data_overview_path,
                train_blind_split_report_path="",
                activity_first_router_report_path=None,
                backtest_summary_path=summary_path,
                progress_path=progress_path,
                error=error,
            )

        _emit_progress(
            progress_callback,
            "split_started",
            35.0,
            "Train/Blindtest Split startet",
            run_id=run_id,
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
        progress_path = _save_progress(
            run_id,
            "running",
            "activity_first_router",
            84.0,
            message="Activity-First Router läuft; bei 14/30-Tage-Smoke kann dieser Schritt länger dauern",
            started_at=started_at,
        )
        _emit_progress(
            progress_callback,
            "activity_first_router_started",
            84.0,
            "Activity-First Router läuft; bei 14/30-Tage-Smoke kann dieser Schritt länger dauern",
            run_id=run_id,
        )
        heartbeat_stop = _start_heartbeat_progress(
            run_id,
            progress_callback,
            started_at,
            "activity_first_router",
            84.0,
            88.5,
            "Activity-First Router prüft ETHUSDC-Kandidaten",
        )
        try:
            activity_first_router_report = build_activity_first_router_report(
                run_id,
                split,
                stake_quote_amount=stake_quote_amount,
                profile=profile,
                progress_callback=progress_callback,
            )
        finally:
            heartbeat_stop.set()
        activity_first_router_report.router_artifact["run_type"] = run_type
        activity_first_router_report.router_artifact["smoke_test_not_performance_proof"] = (
            run_type == "smoke_test"
        )
        activity_first_router_report.router_artifact["live_release_allowed"] = False
        activity_first_router_report_path = str(
            save_activity_first_router_report(activity_first_router_report)
        )
        _emit_progress(
            progress_callback,
            "activity_first_router_completed",
            89.0,
            "Activity-First Router abgeschlossen",
            run_id=run_id,
        )
        _emit_progress(
            progress_callback,
            "summary_started",
            90.0,
            "Reports werden gespeichert",
            run_id=run_id,
        )
        summary_path = str(save_backtest_summary(build_backtest_summary(run_id)))
        progress_path = _save_progress(run_id, "completed", "completed", 100.0, started_at=started_at)
        mark_backtest_run_completed(run_id)
        _emit_progress(
            progress_callback,
            "completed",
            100.0,
            "Backtest abgeschlossen",
            run_id=run_id,
        )
        return PreparationPipelineResult(
            run_id=run_id,
            status="completed",
            run_type=run_type,
            data_preparation_report_path=data_report_path,
            data_overview_report_path=data_overview_path,
            train_blind_split_report_path=split_report_path,
            activity_first_router_report_path=activity_first_router_report_path,
            backtest_summary_path=summary_path,
            progress_path=progress_path,
            error=None,
        )
    except Exception as error:  # noqa: BLE001
        error_message = str(error)
        if run_id:
            try:
                mark_backtest_run_failed(run_id, error_message)
                progress_path = _save_progress(
                    run_id,
                    "failed",
                    "failed",
                    100.0,
                    error=error_message,
                    started_at=locals().get("started_at"),
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
            run_id=run_id,
            status="failed",
            run_type=run_type,
            data_preparation_report_path=data_report_path,
            data_overview_report_path=data_overview_path,
            train_blind_split_report_path=split_report_path,
            activity_first_router_report_path=activity_first_router_report_path,
            backtest_summary_path=summary_path,
            progress_path=progress_path,
            error=error_message,
        )
