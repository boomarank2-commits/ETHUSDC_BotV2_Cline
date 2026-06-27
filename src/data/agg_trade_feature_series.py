"""Lookahead-safe ETHUSDC aggTrade minute features aligned to 1m candles."""

from __future__ import annotations

import csv
import math
from array import array
from bisect import bisect_left
from collections import deque
from dataclasses import dataclass

from src.data.agg_trade_data_ensure import AGG_TRADE_FEATURE_DIR
from src.data.candle_schema import Candle


AGG_TRADE_METRICS = (
    "agg_trade_count_ratio",
    "raw_trade_count_ratio",
    "taker_buy_quote_imbalance",
    "vwap_close_deviation",
    "max_agg_trade_quote_share",
)


@dataclass(frozen=True)
class AggTradeFeatureSeries:
    """Compact aggTrade features aligned to each closed 1m decision candle."""

    lookback_candles: int
    agg_trade_count_ratio: array
    raw_trade_count_ratio: array
    taker_buy_quote_imbalance: array
    vwap_close_deviation: array
    max_agg_trade_quote_share: array

    def value_at(self, metric: str, index: int) -> float | None:
        values = getattr(self, metric, None)
        if not isinstance(values, array) or index < 0 or index >= len(values):
            return None
        value = float(values[index])
        return None if math.isnan(value) else value


def _relevant_feature_paths(candles: list[Candle]) -> list:
    months = {candle.open_time[:7] for candle in candles}
    if not AGG_TRADE_FEATURE_DIR.exists():
        return []
    return sorted(
        path
        for path in AGG_TRADE_FEATURE_DIR.glob("*.csv")
        if path.stem[:7] in months
    )


def _aligned_raw_values(
    candles: list[Candle],
) -> tuple[array, array, array, array, array, array, array]:
    """Load only aggTrade rows whose minute exists in the candle decision set."""
    size = len(candles)
    missing = math.nan
    agg_counts = array("d", [missing]) * size
    raw_counts = array("d", [missing]) * size
    buy_quote = array("d", [missing]) * size
    sell_quote = array("d", [missing]) * size
    vwaps = array("d", [missing]) * size
    max_quotes = array("d", [missing]) * size
    quote_volumes = array("d", [missing]) * size
    open_times = [candle.open_time for candle in candles]

    for path in _relevant_feature_paths(candles):
        with path.open("r", newline="", encoding="utf-8") as csv_file:
            for row in csv.DictReader(csv_file):
                open_time = row.get("open_time")
                if open_time is None:
                    continue
                index = bisect_left(open_times, open_time)
                if index >= size or open_times[index] != open_time:
                    continue
                agg_counts[index] = float(row["agg_trade_count"])
                raw_counts[index] = float(row["raw_trade_count"])
                buy_quote[index] = float(row["taker_buy_quote_volume"])
                sell_quote[index] = float(row["taker_sell_quote_volume"])
                vwaps[index] = float(row["vwap"])
                max_quotes[index] = float(row["max_agg_trade_quote"])
                quote_volumes[index] = float(row["quote_volume"])
    return agg_counts, raw_counts, buy_quote, sell_quote, vwaps, max_quotes, quote_volumes


def _relative_to_prior(values: array, lookback_candles: int) -> array:
    result = array("d")
    window: deque[float] = deque()
    rolling_total = 0.0
    valid_count = 0
    for value in values:
        current = float(value)
        if (
            len(window) == lookback_candles
            and valid_count == lookback_candles
            and not math.isnan(current)
            and rolling_total > 0
        ):
            result.append(current / (rolling_total / lookback_candles))
        else:
            result.append(math.nan)
        window.append(current)
        if not math.isnan(current):
            rolling_total += current
            valid_count += 1
        if len(window) > lookback_candles:
            removed = window.popleft()
            if not math.isnan(removed):
                rolling_total -= removed
                valid_count -= 1
    return result


def build_closed_agg_trade_feature_series(
    candles: list[Candle],
    lookback_candles: int,
) -> AggTradeFeatureSeries:
    """Build minute features using no future aggTrades or candles.

    The minute at index ``i`` is used only after it has closed. Relative
    intensity compares it with the preceding complete minutes only.
    """
    if lookback_candles < 1:
        raise ValueError("lookback_candles must be at least 1")
    (
        agg_counts,
        raw_counts,
        buy_quote,
        sell_quote,
        vwaps,
        max_quotes,
        quote_volumes,
    ) = _aligned_raw_values(candles)
    imbalance = array("d")
    vwap_deviation = array("d")
    max_share = array("d")
    for candle, buy, sell, vwap, max_quote, quote_volume in zip(
        candles,
        buy_quote,
        sell_quote,
        vwaps,
        max_quotes,
        quote_volumes,
        strict=True,
    ):
        total_taker = buy + sell
        imbalance.append(
            (buy - sell) / total_taker
            if not math.isnan(total_taker) and total_taker > 0
            else math.nan
        )
        vwap_deviation.append(
            candle.close / vwap - 1.0
            if not math.isnan(vwap) and vwap > 0
            else math.nan
        )
        max_share.append(
            max_quote / quote_volume
            if not math.isnan(max_quote)
            and not math.isnan(quote_volume)
            and quote_volume > 0
            else math.nan
        )
    return AggTradeFeatureSeries(
        lookback_candles=lookback_candles,
        agg_trade_count_ratio=_relative_to_prior(agg_counts, lookback_candles),
        raw_trade_count_ratio=_relative_to_prior(raw_counts, lookback_candles),
        taker_buy_quote_imbalance=imbalance,
        vwap_close_deviation=vwap_deviation,
        max_agg_trade_quote_share=max_share,
    )
