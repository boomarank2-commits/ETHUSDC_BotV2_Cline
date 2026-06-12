"""Technical report for train/blindtest candle splits."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.data.train_blind_split import TrainBlindSplit

TRAIN_BLIND_SPLIT_REPORT_FILENAME = "train_blind_split_report.json"


@dataclass(frozen=True)
class TrainBlindSplitReport:
    """Technical report describing training and blindtest candle windows."""

    run_id: str
    symbol: str
    interval: str
    training_candle_count: int
    blindtest_candle_count: int
    training_start: str
    training_end: str
    blindtest_start: str
    blindtest_end: str
    has_overlap: bool
    blindtest_after_training: bool

    def __post_init__(self) -> None:
        get_run_report_dir(self.run_id)


def _get_train_blind_split_report_path(run_id: str) -> Path:
    return get_run_report_dir(run_id) / TRAIN_BLIND_SPLIT_REPORT_FILENAME


def build_train_blind_split_report(run_id: str, split: TrainBlindSplit) -> TrainBlindSplitReport:
    """Build report data from an existing technical train/blind split."""
    get_run_report_dir(run_id)
    training_open_times = {candle.open_time for candle in split.training_candles}
    blindtest_open_times = {candle.open_time for candle in split.blindtest_candles}
    return TrainBlindSplitReport(
        run_id=run_id,
        symbol=split.symbol,
        interval=split.interval,
        training_candle_count=len(split.training_candles),
        blindtest_candle_count=len(split.blindtest_candles),
        training_start=split.training_start,
        training_end=split.training_end,
        blindtest_start=split.blindtest_start,
        blindtest_end=split.blindtest_end,
        has_overlap=bool(training_open_times.intersection(blindtest_open_times)),
        blindtest_after_training=split.training_end < split.blindtest_start,
    )


def save_train_blind_split_report(report: TrainBlindSplitReport) -> Path:
    """Save a train/blind split report as readable JSON."""
    report_dir = ensure_run_report_dir(report.run_id)
    report_path = report_dir / TRAIN_BLIND_SPLIT_REPORT_FILENAME
    content = json.dumps(asdict(report), indent=2, sort_keys=True)
    report_path.write_text(f"{content}\n", encoding="utf-8")
    return report_path


def load_train_blind_split_report(run_id: str) -> TrainBlindSplitReport:
    """Load and validate a train/blind split report."""
    raw_report: dict[str, Any] = json.loads(
        _get_train_blind_split_report_path(run_id).read_text(encoding="utf-8")
    )
    return TrainBlindSplitReport(**raw_report)
