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
    DataInventoryItem("btcusdc_klines_1m", "BTCUSDC 1m Candles", "yes", True, False, True, True, "medium", "Activity-First Router training-only cross-market diagnostics and frozen filter candidates"),
    DataInventoryItem("ethbtc_klines_1m", "ETHBTC 1m Candles", "yes", True, False, True, True, "medium", "Activity-First Router training-only cross-market diagnostics and frozen filter candidates"),
    DataInventoryItem("ethusdt_klines_1m", "ETHUSDT 1m Candles", "yes", True, False, True, True, "high", "Activity-First Router training-only cross-market diagnostics and frozen filter candidates"),
    DataInventoryItem("usdcusdt_klines_1m", "USDCUSDT 1m Candles", "yes", True, False, True, True, "medium", "Activity-First Router training-only cross-market diagnostics and frozen filter candidates"),
    DataInventoryItem("enhanced_kline_order_flow", "Kline quote/trade/taker fields", "yes", True, False, True, True, "high", "Activity-First Router training-only diagnostics and frozen filter candidates"),
    DataInventoryItem("exchange_info", "ETHUSDC exchange_info", "yes", True, False, True, True, "medium", "Spot filter simulation"),
    DataInventoryItem("ethusdc_agg_trades", "ETHUSDC aggTrades", "yes", True, False, True, True, "high", "Activity-First Router training-only diagnostics and frozen filter candidates"),
    DataInventoryItem("ethusdc_trades", "ETHUSDC raw trades", "yes", True, False, False, False, "low", "not downloaded initially because aggTrades plus kline trade counts preserve the required order-flow signal at far lower storage cost"),
    DataInventoryItem("bookticker_spread", "bookTicker / Spread", "live only", False, True, True, False, "high", "continuous live collection; usable only after at least 30 days"),
    DataInventoryItem("orderbook_depth_liquidity", "Orderbook / Depth / Liquidity", "live only", False, True, True, False, "high", "continuous live collection; usable only after at least 30 days"),
)
