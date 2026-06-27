"""Technical progress persistence for future backtest runs."""

import json
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from time import sleep
from typing import Any
from uuid import uuid4

from src.common.report_paths import ensure_run_report_dir, get_run_report_dir

PROGRESS_FILENAME = "progress.json"
ALLOWED_PROGRESS_STATUSES = frozenset({"initialized", "running", "completed", "failed"})
WINDOWS_REPLACE_RETRY_DELAYS_SECONDS = (0.02, 0.05, 0.10, 0.20, 0.40, 0.80)


@dataclass(frozen=True)
class BacktestRunProgress:
    """Technical progress state for a future backtest run."""

    run_id: str
    status: str
    stage: str
    progress_pct: float
    message: str | None
    error: str | None
    runtime_seconds: float | None = None
    estimated_remaining_seconds: float | None = None

    def __post_init__(self) -> None:
        get_run_report_dir(self.run_id)
        if self.status not in ALLOWED_PROGRESS_STATUSES:
            allowed = ", ".join(sorted(ALLOWED_PROGRESS_STATUSES))
            msg = f"status must be one of: {allowed}"
            raise ValueError(msg)
        if not 0 <= self.progress_pct <= 100:
            msg = "progress_pct must be between 0 and 100"
            raise ValueError(msg)


def _get_progress_path(run_id: str) -> Path:
    return get_run_report_dir(run_id) / PROGRESS_FILENAME


def default_run_progress(run_id: str) -> BacktestRunProgress:
    """Create default initialized progress for a run."""
    return BacktestRunProgress(
        run_id=run_id,
        status="initialized",
        stage="initialized",
        progress_pct=0.0,
        message=None,
        error=None,
    )


def save_run_progress(progress: BacktestRunProgress) -> Path:
    """Save progress atomically so UI refreshes never observe partial JSON.

    Windows can briefly deny ``os.replace`` while the Tk UI, antivirus, or another
    writer has the current ``progress.json`` open.  Use a unique temp file per
    write and retry the replace instead of letting the heartbeat thread die.
    """
    report_dir = ensure_run_report_dir(progress.run_id)
    progress_path = report_dir / PROGRESS_FILENAME
    temp_path = progress_path.with_name(f"{progress_path.name}.{uuid4().hex}.tmp")
    content = json.dumps(asdict(progress), indent=2, sort_keys=True)
    temp_path.write_text(f"{content}\n", encoding="utf-8")
    last_error: PermissionError | None = None
    try:
        for delay_seconds in (0.0, *WINDOWS_REPLACE_RETRY_DELAYS_SECONDS):
            if delay_seconds:
                sleep(delay_seconds)
            try:
                temp_path.replace(progress_path)
                return progress_path
            except PermissionError as error:
                last_error = error
        if last_error is not None:
            raise last_error
        return progress_path
    finally:
        with suppress(OSError):
            temp_path.unlink()


def load_run_progress(run_id: str) -> BacktestRunProgress:
    """Load run progress from JSON and validate it."""
    raw_progress: dict[str, Any] = json.loads(
        _get_progress_path(run_id).read_text(encoding="utf-8")
    )
    return BacktestRunProgress(**raw_progress)
