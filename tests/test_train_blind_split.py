from dataclasses import replace

import pytest

import src.data.train_blind_split as split_module
from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle
from src.data.train_blind_split import (
    BLINDTEST_CANDLE_COUNT,
    BLINDTEST_DAYS,
    CANDLES_PER_DAY_1M,
    REQUIRED_CANDLE_COUNT,
    TRAINING_CANDLE_COUNT,
    TRAINING_DAYS,
    build_train_blind_split,
)


def _candle(index: int) -> Candle:
    return Candle(f"2026-01-01T00:{index:02d}:00", 100.0, 110.0, 90.0, 105.0, 1.0)


def _dataset(count: int, offset: int = 0) -> CandleDataset:
    return CandleDataset("ETHUSDC", "1m", [_candle(offset + index) for index in range(count)])


@pytest.fixture(autouse=True)
def small_split_constants(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(split_module, "TRAINING_CANDLE_COUNT", 3)
    monkeypatch.setattr(split_module, "BLINDTEST_CANDLE_COUNT", 2)
    monkeypatch.setattr(split_module, "REQUIRED_CANDLE_COUNT", 5)


def test_constants_match_730_365_and_1m() -> None:
    assert TRAINING_DAYS == 730
    assert BLINDTEST_DAYS == 365
    assert CANDLES_PER_DAY_1M == 24 * 60
    assert TRAINING_CANDLE_COUNT == 730 * 24 * 60
    assert BLINDTEST_CANDLE_COUNT == 365 * 24 * 60
    assert REQUIRED_CANDLE_COUNT == (730 + 365) * 24 * 60


def test_small_dataset_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_train_blind_split(_dataset(4))


def test_valid_dataset_creates_training_and_blindtest_lengths() -> None:
    split = build_train_blind_split(_dataset(5))

    assert len(split.training_candles) == 3
    assert len(split.blindtest_candles) == 2


def test_smoke_split_uses_two_to_one_training_blindtest_days(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(split_module, "CANDLES_PER_DAY_1M", 2)
    split = build_train_blind_split(_dataset(50), training_days=14, blindtest_days=7)

    assert len(split.training_candles) == 28
    assert len(split.blindtest_candles) == 14
    assert split.training_end < split.blindtest_start


def test_more_candles_uses_latest_required_candles() -> None:
    split = build_train_blind_split(_dataset(7))

    selected_candles = split.training_candles + split.blindtest_candles
    selected_open_times = [candle.open_time for candle in selected_candles]

    assert selected_open_times == [
        "2026-01-01T00:02:00",
        "2026-01-01T00:03:00",
        "2026-01-01T00:04:00",
        "2026-01-01T00:05:00",
        "2026-01-01T00:06:00",
    ]


def test_training_is_before_blindtest() -> None:
    split = build_train_blind_split(_dataset(5))

    assert split.training_end < split.blindtest_start


def test_no_overlap_between_training_and_blindtest() -> None:
    split = build_train_blind_split(_dataset(5))

    assert set(split.training_candles).isdisjoint(split.blindtest_candles)


def test_wrong_symbol_is_rejected() -> None:
    with pytest.raises(ValueError):
        dataset = replace(_dataset(5), symbol="BTCUSDC")
        build_train_blind_split(dataset)


def test_wrong_interval_is_rejected() -> None:
    with pytest.raises(ValueError):
        dataset = replace(_dataset(5), interval="5m")
        build_train_blind_split(dataset)
