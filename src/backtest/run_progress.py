"""Technical progress persistence for future backtest runs."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.common.report_paths import ensure_run_report_dir, get_run_report_dir

PROGRESS_FILENAME = "progress.json"
ALLOWED_PROGRESS_STATUSES = frozenset({"initialized", "running", "completed", "failed"})


@dataclass(frozen=True)
class BacktestRunProgress:
    """Technical progress state for a future backtest run."""

    run_id: str
    status: str
    stage: str
    progress_pct: float
    message: str | None
    error: str | None

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
    """Save run progress as readable JSON."""
    report_dir = ensure_run_report_dir(progress.run_id)
    progress_path = report_dir / PROGRESS_FILENAME
    content = json.dumps(asdict(progress), indent=2, sort_keys=True)
    progress_path.write_text(f"{content}\n", encoding="utf-8")
    return progress_path


def load_run_progress(run_id: str) -> BacktestRunProgress:
    """Load run progress from JSON and validate it."""
    raw_progress: dict[str, Any] = json.loads(
        _get_progress_path(run_id).read_text(encoding="utf-8")
    )
    return BacktestRunProgress(**raw_progress)
