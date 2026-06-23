import pytest

from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle


def _candle(open_time: str) -> Candle:
    return Candle(open_time, 100.0, 110.0, 90.0, 105.0, 1.0)


def test_valid_ethusdc_1m_dataset_is_accepted() -> None:
    dataset = CandleDataset("ETHUSDC", "1m", [_candle("2026-01-01T00:00:00Z")])

    assert dataset.symbol == "ETHUSDC"


def test_wrong_symbol_is_rejected() -> None:
    with pytest.raises(ValueError):
        CandleDataset("XRPUSDC", "1m", [_candle("2026-01-01T00:00:00Z")])


def test_wrong_interval_is_rejected() -> None:
    with pytest.raises(ValueError):
        CandleDataset("ETHUSDC", "5m", [_candle("2026-01-01T00:00:00Z")])


def test_empty_candles_are_rejected() -> None:
    with pytest.raises(ValueError):
        CandleDataset("ETHUSDC", "1m", [])


def test_duplicate_open_time_is_rejected() -> None:
    with pytest.raises(ValueError):
        CandleDataset(
            "ETHUSDC",
            "1m",
            [_candle("2026-01-01T00:00:00Z"), _candle("2026-01-01T00:00:00Z")],
        )


def test_unsorted_open_time_is_rejected() -> None:
    with pytest.raises(ValueError):
        CandleDataset(
            "ETHUSDC",
            "1m",
            [_candle("2026-01-01T00:01:00Z"), _candle("2026-01-01T00:00:00Z")],
        )
