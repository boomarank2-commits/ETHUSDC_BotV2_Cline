from datetime import datetime, timedelta

from src.data.candle_schema import Candle
from src.data.derived_timeframes import (
    build_closed_timeframe_feature_snapshots,
    build_derived_timeframe_counts,
    derive_closed_timeframe_candles,
)


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
                quote_volume=10.0 + offset,
                trade_count=offset + 1,
                taker_buy_base_volume=0.5 + offset,
                taker_buy_quote_volume=5.0 + offset,
                close_time=(
                    start_time + timedelta(minutes=offset + 1)
                ).isoformat(timespec="seconds"),
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
    assert first.quote_volume == 60.0
    assert first.trade_count == 15
    assert first.taker_buy_base_volume == 12.5
    assert first.taker_buy_quote_volume == 35.0
    assert first.close_time == "2026-01-01T00:05:00"


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


def test_feature_snapshot_uses_5m_candle_only_after_it_closed() -> None:
    candles = _minute_candles(11)
    result = build_closed_timeframe_feature_snapshots(
        candles,
        {
            "2026-01-01T00:04:00",
            "2026-01-01T00:05:00",
            "2026-01-01T00:10:00",
        },
    )

    assert "5m" not in result.snapshots["2026-01-01T00:04:00"]
    first_available = result.snapshots["2026-01-01T00:05:00"]["5m"]
    assert first_available["source_open_time"] == "2026-01-01T00:00:00"
    assert first_available["available_at"] == "2026-01-01T00:05:00"
    assert first_available["close_return"] is None
    second_available = result.snapshots["2026-01-01T00:10:00"]["5m"]
    assert second_available["source_open_time"] == "2026-01-01T00:05:00"
    assert second_available["close_return"] == 109.5 / 104.5 - 1.0


def test_feature_snapshot_does_not_use_incomplete_or_gapped_bucket() -> None:
    candles = [
        candle
        for candle in _minute_candles(11)
        if candle.open_time != "2026-01-01T00:03:00"
    ]
    result = build_closed_timeframe_feature_snapshots(
        candles,
        {"2026-01-01T00:05:00", "2026-01-01T00:10:00"},
    )

    assert "5m" not in result.snapshots["2026-01-01T00:05:00"]
    assert result.snapshots["2026-01-01T00:10:00"]["5m"]["source_open_time"] == (
        "2026-01-01T00:05:00"
    )
