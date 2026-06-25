# DATA_TRUTH

This file contains only confirmed data truth.

## Main Market

- ETHUSDC is the main symbol.
- USDC is the quote/capital basis.

## Required Principle

All training and blindtest data must be time-safe.

No future information may be used in features.

## Minimum Data Idea

The project needs enough historical data for:

- 730 days training / optimization
- 365 days blindtest

## Confirmed Current Base

Confirmed starting point:
- ETHUSDC candles / klines
- Binance exchange_info
- Binance filters / rules
- fee model

ETHUSDC 1m candles are the main base, but the final model must not be limited to raw 1m candles only.

Derived timeframes may be generated from validated 1m candles, for example:
- 5m
- 15m
- 30m
- 1h
- 4h
- 1d

These derived timeframes must be built without lookahead. A higher timeframe candle may only be used after it would have been closed at that historical point.

## Optional Context Data

Optional context may be used only when valid and time-safe:
- BTCUSDC as market context
- ETHBTC as relative ETH strength
- ETHUSDC trades
- ETHUSDC aggTrades
- bookTicker
- orderbook snapshots / depth data

A missing optional source must not silently become assumed truth.

## Orderbook / BookTicker Rule

Orderbook and bookTicker data must not be blindly used just because they would be useful.

They may be used only after they have been collected live and validated as sufficiently clean, gap-aware and time-safe.

A practical minimum before backtest use is at least 30 days of clean live-collected data.

Even then, they may only be used for historical points where the data truly existed at that time.

Not allowed:
- future orderbook information
- later confirmation from orderbook data
- filling old historical gaps with future snapshots
- pretending orderbook existed for periods where it was not collected

## Purpose of More Data

Additional validated data is meant to locate ETH situations more precisely, not to make reports look better.

Expected benefits:
- better entry quality
- better distinction between real impulse and fake move
- better spread / slippage estimation
- better taker pressure estimation
- better liquidity evaluation
- better trade vs no_trade decision

## Open Data Questions

Any missing data rule must be documented in memory-bank/openQuestions.md before implementation.
