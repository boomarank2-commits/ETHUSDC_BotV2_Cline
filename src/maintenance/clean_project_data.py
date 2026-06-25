"""Clean downloaded/runtime data while preserving source code and project structure."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from src.common.paths import CONFIGS_DIR, DATA_DIR, LOGS_DIR, REPORTS_DIR
from src.common.runtime_state import default_runtime_state, save_runtime_state
from src.data.data_catalog import save_data_catalog
from src.data.live_microstructure import request_live_microstructure_collector_stop


@dataclass(frozen=True)
class CleanProjectDataResult:
    deleted_paths: list[str]
    kept_paths: list[str]
    message: str


def _delete_children(directory: Path, deleted: list[str]) -> None:
    if not directory.exists():
        return
    for child in directory.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        deleted.append(str(child))


def clean_downloaded_data_and_reports() -> CleanProjectDataResult:
    """Delete downloaded market data and reports; keep code/config folders/memory/docs/tests."""
    deleted: list[str] = []
    kept = [str(CONFIGS_DIR), str(DATA_DIR), str(REPORTS_DIR)]
    request_live_microstructure_collector_stop()
    _delete_children(DATA_DIR / "candles", deleted)
    for optional_dir in (
        DATA_DIR / "realtime",
        DATA_DIR / "live",
        DATA_DIR / "microstructure",
        DATA_DIR / "live_microstructure",
        DATA_DIR / "agg_trades",
        DATA_DIR / "market_features",
        DATA_DIR / "trades",
        DATA_DIR / "exchange_info",
    ):
        _delete_children(optional_dir, deleted)
    _delete_children(REPORTS_DIR / "backtests", deleted)
    if LOGS_DIR.exists():
        for log_path in LOGS_DIR.glob("*backtest*"):
            if log_path.is_dir():
                shutil.rmtree(log_path)
            else:
                log_path.unlink()
            deleted.append(str(log_path))
        for log_path in LOGS_DIR.glob("*download*"):
            if log_path.exists():
                if log_path.is_dir():
                    shutil.rmtree(log_path)
                else:
                    log_path.unlink()
                deleted.append(str(log_path))
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    save_data_catalog([])
    save_runtime_state(default_runtime_state())
    return CleanProjectDataResult(
        deleted_paths=deleted,
        kept_paths=kept,
        message="Clean-Zustand: Beim nächsten Backtest werden Daten neu geladen.",
    )
