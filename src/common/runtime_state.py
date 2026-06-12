"""Technical runtime state persistence."""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.common.paths import CONFIGS_DIR

RUNTIME_STATE_PATH = CONFIGS_DIR / "runtime_state.json"
ALLOWED_RUNTIME_STATUSES = frozenset({"idle", "running", "completed", "failed"})
_SAFE_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


@dataclass(frozen=True)
class RuntimeState:
    """Current technical runtime state."""

    active_run_id: str | None
    status: str
    last_error: str | None

    def __post_init__(self) -> None:
        _validate_status(self.status)
        _validate_active_run_id(self.active_run_id)


def _validate_status(status: str) -> None:
    if status not in ALLOWED_RUNTIME_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_RUNTIME_STATUSES))
        msg = f"status must be one of: {allowed}"
        raise ValueError(msg)


def _validate_active_run_id(active_run_id: str | None) -> None:
    if active_run_id is None:
        return

    if not active_run_id:
        msg = "active_run_id must not be empty"
        raise ValueError(msg)

    if not _SAFE_RUN_ID_PATTERN.fullmatch(active_run_id):
        msg = "active_run_id may contain only letters, numbers and underscores"
        raise ValueError(msg)

    run_path = Path(active_run_id)
    if run_path.name != active_run_id:
        msg = "active_run_id must not contain path separators"
        raise ValueError(msg)


def default_runtime_state() -> RuntimeState:
    """Return the default idle runtime state."""
    return RuntimeState(active_run_id=None, status="idle", last_error=None)


def save_runtime_state(state: RuntimeState) -> None:
    """Save the runtime state as readable JSON."""
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    content = json.dumps(asdict(state), indent=2, sort_keys=True)
    RUNTIME_STATE_PATH.write_text(f"{content}\n", encoding="utf-8")


def load_runtime_state() -> RuntimeState:
    """Load the runtime state, or return the default state when no file exists."""
    if not RUNTIME_STATE_PATH.exists():
        return default_runtime_state()

    raw_state: dict[str, Any] = json.loads(RUNTIME_STATE_PATH.read_text(encoding="utf-8"))
    return RuntimeState(
        active_run_id=raw_state.get("active_run_id"),
        status=raw_state.get("status", "idle"),
        last_error=raw_state.get("last_error"),
    )
