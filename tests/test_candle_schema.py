import pytest

from src.data.candle_schema import Candle


def test_valid_candle_is_accepted() -> None:
    candle = Candle("2026-01-01T00:00:00Z", 100.0, 110.0, 90.0, 105.0, 0.0)

    assert candle.close == 105.0


@pytest.mark.parametrize("field_name", ["open", "high", "low", "close"])
def test_negative_prices_are_rejected(field_name: str) -> None:
    values = {
        "open_time": "2026-01-01T00:00:00Z",
        "open": 100.0,
        "high": 110.0,
        "low": 90.0,
        "close": 105.0,
        "volume": 1.0,
    }
    values[field_name] = -1.0

    with pytest.raises(ValueError):
        Candle(**values)


def test_negative_volume_is_rejected() -> None:
    with pytest.raises(ValueError):
        Candle("2026-01-01T00:00:00Z", 100.0, 110.0, 90.0, 105.0, -1.0)


@pytest.mark.parametrize(
    "field_name",
    [
        "quote_volume",
        "trade_count",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
    ],
)
def test_negative_order_flow_fields_are_rejected(field_name: str) -> None:
    values = {
        "open_time": "2026-01-01T00:00:00Z",
        "open": 100.0,
        "high": 110.0,
        "low": 90.0,
        "close": 105.0,
        "volume": 1.0,
        field_name: -1,
    }

    with pytest.raises(ValueError):
        Candle(**values)


def test_high_under_close_or_open_is_rejected() -> None:
    with pytest.raises(ValueError):
        Candle("2026-01-01T00:00:00Z", 100.0, 99.0, 90.0, 105.0, 1.0)


def test_low_over_close_or_open_is_rejected() -> None:
    with pytest.raises(ValueError):
        Candle("2026-01-01T00:00:00Z", 100.0, 110.0, 106.0, 105.0, 1.0)


def test_empty_open_time_is_rejected() -> None:
    with pytest.raises(ValueError):
        Candle("", 100.0, 110.0, 90.0, 105.0, 1.0)
