"""Lookahead-safe derived candle timeframes from validated 1m candles."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.data.candle_schema import Candle

DERIVED_TIMEFRAME_MINUTES = {
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}


def _parse_open_time(open_time: str) -> datetime:
    try:
        return datetime.fromisoformat(open_time.replace("Z", "+00:00"))
    except ValueError as error:
        msg = f"open_time is not parseable: {open_time}"
        raise ValueError(msg) from error


def _format_like_source(value: datetime, source_open_time: str) -> str:
    if source_open_time.endswith("Z"):
        return value.isoformat().replace("+00:00", "Z")
    if "T" in source_open_time and "+" not in source_open_time:
        return value.replace(tzinfo=None).isoformat(timespec="seconds")
    return value.isoformat(timespec="seconds")


def _bucket_start(open_time: datetime, timeframe_minutes: int) -> datetime:
    day_start = open_time.replace(hour=0, minute=0, second=0, microsecond=0)
    minutes_since_day_start = int((open_time - day_start).total_seconds() // 60)
    bucket_minute = minutes_since_day_start - (minutes_since_day_start % timeframe_minutes)
    return day_start + timedelta(minutes=bucket_minute)


def derive_closed_timeframe_candles(
    candles_1m: list[Candle],
    timeframe: str,
) -> list[Candle]:
    """Aggregate only complete higher-timeframe candles from historical 1m candles.

    A derived candle is emitted only when every 1m candle in its bucket exists. A partial
    last bucket is ignored, so the returned feature candles are closed from the historical
    point of view and do not require future data.
    """
    if timeframe not in DERIVED_TIMEFRAME_MINUTES:
        msg = f"unsupported derived timeframe: {timeframe}"
        raise ValueError(msg)

    timeframe_minutes = DERIVED_TIMEFRAME_MINUTES[timeframe]
    buckets: dict[datetime, list[tuple[datetime, Candle]]] = {}
    for candle in candles_1m:
        parsed_open_time = _parse_open_time(candle.open_time)
        bucket = _bucket_start(parsed_open_time, timeframe_minutes)
        buckets.setdefault(bucket, []).append((parsed_open_time, candle))

    derived: list[Candle] = []
    expected_delta = timedelta(minutes=1)
    for bucket_start in sorted(buckets):
        bucket_rows = sorted(buckets[bucket_start], key=lambda row: row[0])
        if len(bucket_rows) != timeframe_minutes:
            continue
        expected_times = [bucket_start + timedelta(minutes=offset) for offset in range(timeframe_minutes)]
        actual_times = [row[0] for row in bucket_rows]
        if actual_times != expected_times:
            continue
        if any(current - previous != expected_delta for previous, current in zip(actual_times, actual_times[1:], strict=False)):
            continue

        bucket_candles = [row[1] for row in bucket_rows]
        derived.append(
            Candle(
                open_time=_format_like_source(bucket_start, bucket_candles[0].open_time),
                open=bucket_candles[0].open,
                high=max(candle.high for candle in bucket_candles),
                low=min(candle.low for candle in bucket_candles),
                close=bucket_candles[-1].close,
                volume=sum(candle.volume for candle in bucket_candles),
            )
        )
    return derived


def build_derived_timeframe_counts(candles_1m: list[Candle]) -> dict[str, int]:
    """Return lookahead-safe completed candle counts for all supported timeframes."""
    return {
        timeframe: len(derive_closed_timeframe_candles(candles_1m, timeframe))
        for timeframe in DERIVED_TIMEFRAME_MINUTES
    }