# NEXT_START_2026_06_18

Project path:
- `C:\TradingBot\ETHUSDC_BotV2_Cline`

Current truth:
- Last completed runtime run: `run_20260618_071808`, status `completed`.
- Result: Strategy V1 `+2.2964 USDC`, `0.006291 USDC/day`, `8` blindtest trades.
- Selected candidate: `range_breakout_lb360_th0.01_tp0.015` without context.
- BTCUSDC and ETHBTC are now complete, usable and used; Strategy V1 context was available/aligned.

Blocker found:
- BTCUSDC/ETHBTC were wired but incomplete, so context candidates scored `-1000000000` / 0 trades.
- `run_backtest_for_ui(...)` ignored incomplete context ensure results and could continue ETHUSDC-only.

Changes now:
- Context ensure validates count, gaps and freshness.
- Existing incomplete context CSVs trigger backfill/resume before normal incremental update.
- UI start now blocks if required context data remains incomplete.
- Strategy V1 uses cached ETHUSDC exchange_info filters minimally: MIN_NOTIONAL/NOTIONAL, LOT_SIZE and PRICE_FILTER.

Current process state:
- No background process should be used.
- Backtest/backfill should run visibly through the UI only.
- New UI run `run_20260618_071808` completed with context data available.
- Handoff report for GPT: `memory-bank/GPT_HANDOFF_CONTEXT_BLOCKER_2026_06_18.md`.

Next:
1. Do not work on downloader/data next.
2. Low-activity scoring penalty is now implemented; next run must be visible via UI.
3. Inspect new report fields after next UI run: raw/adjusted score, penalty, trades/month.
4. No large architecture rewrite.

Latest analysis:
- 144 candidates: 72 context, 72 non-context.
- Context candidates with trades: 68; zero-trade context candidates: 4.
- Best context: `range_breakout_lb120_th0.01_tp0.015_ctx`, score `+2.3067`, 17 training trades.
- Best non-context/selected: `range_breakout_lb360_th0.01_tp0.015`, score `+3.5500`, 18 training trades.
- No technical context-passing bug found; weak point is scoring/candidate robustness.
- Implemented rule: target 24 training trades over 730 days; each missing trade costs `0.02 USDC` adjusted score.
- On old run data, theoretical new winner: `range_breakout_lb30_th0.01_tp0.015`, 31 training trades, non-context.

Catalog regression:
- UI run `run_20260618_153414` completed with `-5.96 USDC` / 20 trades, but is not valid for context-scoring comparison.
- BTCUSDC/ETHBTC were `not_available` because `configs/data_catalog.json` had only ETHUSDC.
- CSV files still exist; only Catalog entries were lost.
- Cause fixed: ETHUSDC ensure now upserts instead of overwriting Catalog; Context ensure upserts existing valid context CSVs.
- Catalog repaired to ETHUSDC, BTCUSDC, ETHBTC.
- Next UI backtest should only be evaluated if BTCUSDC/ETHBTC are usable/used again.

Data ensure / clean update:
- Backtest start checks ETHUSDC 1m, BTCUSDC 1m, ETHBTC 1m and exchange_info.
- Existing data uses 7-day freshness plus append/resume/backfill; Catalog writes must preserve other symbols.
- Microstructure is reported but not used: aggTrades/trades not available for current historical blindtest; bookTicker/orderbook require live collection.
- UI has `Alle Daten löschen / Bot clean machen` with two warnings; it deletes downloaded data/reports and resets Catalog/runtime.
- Next: visible UI backtest, then inspect data areas and Strategy V1 report.

Latest valid UI run:
- `run_20260618_160502`, status completed, valid context run.
- Result `-5.96 USDC`, 20 blindtest trades.
- Selected `range_breakout_lb30_th0.01_tp0.015`, non-context, raw/adjusted score `+3.5166`, 31 training trades.
- Low-activity fix selected expected higher-activity candidate, but blindtest got worse.
- Next small step: add/use training-only stability diagnostics, not microstructure or Blindtest optimization.

Stability scoring update:
- Implemented training-only stability metrics and final score penalties.
- Penalizes few active training months, negative-month dominance, training drawdown above threshold and top-trade profit concentration.
- Existing saved runs cannot determine new expected winner because old candidate audits lack trade/month distribution.
- Next UI run will generate the required stability report fields.

Clean-restart latest:
- `run_20260618_164530` completed with valid/used ETHUSDC, exchange_info, BTCUSDC, ETHBTC.
- Result `+2.30 USDC` / 8 trades; selected `range_breakout_lb360_th0.01_tp0.015` non-context.
- Stability rule was active and reported; selection used `adjusted_score_final`.
- No selection/report bug found; mini-fix raised low-activity penalty to `0.08` per missing training trade under 24.

Patch recovery latest:
- Last user-provided baseline: `run_20260619_053202`, completed, data valid/used, `no_robust_positive_candidate`, best final training score `-1.4644`, selected `range_breakout_lb20_th0.01_tp0.015`, result `-9.68 USDC` / 21 trades.
- Candidate-space extended again: normal profile now 560 candidates (was 400 in latest run) via extra TP/SL/Hold and trailing-stop variants; no architecture rewrite.
- Tests green: `python -m compileall src tests`; `python -m pytest -q`.
- New central UI-controller run: `run_20260619_062700`, completed, ETHUSDC/exchange_info/BTCUSDC/ETHBTC usable+used, selected same candidate, best final training score `-1.4644`, result `-9.68 USDC`, `-0.0265 USDC/day`, 21 trades.
- Next blocker: exit expansion did not help; Strategy V1 entry/setup families themselves are too weak/narrow, likely need a small new entry variant or richer training-only setup features before another UI backtest.