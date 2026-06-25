# Next Codex Task - Data Usage After Full Run

Stand: 2026-06-25

## Context

A full backtest has completed:

- Run-ID: `run_20260625_194632`
- Type: `full_backtest`
- Status: completed
- Result: 0 trades, 0.00 USDC/day
- Candidate space: `trade_allowed_blocked`
- Best training candidate: about 0.01 USDC/day
- ETHUSDC candles: 1,579,690
- Gaps: 0
- Usable: true
- Data areas: 8 usable, 4 used in backtest, 3 not available

Decision: do not take over.

## First truth source

Before doing anything, read:

1. `docs/CURRENT_TRUTH_MAP.md`
2. `docs/FINAL_ONE_YEAR_BLINDTEST_TRUTH.md`
3. `specs/07_FINAL_ONE_YEAR_BLINDTEST_CONTRACT.md`
4. `README.md`
5. `AGENTS.md`

If anything conflicts, `docs/CURRENT_TRUTH_MAP.md` wins.

## Hard rules

- ETHUSDC only.
- USDC quote/capital basis.
- Binance Spot.
- LONG-only.
- No short, no futures, no margin, no leverage.
- No blindtest learning.
- No lookahead.
- No fake trades.
- No separate backtest engine.
- No direct optimization on 7/14/30 smoke windows.
- No raw market data committed to GitHub.
- Smoke and Full must keep the same UI/controller/pipeline/router path.
- 365-day blindtest after 730-day training is the decision basis.

## Goal

This bot is not a generic bot. It is built for Ethereum / ETHUSDC.

Target direction:

- 100 USDC stake per trade
- long-term goal: 3 USDC/day or more in the 365-day blindtest
- after fees, slippage, Binance filters and shared capital/time context
- only after training evidence and blindtest confirmation
- only after conscious user takeover

The target must not be faked by loosening gates, adding fake trades, using blindtest data for learning, or silently changing the engine.

## Part 1 - Verify data completeness and real usage

Do this first. If Part 1 is large, stop after Part 1 and report.

Inspect the latest run folder locally:

`reports/backtests/run_20260625_194632`

Check at minimum:

- `backtest_summary.json`
- `activity_first_router_report.json`
- `data_preparation_report.json`
- `data_overview_report.json`
- `run_request.json`
- progress/status files if useful

Create or update a small report file, for example:

`reports/backtests/run_20260625_194632/data_usage_audit.md`

The audit must include a matrix with one row per data source:

- ETHUSDC 1m OHLCV
- ETHUSDC complete kline fields: quote volume, trade count, taker buy fields
- ETHUSDC derived timeframes 5m/15m/30m/1h/4h/1d
- BTCUSDC 1m
- ETHBTC 1m
- ETHUSDT 1m
- USDCUSDT 1m
- ETHUSDC exchange_info / filters
- ETHUSDC aggTrade minute features
- live spread / bookTicker / top-20 depth

Columns:

- downloaded / locally present
- quality status
- freshness status
- shown in Data Overview
- used in backtest yes/no
- used in router decision yes/no
- used only as diagnostics yes/no
- reason if not used
- next safe step

Important: do not commit raw `data/` files. Only commit small reports or code/docs.

## Part 2 - Integrate useful data into training/router, one source at a time

Start Part 2 only after Part 1 is clear.

Purpose: make prepared data actually useful for the Ethereum strategy, but only safely.

Required approach:

1. Add lookahead-safe feature access for one prepared data source at a time.
2. Use training data only to test whether the feature separates winners from losers.
3. Report the separation clearly.
4. Only if there is a training-only signal, allow it as a small score/gate candidate.
5. Freeze before blindtest.
6. Run blindtest without learning or re-selection.

Candidate order:

1. Existing HTF diagnostics, because they are already connected.
2. Complete kline order-flow fields: quote volume, trade count, taker-buy imbalance.
3. aggTrade minute features.
4. Context markets: BTCUSDC, ETHBTC, ETHUSDT, USDCUSDT.
5. Spread/depth only after at least 30 real days of validated collection.

Do not integrate everything at once if that makes the change hard to verify.

## What must be reported

For every feature source tested:

- sample count
- winner average
- loser average
- winner minus loser
- profit factor effect if available
- trade count effect
- no-trade filtering effect
- risk of overfitting
- whether it changes gates/scores/trades
- whether it is training-only or blindtest-learned

The report must make it obvious why a feature was accepted or rejected.

## Stop conditions

Stop and report instead of continuing if:

- downloaded data is incomplete
- reports disagree with each other
- Data Overview says a source is available but router cannot access it
- feature alignment risks lookahead
- Part 2 becomes too large
- tests fail
- the only way to improve result would be to loosen gates blindly

## Required validation

After code changes:

```bat
python -m compileall src tests
python -m pytest -q
```

Also report:

- changed files
- what data is now used
- what is still only downloaded/prepared
- whether Smoke and Full still use the same path
- whether any feature changes gates/scores/trades
- whether the result moved toward 3 USDC/day honestly

## Expected handoff

If only Part 1 is done, say:

`Part 1 completed. Data availability/usage audit is ready. Should I continue with Part 2 feature integration?`

If Part 2 is also done, say clearly:

- which feature source was integrated
- why it was safe
- what tests passed
- what run should Andreas start next
