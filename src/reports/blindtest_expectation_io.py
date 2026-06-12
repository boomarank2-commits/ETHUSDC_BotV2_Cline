"""JSON IO helpers for blindtest expectation reports."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.reports.blindtest_expectation_schema import (
    BlindtestExpectationSummary,
    MonthlyBlindtestResult,
)

BLINDTEST_EXPECTATION_FILENAME = "blindtest_expectation.json"


def _get_blindtest_expectation_path(run_id: str) -> Path:
    return get_run_report_dir(run_id) / BLINDTEST_EXPECTATION_FILENAME


def save_blindtest_expectation(run_id: str, summary: BlindtestExpectationSummary) -> Path:
    """Save a blindtest expectation summary as readable JSON."""
    report_dir = ensure_run_report_dir(run_id)
    report_path = report_dir / BLINDTEST_EXPECTATION_FILENAME
    content = json.dumps(asdict(summary), indent=2, sort_keys=True)
    report_path.write_text(f"{content}\n", encoding="utf-8")
    return report_path


def load_blindtest_expectation(run_id: str) -> BlindtestExpectationSummary:
    """Load a blindtest expectation summary from JSON and validate the schema."""
    report_path = _get_blindtest_expectation_path(run_id)
    raw_summary: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    monthly_results = [
        MonthlyBlindtestResult(**raw_monthly_result)
        for raw_monthly_result in raw_summary.get("monthly_results", [])
    ]
    raw_summary["monthly_results"] = monthly_results
    return BlindtestExpectationSummary(**raw_summary)
