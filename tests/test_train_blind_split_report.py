import pytest

from src.common.report_paths import get_run_report_dir
from src.data.candle_schema import Candle
from src.data.train_blind_split import TrainBlindSplit
from src.data.train_blind_split_report import (
    TRAIN_BLIND_SPLIT_REPORT_FILENAME,
    build_train_blind_split_report,
    load_train_blind_split_report,
    save_train_blind_split_report,
)


def _candle(open_time: str) -> Candle:
    return Candle(open_time, 100.0, 110.0, 90.0, 105.0, 1.0)


def _split() -> TrainBlindSplit:
    training_candles = [_candle("2026-01-01T00:00:00"), _candle("2026-01-01T00:01:00")]
    blindtest_candles = [_candle("2026-01-01T00:02:00")]
    return TrainBlindSplit(
        symbol="ETHUSDC",
        interval="1m",
        training_candles=training_candles,
        blindtest_candles=blindtest_candles,
        training_start=training_candles[0].open_time,
        training_end=training_candles[-1].open_time,
        blindtest_start=blindtest_candles[0].open_time,
        blindtest_end=blindtest_candles[-1].open_time,
    )


def test_report_is_created_from_valid_split() -> None:
    report = build_train_blind_split_report("run_20260612_190001", _split())

    assert report.symbol == "ETHUSDC"
    assert report.interval == "1m"


def test_training_and_blindtest_counts_match() -> None:
    report = build_train_blind_split_report("run_20260612_190002", _split())

    assert report.training_candle_count == 2
    assert report.blindtest_candle_count == 1


def test_clean_split_has_no_overlap() -> None:
    report = build_train_blind_split_report("run_20260612_190003", _split())

    assert report.has_overlap is False


def test_clean_split_has_blindtest_after_training() -> None:
    report = build_train_blind_split_report("run_20260612_190004", _split())

    assert report.blindtest_after_training is True


def test_report_is_saved_in_run_report_dir() -> None:
    report = build_train_blind_split_report("run_20260612_190005", _split())

    report_path = save_train_blind_split_report(report)

    assert report_path == get_run_report_dir(report.run_id) / TRAIN_BLIND_SPLIT_REPORT_FILENAME


def test_load_reads_same_report() -> None:
    report = build_train_blind_split_report("run_20260612_190006", _split())
    save_train_blind_split_report(report)

    assert load_train_blind_split_report(report.run_id) == report


def test_invalid_run_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_train_blind_split_report("../unsafe", _split())


def test_artificial_overlap_is_detected() -> None:
    split = _split()
    overlap_candle = split.training_candles[-1]
    overlap_split = TrainBlindSplit(
        symbol=split.symbol,
        interval=split.interval,
        training_candles=split.training_candles,
        blindtest_candles=[overlap_candle],
        training_start=split.training_start,
        training_end=split.training_end,
        blindtest_start=overlap_candle.open_time,
        blindtest_end=overlap_candle.open_time,
    )

    report = build_train_blind_split_report("run_20260612_190007", overlap_split)
    assert report.has_overlap is True


def test_blindtest_not_after_training_is_reported() -> None:
    split = _split()
    bad_split = TrainBlindSplit(
        symbol=split.symbol,
        interval=split.interval,
        training_candles=split.training_candles,
        blindtest_candles=split.blindtest_candles,
        training_start=split.training_start,
        training_end="2026-01-01T00:03:00",
        blindtest_start=split.blindtest_start,
        blindtest_end=split.blindtest_end,
    )

    report = build_train_blind_split_report("run_20260612_190008", bad_split)
    assert report.blindtest_after_training is False
