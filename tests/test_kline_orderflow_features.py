import pytest

from src.data.candle_schema import Candle
from src.data.kline_orderflow_features import (
    build_closed_kline_orderflow_feature_series,
)


def _candle(index: int, quote_volume: float, trade_count: int, taker_buy: float) -> Candle:
    return Candle(
        open_time=f"2026-01-01T00:{index:02d}:00Z",
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=quote_volume / 100.0,
        quote_volume=quote_volume,
        trade_count=trade_count,
        taker_buy_base_volume=taker_buy / 100.0,
        taker_buy_quote_volume=taker_buy,
    )


def test_orderflow_features_use_current_closed_minute_against_prior_minutes() -> None:
    candles = [
        _candle(0, 10.0, 1, 5.0),
        _candle(1, 20.0, 2, 10.0),
        _candle(2, 30.0, 3, 24.0),
    ]

    series = build_closed_kline_orderflow_feature_series(candles, 2)

    assert series.value_at("quote_volume_ratio", 1) is None
    assert series.value_at("quote_volume_ratio", 2) == 2.0
    assert series.value_at("trade_count_ratio", 2) == 2.0
    assert series.value_at("taker_buy_quote_imbalance", 2) == pytest.approx(0.6)


def test_orderflow_feature_at_entry_is_not_changed_by_future_candles() -> None:
    initial = [
        _candle(0, 10.0, 1, 5.0),
        _candle(1, 20.0, 2, 10.0),
        _candle(2, 30.0, 3, 24.0),
    ]
    with_future = initial + [_candle(3, 1_000_000.0, 99_999, 1_000_000.0)]

    initial_series = build_closed_kline_orderflow_feature_series(initial, 2)
    future_series = build_closed_kline_orderflow_feature_series(with_future, 2)

    assert future_series.value_at("quote_volume_ratio", 2) == initial_series.value_at(
        "quote_volume_ratio",
        2,
    )
    assert future_series.value_at(
        "trade_count_ratio",
        2,
    ) == initial_series.value_at("trade_count_ratio", 2)
