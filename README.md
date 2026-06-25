# ETHUSDC Bot V2 Cline

Clean rebuild of an ETHUSDC Adaptive Spot LONG-only Bot.

## Canonical target

The final validation target is one full backtest contract:

- 730 days training / optimization
- 365 days blindtest
- no blindtest learning
- one shared account simulation
- one shared router / strategy engine
- no parallel candidate summing as if every candidate had separate capital

Smoke runs with 1 / 7 / 14 / 30 blindtest days are temporary technical checks only. They are shortened versions of the same backtest contract. Once the full 365 day blindtest workflow is proven, smoke runs are no longer decision criteria.

Read order for Cline, Codex or any AI coding agent:

1. docs/FINAL_ONE_YEAR_BLINDTEST_TRUTH.md
2. specs/07_FINAL_ONE_YEAR_BLINDTEST_CONTRACT.md
3. .clinerules/
4. AGENTS.md
5. memory-bank/activeContext.md
6. memory-bank/projectbrief.md
7. docs/MASTER_TRUTH.md
8. docs/BACKTEST_TRUTH.md
9. docs/ROUTER_TRUTH.md
10. docs/DATA_TRUTH.md
11. docs/UI_TRUTH.md
12. docs/IMPLEMENTATION_PLAN.md
13. docs/BACKTEST_ROUTER_CONTRACT.md
14. specs/00_MASTER_GOAL.md
15. specs/01_BACKTEST_CONTRACT.md
16. specs/02_SMOKE_TEST_CONTRACT.md
17. specs/03_STRATEGY_ENGINE_CONTRACT.md
18. specs/04_UI_CONTRACT.md
19. specs/05_REPORTING_CONTRACT.md
20. specs/06_ACCEPTANCE_TESTS.md

Old files are not truth.

## UI starten

- Windows: Doppelklick auf `ETHUSDC_BotV2_UI_starten.bat`
- Alternative per PowerShell:
  `python -m src.ui.app`
