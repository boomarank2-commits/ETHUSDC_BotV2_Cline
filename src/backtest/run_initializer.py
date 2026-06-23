"""Technical initialization for future backtest runs."""

from dataclasses import replace

from src.backtest.run_request import BacktestRunRequest, default_backtest_run_request
from src.backtest.run_request_io import save_backtest_run_request
from src.common.report_paths import ensure_run_report_dir
from src.common.run_identity import create_run_id
from src.common.runtime_state import RuntimeState, save_runtime_state


def initialize_backtest_run(
    time_budget_minutes: int | None = None,
    run_type: str = "full_backtest",
    training_days: int | None = None,
    blindtest_days: int | None = None,
) -> BacktestRunRequest:
    """Initialize technical files for a future backtest run without executing it."""
    run_id = create_run_id()
    request = default_backtest_run_request(
        run_id,
        run_type=run_type,
        training_days=training_days,
        blindtest_days=blindtest_days,
    )
    if time_budget_minutes is not None:
        request = replace(request, time_budget_minutes=time_budget_minutes)

    ensure_run_report_dir(run_id)
    save_backtest_run_request(request)
    save_runtime_state(RuntimeState(active_run_id=run_id, status="running", last_error=None))
    return request
