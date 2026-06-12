"""Technical data preparation report for local candle data."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.data.local_candle_loader import build_local_candle_quality_from_catalog

DATA_PREPARATION_REPORT_FILENAME = "data_preparation_report.json"


@dataclass(frozen=True)
class DataPreparationReport:
    """Technical report describing local candle data readiness."""

    run_id: str
    symbol: str
    interval: str
    candle_count: int
    first_open_time: str
    last_open_time: str
    detected_gaps: int
    has_required_lookback: bool
    usable_for_backtest: bool
    reason: str | None

    def __post_init__(self) -> None:
        get_run_report_dir(self.run_id)


def _get_data_preparation_report_path(run_id: str) -> Path:
    return get_run_report_dir(run_id) / DATA_PREPARATION_REPORT_FILENAME


def _build_unusable_reason(has_required_lookback: bool, detected_gaps: int) -> str | None:
    reasons: list[str] = []
    if not has_required_lookback:
        reasons.append("not enough candles for required lookback")
    if detected_gaps != 0:
        reasons.append("detected candle time gaps")
    if not reasons:
        return None
    return "; ".join(reasons)


def build_data_preparation_report(run_id: str) -> DataPreparationReport:
    """Build a technical data preparation report without backtest calculation."""
    get_run_report_dir(run_id)
    quality = build_local_candle_quality_from_catalog()
    usable_for_backtest = quality.has_required_lookback and quality.detected_gaps == 0
    return DataPreparationReport(
        run_id=run_id,
        symbol=quality.symbol,
        interval=quality.interval,
        candle_count=quality.candle_count,
        first_open_time=quality.first_open_time,
        last_open_time=quality.last_open_time,
        detected_gaps=quality.detected_gaps,
        has_required_lookback=quality.has_required_lookback,
        usable_for_backtest=usable_for_backtest,
        reason=_build_unusable_reason(quality.has_required_lookback, quality.detected_gaps),
    )


def save_data_preparation_report(report: DataPreparationReport) -> Path:
    """Save a data preparation report as readable JSON."""
    report_dir = ensure_run_report_dir(report.run_id)
    report_path = report_dir / DATA_PREPARATION_REPORT_FILENAME
    content = json.dumps(asdict(report), indent=2, sort_keys=True)
    report_path.write_text(f"{content}\n", encoding="utf-8")
    return report_path


def load_data_preparation_report(run_id: str) -> DataPreparationReport:
    """Load and validate a data preparation report."""
    raw_report: dict[str, Any] = json.loads(
        _get_data_preparation_report_path(run_id).read_text(encoding="utf-8")
    )
    return DataPreparationReport(**raw_report)
