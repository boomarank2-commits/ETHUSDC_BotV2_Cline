# Open Questions

These questions must be decided before implementation if needed.

1. Which Python version should be used?
2. Which data source/library should be used for Binance historical ETHUSDC data?
3. Should BTCUSDC or ETHBTC context be included in V2 from the beginning, or only after ETHUSDC baseline works?
4. What exact fees and slippage assumptions should the first backtest use?
5. What is the first acceptance target for the 365 day blindtest?
6. Should the first version use only local CSV data or also download data automatically?

## Resolved 2026-06-25

- Historical Binance Spot data is downloaded automatically through the shared UI
  backtest start path.
- The selected base is ETHUSDC plus BTCUSDC, ETHBTC, ETHUSDT and USDCUSDT 1m
  context, complete kline fields, exchange_info and compact ETHUSDC aggTrades.
- BookTicker/depth are collected live and cannot be backfilled or used before
  real validated coverage exists.
- Raw trades are not duplicated initially because aggTrades plus kline trade
  counts are the selected lower-storage historical order-flow basis.
