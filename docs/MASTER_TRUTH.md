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

## Core Model

The target model is:

Situation -> Cluster -> Router -> Setup -> Trade

Strategies are search space only.
Strategies are not the final target model.

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
