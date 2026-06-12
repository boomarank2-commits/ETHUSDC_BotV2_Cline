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

## Data Types

Confirmed starting point:
- ETHUSDC candles / klines

Other data types such as BTC context, ETHBTC context, trades, aggTrades, bookTicker or orderbook may be added later only after they are clearly defined.

Do not add data sources as required truth until confirmed.

## Open Data Questions

Any missing data rule must be documented in memory-bank/openQuestions.md before implementation.
