"""Technical report path helpers."""

import re
from pathlib import Path

from src.common.paths import REPORTS_DIR

_SAFE_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
BACKTEST_REPORTS_DIR = REPORTS_DIR / "backtests"


def _validate_run_id(run_id: str) -> None:
    if not run_id:
        msg = "run_id must not be empty"
        raise ValueError(msg)

    if not _SAFE_RUN_ID_PATTERN.fullmatch(run_id):
        msg = "run_id may contain only letters, numbers and underscores"
        raise ValueError(msg)

    run_path = Path(run_id)
    if run_path.name != run_id:
        msg = "run_id must not contain path separators"
        raise ValueError(msg)


def get_run_report_dir(run_id: str) -> Path:
    """Return the report directory for a run id without creating it."""
    _validate_run_id(run_id)
    return BACKTEST_REPORTS_DIR / run_id


def ensure_run_report_dir(run_id: str) -> Path:
    """Create and return the report directory for a run id."""
    report_dir = get_run_report_dir(run_id)
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir
