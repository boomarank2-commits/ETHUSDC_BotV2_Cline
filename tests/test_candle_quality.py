import pytest

from src.data.candle_dataset import CandleDataset
from src.data.candle_quality import EXPECTED_MIN_CANDLES, build_candle_quality_report
from src.data.candle_schema import Candle


def _candle(open_time: str) -> Candle:
    return Candle(open_time, 100.0, 110.0, 90.0, 105.0, 1.0)


def _dataset(open_times: list[str]) -> CandleDataset:
    return CandleDataset("ETHUSDC", "1m", [_candle(open_time) for open_time in open_times])


def test_gap_free_dataset_has_zero_detected_gaps() -> None:
    dataset = _dataset(["2026-01-01T00:00:00", "2026-01-01T00:01:00"])

    report = build_candle_quality_report(dataset)

    assert report.detected_gaps == 0


def test_duplicate_open_times_are_rejected_by_dataset_validation() -> None:
    with pytest.raises(ValueError):
        _dataset(["2026-01-01T00:00:00", "2026-01-01T00:00:00"])


def test_unsorted_open_times_are_rejected_by_dataset_validation() -> None:
    with pytest.raises(ValueError):
        _dataset(["2026-01-01T00:01:00", "2026-01-01T00:00:00"])


def test_one_minute_gap_is_detected() -> None:
    dataset = _dataset(["2026-01-01T00:00:00", "2026-01-01T00:02:00"])

    report = build_candle_quality_report(dataset)

    assert report.detected_gaps == 1


def test_has_required_lookback_is_false_for_small_dataset() -> None:
    dataset = _dataset(["2026-01-01T00:00:00"])

    report = build_candle_quality_report(dataset)

    assert report.has_required_lookback is False


def test_has_required_lookback_is_true_for_large_dataset() -> None:
    dataset = _dataset(["2026-01-01T00:00:00", "2026-01-01T00:01:00"])

    report = build_candle_quality_report(dataset, expected_min_candles=2)

    assert report.has_required_lookback is True


def test_expected_min_candles_keeps_confirmed_730_365_rule() -> None:
    assert EXPECTED_MIN_CANDLES == (730 + 365) * 24 * 60


def test_unparseable_open_time_is_rejected() -> None:
    dataset = _dataset(["not-a-date"])

    with pytest.raises(ValueError):
        build_candle_quality_report(dataset)
