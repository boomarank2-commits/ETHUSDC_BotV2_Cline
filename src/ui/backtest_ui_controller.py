"""UI controller for running the benchmark pipeline without UI dependencies."""

from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Callable

from src.backtest.preparation_pipeline import run_backtest_preparation_pipeline
from src.backtest.run_progress import load_run_progress
from src.common.report_paths import BACKTEST_REPORTS_DIR, get_run_report_dir
from src.common.runtime_state import load_runtime_state
from src.data.candle_data_ensure import ensure_ethusdc_1m_data_ready
from src.data.context_data_ensure import ensure_all_context_data_ready
from src.data.data_overview import load_data_overview_report
from src.data.exchange_info import ensure_exchange_info_current
from src.reports.backtest_summary import BacktestSummary, load_backtest_summary

ALLOWED_PROFILES = ("conservative", "normal", "aggressive")
ALLOWED_RUN_TYPES = ("full_backtest", "smoke_test")
ALLOWED_SMOKE_BLINDTEST_DAYS = (1, 7, 14, 30)
BINANCE_UNREACHABLE_MESSAGE = (
    "Binance konnte nicht erreicht werden. Internet/Firewall/Binance-Verbindung prüfen "
    "und später erneut versuchen."
)


@dataclass(frozen=True)
class BacktestUiSettings:
    """Validated UI settings for one backtest run."""

    stake_quote_amount: float = 100.0
    profile: str = "normal"
    run_type: str = "full_backtest"
    blindtest_days: int | None = None
    training_days: int | None = None

    def __post_init__(self) -> None:
        try:
            stake_quote_amount = float(self.stake_quote_amount)
        except (TypeError, ValueError) as error:
            msg = "stake_quote_amount must be numeric"
            raise ValueError(msg) from error
        if stake_quote_amount <= 0:
            msg = "stake_quote_amount must be positive"
            raise ValueError(msg)
        object.__setattr__(self, "stake_quote_amount", stake_quote_amount)
        if self.profile not in ALLOWED_PROFILES:
            msg = "profile must be conservative, normal or aggressive"
            raise ValueError(msg)
        if self.run_type not in ALLOWED_RUN_TYPES:
            msg = "run_type must be full_backtest or smoke_test"
            raise ValueError(msg)
        if self.run_type == "smoke_test":
            blindtest_days = 7 if self.blindtest_days is None else int(self.blindtest_days)
            if blindtest_days not in ALLOWED_SMOKE_BLINDTEST_DAYS:
                msg = "blindtest_days must be 1, 7, 14 or 30 for smoke_test"
                raise ValueError(msg)
            object.__setattr__(self, "blindtest_days", blindtest_days)
            object.__setattr__(self, "training_days", blindtest_days * 2 if self.training_days is None else int(self.training_days))
        else:
            object.__setattr__(self, "blindtest_days", None)
            object.__setattr__(self, "training_days", None)


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
    quote_per_day: float | None = None
    selected_family: str | None = None
    selected_candidate_name: str | None = None
    data_areas: list[dict] | None = None
    no_robust_positive_candidate: bool = False
    candidate_space_status: str | None = None
    best_final_training_score: float | None = None
    best_training_quote_per_day: float | None = None
    target_feasibility_status: str | None = None
    target_min_training_ratio: float | None = None
    progress_pct: float | None = None
    progress_stage: str | None = None
    elapsed_seconds: float | None = None
    estimated_remaining_seconds: float | None = None
    run_type: str = "full_backtest"


def _load_data_areas(run_id: str) -> list[dict] | None:
    try:
        report = load_data_overview_report(run_id)
    except FileNotFoundError:
        return None
    return [area.__dict__ for area in report.areas]


