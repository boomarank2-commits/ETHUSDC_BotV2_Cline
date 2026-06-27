"""Lookahead-safe ETHUSDC order-flow features from completed Binance klines."""

from __future__ import annotations

import math
from array import array
from dataclasses import dataclass

from src.data.candle_schema import Candle


ORDERFLOW_METRICS = (
    "quote_volume_ratio",
    "trade_count_ratio",
    "taker_buy_quote_imbalance",
)


@dataclass(frozen=True)
class KlineOrderflowFeatureSeries:
    """Compact order-flow values aligned to 1m entry decisions.

    The volume and trade-count baselines use only prior completed one-minute
    candles.  The current candle's fields are used only after that candle has
    closed, which matches the router's close-to-next-candle entry model.
    """

    lookback_candles: int
    quote_volume_ratio: array
    trade_count_ratio: array
    taker_buy_quote_imbalance: array

    def value_at(self, metric: str, index: int) -> float | None:
        values = getattr(self, metric, None)
        if not isinstance(values, array) or index < 0 or index >= len(values):
            return None
        value = float(values[index])
        return None if math.isnan(value) else value


def build_closed_kline_orderflow_feature_series(
    candles: list[Candle],
    lookback_candles: int,
) -> KlineOrderflowFeatureSeries:
    """Create one-minute order-flow features without future candles.

    At index ``i`` the relative-volume features compare candle ``i`` with the
    preceding ``lookback_candles`` closed minutes.  Later candles never affect
    the feature at ``i``.
    """
    if lookback_candles < 1:
        msg = "lookback_candles must be at least 1"
        raise ValueError(msg)

    quote_volumes = array("d", (candle.quote_volume for candle in candles))
    trade_counts = array("d", (float(candle.trade_count) for candle in candles))
    quote_volume_ratios = array("d")
    trade_count_ratios = array("d")
    taker_buy_imbalances = array("d")
    prior_quote_total = 0.0
    prior_trade_total = 0.0

    for index, candle in enumerate(candles):
        if index > 0:
            prior_quote_total += quote_volumes[index - 1]
            prior_trade_total += trade_counts[index - 1]
        if index > lookback_candles:
            prior_quote_total -= quote_volumes[index - lookback_candles - 1]
            prior_trade_total -= trade_counts[index - lookback_candles - 1]
        prior_quote_average = (
            prior_quote_total / lookback_candles
            if index >= lookback_candles and prior_quote_total > 0
            else None
        )
        prior_trade_average = (
            prior_trade_total / lookback_candles
            if index >= lookback_candles and prior_trade_total > 0
            else None
        )
        quote_volume_ratios.append(
            candle.quote_volume / prior_quote_average
            if prior_quote_average is not None
            else math.nan
        )
        trade_count_ratios.append(
            candle.trade_count / prior_trade_average
            if prior_trade_average is not None
            else math.nan
        )
        taker_buy_imbalances.append(
            (
                2.0 * candle.taker_buy_quote_volume / candle.quote_volume - 1.0
                if candle.quote_volume > 0
                else math.nan
            )
        )

    return KlineOrderflowFeatureSeries(
        lookback_candles=lookback_candles,
        quote_volume_ratio=quote_volume_ratios,
        trade_count_ratio=trade_count_ratios,
        taker_buy_quote_imbalance=taker_buy_imbalances,
    )
