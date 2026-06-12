"""Technical quality report for candle datasets."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.common.config import CONFIG
from src.data.candle_dataset import CandleDataset

EXPECTED_MIN_CANDLES = (CONFIG.training_days + CONFIG.blindtest_days) * 24 * 60


@dataclass(frozen=True)
class CandleQualityReport:
    """Technical quality summary for a candle dataset."""

    symbol: str
    interval: str
    candle_count: int
    first_open_time: str
    last_open_time: str
    duplicate_open_times: int
    sorted_ascending: bool
    detected_gaps: int
    expected_min_candles: int
    has_required_lookback: bool


def _parse_open_time(open_time: str) -> datetime:
    try:
        return datetime.fromisoformat(open_time.replace("Z", "+00:00"))
    except ValueError as error:
        msg = f"open_time is not parseable: {open_time}"
        raise ValueError(msg) from error


def build_candle_quality_report(
    dataset: CandleDataset,
    expected_min_candles: int = EXPECTED_MIN_CANDLES,
) -> CandleQualityReport:
    """Build a technical candle quality report without trading or backtest logic."""
    open_times = [candle.open_time for candle in dataset.candles]
    parsed_times = [_parse_open_time(open_time) for open_time in open_times]
    duplicate_open_times = len(open_times) - len(set(open_times))
    sorted_ascending = open_times == sorted(open_times)

    detected_gaps = 0
    expected_delta = timedelta(minutes=1)
    for previous_time, current_time in zip(parsed_times, parsed_times[1:], strict=False):
        if current_time - previous_time > expected_delta:
            detected_gaps += 1

    return CandleQualityReport(
        symbol=dataset.symbol,
        interval=dataset.interval,
        candle_count=len(dataset.candles),
        first_open_time=open_times[0],
        last_open_time=open_times[-1],
        duplicate_open_times=duplicate_open_times,
        sorted_ascending=sorted_ascending,
        detected_gaps=detected_gaps,
        expected_min_candles=expected_min_candles,
        has_required_lookback=len(dataset.candles) >= expected_min_candles,
    )
