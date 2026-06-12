"""Technical finalization for future backtest runs."""

from src.common.report_paths import ensure_run_report_dir
from src.common.runtime_state import RuntimeState, load_runtime_state, save_runtime_state


def mark_backtest_run_completed(run_id: str) -> None:
    """Mark a backtest run as completed without calculating results."""
    ensure_run_report_dir(run_id)
    load_runtime_state()
    save_runtime_state(RuntimeState(active_run_id=run_id, status="completed", last_error=None))


def mark_backtest_run_failed(run_id: str, error: str) -> None:
    """Mark a backtest run as failed without calculating results."""
    if not error:
        msg = "error must not be empty"
        raise ValueError(msg)

    ensure_run_report_dir(run_id)
    save_runtime_state(RuntimeState(active_run_id=run_id, status="failed", last_error=error))