def _result_from_summary(summary: BacktestSummary, report_path: str) -> BacktestUiResult:
    progress_pct = None
    progress_stage = None
    elapsed_seconds = None
    estimated_remaining_seconds = None
    try:
        progress = load_run_progress(summary.run_id)
        progress_pct = progress.progress_pct
        progress_stage = progress.stage
        elapsed_seconds = progress.runtime_seconds
        estimated_remaining_seconds = progress.estimated_remaining_seconds
    except FileNotFoundError:
        pass
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
        quote_per_day=summary.quote_per_day,
        selected_family=summary.selected_family,
        selected_candidate_name=summary.selected_candidate_name,
        data_areas=_load_data_areas(summary.run_id),
        no_robust_positive_candidate=summary.no_robust_positive_candidate,
        candidate_space_status=summary.candidate_space_status,
        best_final_training_score=summary.best_final_training_score,
        best_training_quote_per_day=summary.best_training_quote_per_day,
        target_feasibility_status=summary.target_feasibility_status,
        target_min_training_ratio=summary.target_min_training_ratio,
        progress_pct=progress_pct,
        progress_stage=progress_stage,
        elapsed_seconds=elapsed_seconds,
        estimated_remaining_seconds=estimated_remaining_seconds,
        run_type=summary.run_type,
    )


def _load_run_result_if_summary_exists(run_id: str) -> BacktestUiResult | None:
    summary_path = get_run_report_dir(run_id) / "backtest_summary.json"
    if not summary_path.exists():
        return None
    return _result_from_summary(load_backtest_summary(run_id), str(summary_path))


def _load_running_run_result(run_id: str) -> BacktestUiResult | None:
    try:
        progress = load_run_progress(run_id)
    except FileNotFoundError:
        return None
    if progress.status != "running":
        return None
    report_dir = get_run_report_dir(run_id)
    elapsed_seconds = progress.runtime_seconds
    if elapsed_seconds is None:
        elapsed_seconds = max(0.0, time() - (report_dir / "run_request.json").stat().st_mtime)
    estimated_remaining_seconds = progress.estimated_remaining_seconds
    if estimated_remaining_seconds is None and 0 < progress.progress_pct < 100:
        estimated_total_seconds = elapsed_seconds / (progress.progress_pct / 100)
        estimated_remaining_seconds = max(0.0, estimated_total_seconds - elapsed_seconds)
    detail_parts = [f"Backtest läuft: {progress.stage} ({progress.progress_pct:.1f}%)"]
    if progress.message:
        detail_parts.append(progress.message)
    detail_parts.append(f"Laufzeit: {_format_duration(elapsed_seconds)}")
    if estimated_remaining_seconds is not None:
        detail_parts.append(f"Rest geschätzt: {_format_duration(estimated_remaining_seconds)}")
    return BacktestUiResult(
        success=False,
        run_id=run_id,
        status="running",
        message=" | ".join(detail_parts),
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
        report_path=str(report_dir / "progress.json"),
        report_folder=str(report_dir),
        data_areas=_load_data_areas(run_id),
        progress_pct=progress.progress_pct,
        progress_stage=progress.stage,
        elapsed_seconds=elapsed_seconds,
        estimated_remaining_seconds=estimated_remaining_seconds,
    )


def _format_duration(seconds: float) -> str:
    whole_seconds = int(max(0.0, seconds))
    hours, remainder = divmod(whole_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}m {secs:02d}s"
    return f"{minutes:d}m {secs:02d}s"


def _find_latest_run_id_with_summary() -> str | None:
    if not BACKTEST_REPORTS_DIR.exists():
        return None
    candidates = [
        run_dir.name
        for run_dir in BACKTEST_REPORTS_DIR.iterdir()
        if run_dir.is_dir() and (run_dir / "backtest_summary.json").exists()
    ]
    if not candidates:
        return None
    return sorted(candidates)[-1]


def load_latest_completed_backtest_result_for_ui() -> BacktestUiResult | None:
    """Load the newest completed run that already has a summary."""
    latest_run_id = _find_latest_run_id_with_summary()
    if latest_run_id is None:
        return None
    return _load_run_result_if_summary_exists(latest_run_id)


def load_active_backtest_result_for_ui() -> BacktestUiResult | None:
    """Load the active/last run from runtime_state.json for UI display only."""
    runtime_state = load_runtime_state()
    if runtime_state.active_run_id is not None:
        active_result = _load_run_result_if_summary_exists(runtime_state.active_run_id)
        if active_result is not None:
            return active_result
        if runtime_state.status == "running":
            running_result = _load_running_run_result(runtime_state.active_run_id)
            if running_result is not None:
                return running_result

    return load_latest_completed_backtest_result_for_ui()


