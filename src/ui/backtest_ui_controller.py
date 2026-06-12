"""UI controller for running the benchmark pipeline without UI dependencies."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.backtest.preparation_pipeline import run_backtest_preparation_pipeline
from src.data.candle_data_ensure import ensure_ethusdc_1m_data_ready
from src.reports.backtest_summary import BacktestSummary, load_backtest_summary

ALLOWED_PROFILES = ("conservative", "normal", "aggressive")
BINANCE_UNREACHABLE_MESSAGE = (
    "Binance konnte nicht erreicht werden. Internet/Firewall/Binance-Verbindung prüfen "
    "und später erneut versuchen."
)


@dataclass(frozen=True)
class BacktestUiSettings:
    """Validated UI settings for one backtest run."""

    stake_usdt: float = 100.0
    profile: str = "normal"

    def __post_init__(self) -> None:
        if self.stake_usdt <= 0:
            msg = "stake_usdt must be positive"
            raise ValueError(msg)
        if self.profile not in ALLOWED_PROFILES:
            msg = "profile must be conservative, normal or aggressive"
            raise ValueError(msg)


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


def _failure_result(message: str, candle_count: int | None = None) -> BacktestUiResult:
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
            )
        pipeline_result = run_backtest_preparation_pipeline(
            stake_usdt=selected_settings.stake_usdt,
            profile=selected_settings.profile,
            progress_callback=progress_callback,
        )
        if pipeline_result.backtest_summary_path:
            summary = load_backtest_summary(pipeline_result.run_id)
            result = _result_from_summary(summary, pipeline_result.backtest_summary_path)
            message = (
                f"{result.message} | Stake: {selected_settings.stake_usdt:.0f} USDT | "
                f"Profil: {selected_settings.profile}"
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
