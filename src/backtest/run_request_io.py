"""JSON IO helpers for backtest run requests."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.backtest.run_request import BacktestRunRequest
from src.common.report_paths import ensure_run_report_dir, get_run_report_dir

RUN_REQUEST_FILENAME = "run_request.json"


def _get_run_request_path(run_id: str) -> Path:
    return get_run_report_dir(run_id) / RUN_REQUEST_FILENAME


def save_backtest_run_request(request: BacktestRunRequest) -> Path:
    """Save a backtest run request as readable JSON."""
    report_dir = ensure_run_report_dir(request.run_id)
    report_path = report_dir / RUN_REQUEST_FILENAME
    content = json.dumps(asdict(request), indent=2, sort_keys=True)
    report_path.write_text(f"{content}\n", encoding="utf-8")
    return report_path


def load_backtest_run_request(run_id: str) -> BacktestRunRequest:
    """Load a backtest run request from JSON and validate the schema."""
    report_path = _get_run_request_path(run_id)
    raw_request: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    return BacktestRunRequest(**raw_request)
