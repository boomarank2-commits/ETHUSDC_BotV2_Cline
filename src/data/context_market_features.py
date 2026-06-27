"""Lookahead-safe cross-market candle features for the ETHUSDC router.

Only local Binance Spot 1m candles are used.  Values at ETHUSDC minute ``i``
are derived from the matching context candle that closed at that same minute
or from earlier context candles.  The module intentionally has no downloader
and no external data-provider dependency.
"""

from __future__ import annotations

import csv
import math
from array import array
from dataclasses import dataclass, field
from pathlib import Path

from src.data.candle_schema import Candle
from src.data.data_catalog import load_data_catalog


CONTEXT_MARKET_METRICS = (
    "btcusdc_return",
    "ethbtc_return",
    "ethusdt_ethusdc_basis",
    "usdcusdt_deviation",
)

METRIC_SOURCES = {
    "btcusdc_return": "BTCUSDC",
    "ethbtc_return": "ETHBTC",
    "ethusdt_ethusdc_basis": "ETHUSDT",
    "usdcusdt_deviation": "USDCUSDT",
}


@dataclass(frozen=True)
class ContextMarketFeatureSeries:
    """One lookback's compact cross-market values aligned to ETHUSDC candles."""

    lookback_candles: int
    btcusdc_return: array
    ethbtc_return: array
    ethusdt_ethusdc_basis: array
    usdcusdt_deviation: array

    def value_at(self, metric: str, index: int) -> float | None:
        values = getattr(self, metric, None)
        if not isinstance(values, array) or index < 0 or index >= len(values):
            return None
        value = float(values[index])
        return None if math.isnan(value) else value


def _catalog_paths() -> dict[str, Path]:
    try:
        entries = load_data_catalog()
    except (FileNotFoundError, OSError, ValueError):
        return {}
    symbols = set(METRIC_SOURCES.values())
    return {
        entry.symbol: Path(entry.path)
        for entry in entries
        if entry.symbol in symbols and entry.interval == "1m"
    }


def _aligned_closes(candles: list[Candle], path: Path | None) -> array:
    """Stream one context CSV into a compact array aligned to ETHUSDC times."""
    values = array("d", [math.nan]) * len(candles)
    if path is None or not path.exists() or not candles:
        return values
    open_times = [candle.open_time for candle in candles]
    index = 0
    try:
        with path.open("r", newline="", encoding="utf-8") as csv_file:
            for row in csv.DictReader(csv_file):
                open_time = row.get("open_time")
                close = row.get("close")
                if not open_time or not close:
                    continue
                while index < len(open_times) and open_times[index] < open_time:
                    index += 1
                if index >= len(open_times):
                    break
                if open_times[index] == open_time:
                    values[index] = float(close)
                    index += 1
    except (OSError, ValueError):
        return array("d", [math.nan]) * len(candles)
    return values


def _return_against_prior(values: array, lookback_candles: int) -> array:
    result = array("d")
    for index, value in enumerate(values):
        prior_index = index - lookback_candles
        prior = values[prior_index] if prior_index >= 0 else math.nan
        result.append(
            value / prior - 1.0
            if not math.isnan(value) and not math.isnan(prior) and prior > 0
            else math.nan
        )
    return result


@dataclass
class ContextMarketFeatureStore:
    """Source-aligned context closes, loaded once per router candle window."""

    ethusdc_close: array
    context_closes: dict[str, array]
    source_coverage: dict[str, float]
    _series_by_lookback: dict[int, ContextMarketFeatureSeries] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    @property
    def available_sources(self) -> list[str]:
        return sorted(
            symbol for symbol, coverage in self.source_coverage.items() if coverage > 0
        )

    def series_for_lookback(self, lookback_candles: int) -> ContextMarketFeatureSeries:
        if lookback_candles < 1:
            raise ValueError("lookback_candles must be at least 1")
        cached = self._series_by_lookback.get(lookback_candles)
        if cached is not None:
            return cached
        btcusdc = self.context_closes["BTCUSDC"]
        ethbtc = self.context_closes["ETHBTC"]
        ethusdt = self.context_closes["ETHUSDT"]
        usdcusdt = self.context_closes["USDCUSDT"]
        basis = array("d")
        deviation = array("d")
        for ethusdc, ethusdt_close, usdcusdt_close in zip(
            self.ethusdc_close,
            ethusdt,
            usdcusdt,
            strict=True,
        ):
            basis.append(
                ethusdt_close / ethusdc - 1.0
                if not math.isnan(ethusdt_close) and ethusdc > 0
                else math.nan
            )
            deviation.append(
                usdcusdt_close - 1.0
                if not math.isnan(usdcusdt_close)
                else math.nan
            )
        series = ContextMarketFeatureSeries(
            lookback_candles=lookback_candles,
            btcusdc_return=_return_against_prior(btcusdc, lookback_candles),
            ethbtc_return=_return_against_prior(ethbtc, lookback_candles),
            ethusdt_ethusdc_basis=basis,
            usdcusdt_deviation=deviation,
        )
        self._series_by_lookback[lookback_candles] = series
        return series


def build_closed_context_market_feature_store(
    candles: list[Candle],
) -> ContextMarketFeatureStore:
    """Build a reusable store without reading any data after its decision time."""
    paths = _catalog_paths()
    context_closes = {
        symbol: _aligned_closes(candles, paths.get(symbol))
        for symbol in ("BTCUSDC", "ETHBTC", "ETHUSDT", "USDCUSDT")
    }
    total = max(1, len(candles))
    coverage = {
        symbol: sum(not math.isnan(value) for value in values) / total
        for symbol, values in context_closes.items()
    }
    return ContextMarketFeatureStore(
        ethusdc_close=array("d", (candle.close for candle in candles)),
        context_closes=context_closes,
        source_coverage=coverage,
    )
