from datetime import datetime, timedelta

from src.data.candle_schema import Candle
from src.data.derived_timeframes import build_derived_timeframe_counts, derive_closed_timeframe_candles


def _minute_candles(count: int, start: str = "2026-01-01T00:00:00") -> list[Candle]:
    start_time = datetime.fromisoformat(start)
    candles: list[Candle] = []
    for offset in range(count):
        open_time = (start_time + timedelta(minutes=offset)).isoformat(timespec="seconds")
        open_price = 100.0 + offset
        candles.append(
            Candle(
                open_time=open_time,
                open=open_price,
                high=open_price + 2.0,
                low=open_price - 1.0,
                close=open_price + 0.5,
                volume=1.0 + offset,
            )
        )
    return candles


def test_derive_5m_candles_aggregates_ohlcv_from_1m_candles() -> None:
    derived = derive_closed_timeframe_candles(_minute_candles(10), "5m")

    assert len(derived) == 2
    first = derived[0]
    assert first.open_time == "2026-01-01T00:00:00"
    assert first.open == 100.0
    assert first.high == 106.0
    assert first.low == 99.0
    assert first.close == 104.5
    assert first.volume == 15.0


def test_partial_higher_timeframe_candle_is_not_returned_as_closed_feature() -> None:
    derived = derive_closed_timeframe_candles(_minute_candles(9), "5m")

    assert len(derived) == 1
    assert derived[0].open_time == "2026-01-01T00:00:00"


def test_bucket_with_missing_1m_candle_is_not_returned() -> None:
    candles = _minute_candles(10)
    candles_without_one_minute = [candle for candle in candles if candle.open_time != "2026-01-01T00:03:00"]

    derived = derive_closed_timeframe_candles(candles_without_one_minute, "5m")

    assert [candle.open_time for candle in derived] == ["2026-01-01T00:05:00"]


def test_derived_timeframe_counts_cover_required_timeframes_without_partial_buckets() -> None:
    counts = build_derived_timeframe_counts(_minute_candles(61))

    assert counts == {
        "5m": 12,
        "15m": 4,
        "30m": 2,
        "1h": 1,
        "4h": 0,
        "1d": 0,
    }