def _failure_result(message: str, candle_count: int | None = None, run_type: str = "full_backtest") -> BacktestUiResult:
    return BacktestUiResult(
        success=False,
        run_id=None,
        status="failed",
        message=message,
        symbol=None,
        start_capital=None,
        final_capital=None,
        total_pnl=None,
        total_pnl_pct=None,
        trade_count=None,
        candle_count=candle_count,
        detected_gaps=None,
        usable_for_backtest=False,
        training_start=None,
        training_end=None,
        blindtest_start=None,
        blindtest_end=None,
        report_path=None,
        report_folder=None,
        run_type=run_type,
    )


def _is_network_error(message: str) -> bool:
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in (
            "binance request error",
            "winerror 10060",
            "timed out",
            "timeout",
            "connection",
            "verbindungsversuch",
        )
    )


def _ui_error_message(message: str) -> str:
    if _is_network_error(message):
        return BINANCE_UNREACHABLE_MESSAGE
    return message


def _context_failure_message(results: list[object]) -> str | None:
    failed = [result for result in results if not getattr(result, "success", False)]
    if not failed:
        return None
    details = "; ".join(
        f"{getattr(result, 'symbol', 'context')}: {getattr(result, 'message', getattr(result, 'error', 'unknown'))}"
        for result in failed
    )
    return f"Kontextdaten fehlen/unvollständig, Kontextfilter nicht aktiv. Backtest wurde nicht gestartet: {details}"


def run_backtest_for_ui(
    settings: BacktestUiSettings | None = None,
    progress_callback: Callable[[dict], None] | None = None,
) -> BacktestUiResult:
    """Run the existing benchmark pipeline and return a UI-friendly result."""
    try:
        selected_settings = settings or BacktestUiSettings()
        if progress_callback is not None:
            progress_callback({"phase": "data_check_started", "progress_pct": 0.0})
        ensure_result = ensure_ethusdc_1m_data_ready(progress_callback=progress_callback)
        if not ensure_result.success:
            return _failure_result(
                _ui_error_message(ensure_result.message),
                candle_count=ensure_result.candle_count,
                run_type=selected_settings.run_type,
            )
        context_results = ensure_all_context_data_ready(progress_callback=progress_callback)
        context_failure = _context_failure_message(context_results)
        if context_failure is not None:
            return _failure_result(_ui_error_message(context_failure), run_type=selected_settings.run_type)
        exchange_status = ensure_exchange_info_current()
        if not exchange_status.usable_for_backtest:
            return _failure_result(_ui_error_message(f"exchange_info nicht nutzbar: {exchange_status.reason}"), run_type=selected_settings.run_type)
        pipeline_result = run_backtest_preparation_pipeline(
            stake_quote_amount=selected_settings.stake_quote_amount,
            profile=selected_settings.profile,
            run_type=selected_settings.run_type,
            blindtest_days=selected_settings.blindtest_days,
            training_days=selected_settings.training_days,
            progress_callback=progress_callback,
        )
        if pipeline_result.backtest_summary_path:
            summary = load_backtest_summary(pipeline_result.run_id)
            result = _result_from_summary(summary, pipeline_result.backtest_summary_path)
            message = (
                f"{result.message} | Stake: {selected_settings.stake_quote_amount:.0f} USDC | "
                f"Profil: {selected_settings.profile} | Run-Type: {selected_settings.run_type}"
            )
            return BacktestUiResult(
                **{
                    **result.__dict__,
                    "message": message,
                }
            )
        return BacktestUiResult(
            success=False,
            run_id=pipeline_result.run_id or None,
            status=pipeline_result.status,
            message=_ui_error_message(
                pipeline_result.error or "backtest pipeline failed without summary"
            ),
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
        message = _ui_error_message(str(error))
        return BacktestUiResult(
            success=False,
            run_id=None,
            status="failed",
            message=message,
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
