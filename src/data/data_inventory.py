"""Backtest data inventory and historical/live availability classification."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DataInventoryItem:
    data_kind: str
    label: str
    historically_downloadable: str
    fair_for_current_blindtest: bool
    live_collection_required: bool
    check_at_backtest_start: bool
    use_in_backtest_now: bool
    target_value: str
    status_reason: str


BACKTEST_DATA_INVENTORY = (
    DataInventoryItem("ethusdc_klines_1m", "ETHUSDC 1m Candles", "yes", True, False, True, True, "high", "primary candle source"),
    DataInventoryItem("btcusdc_klines_1m", "BTCUSDC 1m Candles", "yes", True, False, True, True, "medium", "Strategy V1 context filter"),
    DataInventoryItem("ethbtc_klines_1m", "ETHBTC 1m Candles", "yes", True, False, True, True, "medium", "Strategy V1 context filter"),
    DataInventoryItem("exchange_info", "ETHUSDC exchange_info", "yes", True, False, True, True, "medium", "Spot filter simulation"),
    DataInventoryItem("ethusdc_agg_trades", "ETHUSDC aggTrades", "unclear", False, False, False, False, "medium", "not_available_for_historical_blindtest"),
    DataInventoryItem("ethusdc_trades", "ETHUSDC trades", "unclear", False, False, False, False, "medium", "not_available_for_historical_blindtest"),
    DataInventoryItem("bookticker_spread", "bookTicker / Spread", "no", False, True, False, False, "high", "live_collection_required"),
    DataInventoryItem("orderbook_depth_liquidity", "Orderbook / Depth / Liquidity", "no", False, True, False, False, "high", "live_collection_required"),
)