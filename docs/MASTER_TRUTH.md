# MASTER_TRUTH

This file contains only confirmed project truth.

Old READMEs, old reports, old code and old bot folders are not truth.
They may be used later as archive material only if explicitly requested.

## Project

ETHUSDC Adaptive Spot LONG-only Bot V2.

## Hard Rules

- Symbol: ETHUSDC
- Quote/capital basis: USDC
- Exchange target: Binance Spot
- LONG only
- No short
- No futures
- No margin
- No leverage

## Final Validation Target

The final decision target is one 730 day training / optimization window followed by one 365 day blindtest.

1 / 7 / 14 / 30 day smoke runs are only shortened technical checks of this same contract. They are not separate backtests and must not receive special logic.

When the 365 day blindtest workflow is proven, the short smoke windows are no longer decision criteria.

## Core Model

The target model is:

Situation -> Cluster / Regime -> Router -> Setup or no_trade -> Trade

Strategies are search space only.
Strategies are not the final target model.

## Shared Capital Rule

A trained strategy pool may contain multiple candidates.

The simulation still has one shared account context.

Candidate results must not be added as if every candidate had separate capital.

Overlapping candidate proposals must be resolved by the router. Without an explicit later capital allocation rule, only one action may be executed for the same shared time / capital context.

## Build Order

1. Backtest core
2. Training / optimization
3. Router freeze
4. Blindtest
5. Reports
6. UI
7. Paper
8. Test trade
9. Live

UI, Paper, Test Trade and Live are later phases.
Do not build them before the backtest core is correct.

## No Assumption Rule

If a rule is missing, unclear or contradictory:
- do not guess
- do not build
- document it in memory-bank/openQuestions.md
- wait for user decision
