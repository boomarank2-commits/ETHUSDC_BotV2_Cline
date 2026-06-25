"""Lookahead-safe derived candle timeframes from validated 1m candles."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from src.data.candle_schema import Candle

DERIVED_TIMEFRAME_MINUTES = {
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}


@dataclass(frozen=True)
class DerivedTimeframeFeatureBuildResult:
    """Time-safe higher-timeframe features available at selected 1m decision times."""

    snapshots: dict[str, dict[str, dict[str, Any]]]
    closed_candle_counts: dict[str, int]
    available_timeframes: list[str]
    used_timeframes: list[str]


@dataclass
class _TimeframeAggregationState:
    bucket_start: datetime | None = None
    rows: list[tuple[datetime, Candle]] = field(default_factory=list)
    previous_closed: Candle | None = None
    latest_closed: Candle | None = None
    closed_count: int = 0


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


def _closed_candle_from_rows(
    bucket_start: datetime,
    rows: list[tuple[datetime, Candle]],
    timeframe_minutes: int,
) -> Candle | None:
    if len(rows) != timeframe_minutes:
        return None
    expected_times = [
        bucket_start + timedelta(minutes=offset) for offset in range(timeframe_minutes)
    ]
    actual_times = [row[0] for row in rows]
    if actual_times != expected_times:
        return None
    bucket_candles = [row[1] for row in rows]
    return Candle(
        open_time=_format_like_source(bucket_start, bucket_candles[0].open_time),
        open=bucket_candles[0].open,
        high=max(candle.high for candle in bucket_candles),
        low=min(candle.low for candle in bucket_candles),
        close=bucket_candles[-1].close,
        volume=sum(candle.volume for candle in bucket_candles),
    )


def _finalize_state(
    state: _TimeframeAggregationState,
    timeframe_minutes: int,
) -> None:
    if state.bucket_start is None:
        return
    closed = _closed_candle_from_rows(state.bucket_start, state.rows, timeframe_minutes)
    if closed is None:
        return
    state.previous_closed = state.latest_closed
    state.latest_closed = closed
    state.closed_count += 1


def _feature_snapshot(
    state: _TimeframeAggregationState,
    timeframe_minutes: int,
) -> dict[str, Any] | None:
    latest = state.latest_closed
    if latest is None:
        return None
    previous = state.previous_closed
    close_return = None
    if previous is not None and previous.close > 0:
        close_return = latest.close / previous.close - 1.0
    range_pct = (latest.high - latest.low) / latest.close if latest.close > 0 else None
    bucket_start = _parse_open_time(latest.open_time)
    available_at = bucket_start + timedelta(minutes=timeframe_minutes)
    return {
        "source_open_time": latest.open_time,
        "available_at": _format_like_source(available_at, latest.open_time),
        "close": latest.close,
        "close_return": close_return,
        "range_pct": range_pct,
        "volume": latest.volume,
    }


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
        actual_times = [row[0] for row in bucket_rows]
        if any(
            current - previous != expected_delta
            for previous, current in zip(actual_times, actual_times[1:], strict=False)
        ):
            continue
        closed = _closed_candle_from_rows(bucket_start, bucket_rows, timeframe_minutes)
        if closed is not None:
            derived.append(closed)
    return derived


def build_closed_timeframe_feature_snapshots(
    candles_1m: list[Candle],
    decision_open_times: set[str],
) -> DerivedTimeframeFeatureBuildResult:
    """Build features that use only higher-timeframe candles closed before each decision.

    The current 1m candle is added after its decision-time snapshot is captured. Therefore
    a 5m candle starting at 00:00 can first appear in the snapshot at 00:05, never earlier.
    """
    states = {
        timeframe: _TimeframeAggregationState()
        for timeframe in DERIVED_TIMEFRAME_MINUTES
    }
    snapshots: dict[str, dict[str, dict[str, Any]]] = {}

    for candle in candles_1m:
        open_time = _parse_open_time(candle.open_time)
        for timeframe, timeframe_minutes in DERIVED_TIMEFRAME_MINUTES.items():
            state = states[timeframe]
            current_bucket = _bucket_start(open_time, timeframe_minutes)
            if state.bucket_start is None:
                state.bucket_start = current_bucket
            elif current_bucket != state.bucket_start:
                _finalize_state(state, timeframe_minutes)
                state.bucket_start = current_bucket
                state.rows = []

        if candle.open_time in decision_open_times:
            current_snapshot: dict[str, dict[str, Any]] = {}
            for timeframe, timeframe_minutes in DERIVED_TIMEFRAME_MINUTES.items():
                feature = _feature_snapshot(states[timeframe], timeframe_minutes)
                if feature is not None:
                    current_snapshot[timeframe] = feature
            snapshots[candle.open_time] = current_snapshot

        for state in states.values():
            state.rows.append((open_time, candle))

    for timeframe, timeframe_minutes in DERIVED_TIMEFRAME_MINUTES.items():
        _finalize_state(states[timeframe], timeframe_minutes)

    closed_counts = {
        timeframe: states[timeframe].closed_count
        for timeframe in DERIVED_TIMEFRAME_MINUTES
    }
    available_timeframes = [
        timeframe for timeframe in DERIVED_TIMEFRAME_MINUTES if closed_counts[timeframe] > 0
    ]
    used_timeframes = [
        timeframe
        for timeframe in DERIVED_TIMEFRAME_MINUTES
        if any(timeframe in snapshot for snapshot in snapshots.values())
    ]
    return DerivedTimeframeFeatureBuildResult(
        snapshots=snapshots,
        closed_candle_counts=closed_counts,
        available_timeframes=available_timeframes,
        used_timeframes=used_timeframes,
    )


def build_derived_timeframe_counts(candles_1m: list[Candle]) -> dict[str, int]:
    """Return lookahead-safe completed candle counts for all supported timeframes."""
    return {
        timeframe: len(derive_closed_timeframe_candles(candles_1m, timeframe))
        for timeframe in DERIVED_TIMEFRAME_MINUTES
    }
