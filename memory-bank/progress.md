# Progress

## 2026-06-25 - Daten-/Feature-Baustein abgeleitete Timeframes

Geändert: `src/data/derived_timeframes.py` erzeugt aus ETHUSDC-1m-Candles lookahead-sicher nur vollständig geschlossene 5m/15m/30m/1h/4h/1d-Kerzen. `data_preparation_report.json` meldet ETHUSDC-1m, `derived_timeframes_available`, Counts und optionale Quellen BTCUSDC/ETHBTC/trades/aggTrades/bookTicker/orderbook ehrlich als available/missing.

Keine neue Handelslogik, kein Live/Paper, keine separate Smoke-Engine; Smoke und Full bleiben derselbe Backtest-Apparat. Tests grün: `python -m compileall src tests`, `python -m pytest -q`.

## 2026-06-23 - Finaler Precheck-Transparenz-Patch und UI-naher Smoke

`run_20260623_155039`: 0 Trades trotz Best training 0.0624, weil 123/123 Kandidaten im Training-Precheck endeten; positiver Best-Candidate hatte nur 1 Trade/14d und wurde nicht vollständig split-/validation-/robustness-bewertet.

Gepatcht: Gemeinsamer Router bewertet positive oder ausreichend aktive Kandidaten trotz Precheck vollständig und schreibt spezifische Blocker; trade_allowed bleibt streng. UI-naher Controller-Lauf `run_20260623_163853`: 0 Trades, `optimizer_search_space_failed`, Best 0.06237, trade_allowed 0; Hauptblocker Aktivität/Target-Math/Net. Tests grün.

## 2026-06-23 - Finaler UI-Smoke/Report-Fix

UI-naher Controller-Lauf: `run_20260623_112707`, 0 Trades, `optimizer_search_space_failed`, `opportunity_mining=True`, 4829 Fenster/31 Cluster, Best-Candidates vorhanden; Kandidaten wurden getestet, aber verworfen wegen Aktivität/Target-Math/negativer Net.

Gepatcht: Gemeinsame Summary ignorierte bei 0 trade_allowed die Router-Best-Candidates und zeigte deshalb `Best training USDC/Tag=0.0000`. Summary nutzt jetzt `best_*_candidate`; neu berechnet: 0.06237 USDC/Tag. Tests grün: `compileall`, `pytest -q`.

## 2026-06-23 - Gemeinsamer Opportunity-Mining-Pfad repariert

Geprüft: `run_20260623_105958` nutzt denselben Backtest-/Router-/Optimizer-Code wie Full; kein Smoke-Sonderpfad. Schwellen-Patch greift (`minwin=14`, Target-Fenster 42/84), aber 0 Trades blieb.

Gepatcht: `opportunity_mining` zählte bisher MFE/MAE-Fenster, nutzte sie aber nicht als Suchraum. Gemeinsamer Router übergibt jetzt geminte Opportunity-Cluster an `_build_router_pass`. Tests grün: targeted, `compileall`, `pytest -q`.

## 2026-06-23 - UI-Smoke run_102333 Aktivitätsschwellen gepatcht

Geprüft: `run_20260623_102333` war echter `smoke_test`, 14d Training/7d Blindtest, `opportunity_mining=True`, 4829 Opportunity-Fenster; Kandidaten je Pass: primary 70, activity_expansion 18, target_activity 4, opportunity_mining 33. Best-Kandidatenfelder vorhanden.

Ursache/Patch: 0 Trades kamen nicht vom Button/Anschluss, sondern alle Kandidaten scheiterten an Aktivität/Target-Math/negativer Net. Router skaliert jetzt absolute Aktivitäts-/Trade-Schwellen auf Fensterdauer; 14d Training: 3 Trades/Tag = 42, 6 Trades/Tag = 84, nicht Jahres-Absolute. Tests grün: targeted, `compileall`, `pytest -q`.

## 2026-06-23 - UI/Pipeline Smoke-Test-Modus

Geändert: `BacktestUiSettings`/Pipeline haben `run_type`; Full bleibt `full_backtest`, Smoke ist `smoke_test` mit 2:1 Split (1/7/14/30 Tage Blindtest -> 2/14/28/60 Tage Training). UI hat Button `Smoke-Test starten` und Dauer-Auswahl.

Smoke nutzt dieselbe Pipeline/Engine/Cluster-Router wie Full; Reports/Summary/Run-Request markieren `run_type`. Kein Leistungsnachweis, keine Live-Freigabe, kein Blindtest-Lernen. Tests grün: `compileall`, `pytest -q`.

## 2026-06-23 - Smoke-Test neuer Router-Ablauf

Geprüft: UI-Pipeline nutzt aktuellen Cluster-Router; synthetischer Kurz-Smoke läuft ohne Full-Backtest, `opportunity_mining=True`, 180 Opportunity-Fenster, alle vier Suchpässe mit Kandidaten, keine alte 12-Trade-Auswahl, Blindtest ohne Lernen.

Gepatcht: `optimizer_search_space_failed` wird in Router-Diagnostics und Backtest-Summary korrekt weitergereicht statt auf `router_too_inactive` zu fallen. Tests grün: targeted Smoke/Summary, `compileall`, `pytest -q`.

## 2026-06-23 - Performance-Suchraum: Opportunity-Mining und Ziel-Aktivität

Geändert: Router sucht nach primary/activity/target jetzt zusätzlich training-only `opportunity_mining`; dazu Opportunity-Fenster per MFE/MAE, Aktivitätsklassen, Target-Relevanz aus Trades/Tag + Active-Days + Netto-Edge + Fee-Ratio, breitere aktive Kandidaten und best_target/best_fee_survivor.

Workflow: `memory-bank/NEXT_WORK_STATE.md` erstellt, `.clinerules/07_COST_DISCIPLINE_AND_WORKFLOW.md` ergänzt, `.clineignore` um Cache/Joblib/Pycache ergänzt. Kein Full-Backtest durch Cline.

## 2026-06-23 - run_061114 target_activity 0-Setup Diagnose

`run_20260623_061114`: completed, 100 -> 100 USDC, 0 trades, `optimizer_failed_to_find_target_relevant_search_space`; old 12-trade setup remained blocked.

Pass counts: primary 109 rows (61 target_math, 48 activity), activity_expansion 18 rows (13 target_math, 4 training_net, 1 activity), target_activity 4 rows (2 target_math, 2 training_net). `target_activity` ran wirklich, erzeugte aber keinen positiven Ersatz: hohe Aktivität war nach Fees negativ, positive Edge war viel zu selten.

Patched only diagnostics: rejection summary now stores pass-wise `search_pass_summary` plus `rejected_by_other`; no gate loosened, no fake trades, no V1 fallback, no blindtest learning.

Tests green: targeted router tests, `python -m compileall src tests`, `python -m pytest -q`. New Full-Backtest is sinnvoll only to emit improved diagnostics in a fresh run.

## 2026-06-22 - 0-trade optimizer failure handling and target-activity pass

Patched interpretation: 0 trades in 365d optimizer/backtest is `optimizer_failed_to_find_target_relevant_search_space`, not acceptable no_trade success.

Router now runs training-only search passes in order: primary, `activity_expansion`, then `target_activity` if still 0 trade_allowed setups. The added pass searches broader target-activity clusters with more active entry variants, without blindtest learning, fake trades, or V1 fallback.

Reports/diagnostics now expose best_found_candidate, best_activity_candidate, best_edge_candidate, best_balanced_candidate plus rejection counts for target_math/activity/profit_factor/training_net/deduplication.

Tests green: `python -m compileall src tests`; `python -m pytest -q`. Next Full-Backtest is sinnvoll.


## 2026-06-22 - Second training-only search pass after 0-trade run

`run_20260622_154319`: `0.00 USDC`, 0 trades, `router_too_inactive`; old 12-trade router was blocked, but no replacement setup was found. Report check: 109 candidates/rows, selected 0; 109 skipped by Full-Training precheck, 61 by target math and 48 by activity.

Patched Cluster Router rejection summary: rejected_by_target_math, rejected_by_activity, rejected_by_profit_factor, rejected_by_training_net, rejected_by_deduplication and top_nearly_valid_candidates.

Patched second training-only search pass `activity_expansion`: only starts when primary pass finds 0 setups; uses broader activity clusters and more active local setup variants. Blindtest remains frozen-router-only; no V1 fallback; old target-math-dead setups stay blocked.

Tests green: `python -m compileall src tests`; `python -m pytest -q`. Next Full-Backtest is sinnvoll.


## 2026-06-21 - Router-Auswahl und Laufzeit nach run_172844 gepatcht

Vergleich `run_20260621_111755` vs `run_20260621_172844`: beide wählten dieselben 2 Cluster, dasselbe Setup `cluster_router_situation_router_lb30_th0.006_tp0.012_sl0.006_hold240` und exakt dieselben 12 Entry-/Exit-Zeiten; Ergebnis wieder `-2.40 USDC`, 12 Trades, `target_math_not_reachable_current_activity`.

Ursache: neuer Suchraum wurde erzeugt, aber Scoring/Gates ließen seltene High-edge Setups weiter zu; Target-Awareness war nicht hart genug in der Auswahl. Zeitfresser: pro Cluster/Kandidat wurden Full-Training, Split-Training, Validation und 4 Robustness-Blöcke simuliert, auch wenn Full-Training bereits mathematisch unbrauchbar war.

Geändert: Setup-Kandidaten werden dedupliziert; Full-Training-Precheck überspringt teure Validation/Robustness für Varianten mit Zielmath-/Aktivitäts-/Edge-/PF-/Netto-Fail; Target-Math `required_net_per_trade > 10% Stake` blockiert jetzt `trade_allowed`.

Sicherheiten unverändert: kein V1-Fallback, frozen Router, kein Blindtest-Lernen, no_trade wenn kein approved Setup passt.

Tests grün: `python -m compileall src tests`; `python -m pytest -q`. Neuer UI-Backtest ist sinnvoll; erwartete echte Laufzeit sollte niedriger als 4-5h sein, genauer erst im Lauf messbar.


## 2026-06-21 - Performance-relevanter Cluster-Router Setup-Optimizer Patch nach run_111755

`run_20260621_111755` war nach 3h16m05s fertig: Start 100 USDC, Ende 97.60 USDC, PnL -2.40 USDC, 12 Trades. Der Progress-/Target-Math-/Diagnose-Patch funktionierte, verbesserte aber die Performance nicht; Hauptblocker bleibt Router-Inaktivität bzw. zu schwache lokale Setup-Optimierung.

Geändert: Cluster-Router Setup-Suchraum um mehrere lokale Varianten erweitert (Entry/TP/SL/Hold/Trailing), LONG-only Cluster-Erkennung um Recovery-Regime verbreitert, pro Setup training-only Target-Math (trades/day, net/trade, expected/day, required edge/activity, activity_gap, edge_gap, target_math_status, aktive Tage) berechnet.

Geändert: pro Cluster wird ein erlaubtes Setup jetzt nach training-only target-aware Score gewählt, nicht mehr nur nach Validation-Net/Trade; seltene 1-12 Trades/Jahr werden dadurch nicht mehr bevorzugt, wenn Aktivität/Zielmathe unplausibel ist.

Sicherheiten: Blindtest nutzt weiterhin nur frozen Router-Setups; kein V1-Fallback, kein diagnostic_only/research_only Handel, no_trade wenn kein approved Setup passt.

Tests grün: `python -m compileall src tests`; `python -m pytest -q`. Nächster UI-Backtest ist startklar.


## 2026-06-21 - Final user requested patch set after run 070352

Analyzed `run_20260621_070352`: `-2.398 USDC`, 12 trades, 2 frozen setups, 61 clusters, 997519 opportunity events. Blocker is target math/activity: at 12 trades/year, 3 USDC/day requires `91.25 USDC` net/trade; blindtest gross was already slightly negative and fees completed the loss.

Patched progress persistence: `progress.json` now stores `runtime_seconds` and `estimated_remaining_seconds`; UI completed/running result loader reads these fields instead of only estimating from file time.

Patched target awareness: `cluster_router_diagnostics.json` now includes target 3.0/day, lower target 1.5/day, trades/day, net/trade, required net/trade for 1/day and 3/day, required trades/day at current edge, target activity gap, target edge gap and target math status.

Patched trade diagnostics: Cluster Router blindtest trades now include `trade_id`, `cluster_id`, `setup_id`, `fees`, `slippage`, `mfe`, `mae`, `hold_minutes`, `context_status`, `entry_reason`, `reject_reason` using high/low candles between entry and exit for MFE/MAE.

Patched stricter summary statuses: Cluster Router summary now separates positive/negative/too-inactive/generalization states instead of always reporting `frozen_router_trade_allowed` when it merely traded.

Added/updated tests for target diagnostics, trade diagnostic fields, no fallback semantics and progress fields. Tests green: `python -m pytest -q`; compile green: `python -m compileall src tests`.

Cleanup: removed `.pytest_cache` and `.ruff_cache`; did not delete raw data, configs, docs, reports, memory-bank or tests. Earlier root temp files and old structure dump were already removed.

## 2026-06-20 - Final pre-limit patch after run 193025

Analyzed latest completed `run_20260620_193025`: result `0 trades`, `0.0 USDC/day`, `no_trade_allowed_cluster_setup`; latest 4-block robustness patch was used but over-blocked every setup.

Root cause: ETHUSDC high-edge setups are sparse. Strict requirement for 3 active/positive chronological training blocks blocked rare setups with strong full training + validation, e.g. `trend_mid|mom_high|pullback|vol_high` with `training_net_per_trade 0.469`, `validation_net_per_trade 0.639`, but only 2 active/positive robustness blocks.

Patched final router approval logic to preserve strict multi-block path but add a separate `sparse_high_edge` approval mode: rare setups may pass only if train/full/split/validation edges are high, validation PF >= 1.60, all active robustness blocks are positive, and worst active block net/trade > 0.

This final patch is meant to fix the `0 trades` failure without returning to the 132-trade fee-churn failure from `run_20260620_152836`.

Deleted token-heavy/unneeded root files: tmp_cluster_router_run*.out/err, tmp_run_ui_backtest.out/err, tmp_run_ui_backtest.py, pytest_out.txt, context_ensure logs, `projektstruktur.txt`.

Rewrote `memory-bank/activeContext.md` to contain only current truth, latest runs, current code state, UI state, data state and next action.

Tests green: `python -m pytest tests/test_cluster_router_report.py tests/test_backtest_summary.py -q`, `python -m compileall src tests`, `python -m pytest -q`.

## 2026-06-20 - Multi-block training robustness patched

Patched Cluster Router with 4 chronological robustness blocks inside the 730-day training window; setup approval now requires at least 3 active/positive blocks and worst active block net-per-trade >= -0.05.

Reports now store `robustness_blocks`, active/positive block counts and worst active block net-per-trade per cluster/setup row.

Tests green: `python -m pytest tests/test_cluster_router_report.py tests/test_backtest_summary.py -q`, `python -m compileall src tests`, `python -m pytest -q`; next UI run should test multi-block robustness.

## 2026-06-20 - Run 170135 completed and patch usage verified

Verified `run_20260620_170135` completed with current patches: 61 clusters, 19 setup candidates, families `momentum_breakout/range_breakout/situation_router/trend_pullback`, net-per-trade fields present, and `cluster_router_diagnostics.json` written.

Result: Cluster Router `-7.996 USDC`, `-0.0219 USDC/day`, 30 trades; gross already negative `-2.01`, fees `5.99`, target gap `1103 USDC`.

Conclusion: patches were used, but stronger gates reduced fee churn versus 132-trade run while still not finding enough/positive blindtest edge; next work must address training-to-blindtest regime robustness, not UI/data.

## 2026-06-20 - Running run always takes UI priority

Changed UI behavior: if the active run is `running`, it always overrides latest-completed view and is displayed/updated because that is what the user needs during a backtest.

`Letzten Lauf laden` now refuses to hide a currently running active run; tests green: `python -m pytest tests/test_ui_app_import.py tests/test_backtest_ui_controller.py -q`, `python -m compileall src tests`, `python -m pytest -q`; UI restarted.

## 2026-06-20 - UI new active run text refresh fixed

Fixed UI refresh rule: when active run ID changes, the detail text now refreshes once even if the new run is still `running`; after that, running updates only top labels.

Tests green: `python -m pytest tests/test_ui_app_import.py tests/test_backtest_ui_controller.py -q`, `python -m compileall src tests`, `python -m pytest -q`; UI restarted and sees `run_20260620_170135` running.

## 2026-06-20 - Candidate selection and diagnostics patched, run 170135 started

Patched router selection: it now evaluates all setup candidates per cluster, selects the best candidate that actually passes train/validation edge gates, and only falls back to best rejected row for reporting.

Added stronger R/R setup candidates and `cluster_router_diagnostics.json` with target gap, fee/gross warning, exit/candidate breakdown and top rejected clusters.

Tests green: `python -m pytest tests/test_cluster_router_report.py tests/test_preparation_pipeline.py tests/test_backtest_summary.py -q`, `python -m compileall src tests`, `python -m pytest -q`; UI restarted and new run `run_20260620_170135` is running at data preparation.

## 2026-06-20 - Run 152836 analyzed and edge gates patched

Analyzed `run_20260620_152836`: expanded router created 132 trades but only `+0.30 USDC` gross, `26.36 USDC` fees, `-26.06 USDC` net; more trades without edge worsened result.

Patched Cluster Router gates to require stronger net edge: PF `>=1.25`, validation PF `>=1.35`, positive train split, and at least `0.15 USDC` net per trade in full training/train split/validation.

Added report fields for train/validation net-per-trade and win-rate; tests green: `python -m pytest tests/test_cluster_router_report.py tests/test_backtest_summary.py -q`, `python -m compileall src tests`, `python -m pytest -q`.

## 2026-06-20 - Router opportunity/setup space expanded

Patched Cluster Router toward the 3 USDC/day goal: cluster keys now include trend_low/mom_recover/deep_pullback/impulse regimes instead of only strong uptrend regimes.

Expanded local setup search from only `situation_router` to multiple LONG-only setup families: momentum_breakout, range_breakout, trend_pullback and situation_router; no forced trades and training+validation gates remain required.

Patched Strategy V1 per-entry candidate execution to start after the largest per-entry required lookback; tests green: `python -m pytest tests/test_strategy_v1.py tests/test_cluster_router_report.py tests/test_backtest_summary.py -q`, `python -m compileall src tests`, `python -m pytest -q`.

## 2026-06-20 - UI running refresh no longer rewrites detail text

Changed UI behavior: while a run is `running`, auto-refresh updates only the top status labels/progress/ETA and no longer rewrites the large dashboard text area.

The detail text is rewritten on explicit user actions or once when the run transitions to completed/failed; this prevents scroll jumping during reading.

Tests green: `python -m pytest tests/test_ui_app_import.py tests/test_backtest_ui_controller.py -q`, `python -m pytest -q`, `python -m compileall src tests`; UI restarted.

## 2026-06-20 - UI scroll position preserved

Patched dashboard text refresh to preserve the current `Text.yview()` scroll position after auto-refresh, preventing jumps back to top while reading.

Tests green: `python -m pytest tests/test_ui_app_import.py tests/test_backtest_ui_controller.py -q`, `python -m compileall src tests`, `python -m pytest -q`; UI restarted.

## 2026-06-20 - UI reading pause added and target gap quantified

Added UI button `Anzeige pausieren` / `Anzeige weiter aktualisieren`; when paused, auto-refresh no longer rewrites the dashboard text area while the user scrolls/reads.

Tests green: `python -m pytest tests/test_ui_app_import.py tests/test_backtest_ui_controller.py -q`, `python -m compileall src tests`, `python -m pytest -q`; UI restarted.

Quantified `run_20260620_141818`: 24 trades, gross `+1.10 USDC`, fees `4.79`, net `-3.69`; 3 USDC/day over 365d requires `+1095 USDC`, impossible with 24 trades unless `+45.63 USDC/trade`.

## 2026-06-20 - UI stale running refresh fixed

Fixed UI auto-refresh bug: it only refreshed while result status was `running`, so when a run completed the UI could remain visually stuck at `98% running`.

Now current active view refreshes any active result status, including transition from running to completed; tests green: `python -m pytest tests/test_ui_app_import.py tests/test_backtest_ui_controller.py -q`, `python -m compileall src tests`, `python -m pytest -q`.

Restarted UI; `run_20260620_141818` backend is completed with `-3.6944 USDC`, `-0.0101 USDC/day`, 24 trades.

## 2026-06-20 - Progress callback patched and run 141818 started

Patched Cluster Router to emit/persist per-cluster progress during setup search, so UI can show progress through the long router phase.

Tests green: `python -m pytest tests/test_cluster_router_report.py tests/test_preparation_pipeline.py tests/test_backtest_ui_controller.py -q`, `python -m compileall src tests`, `python -m pytest -q`.

Restarted UI and started new run `run_20260620_141818`; UI loader sees it running at `strategy_v0` 60% with ETA.

## 2026-06-20 - Run 134307 checked

Checked `run_20260620_134307`: Cluster Router `-7.49 USDC`, `-0.0205 USDC/day`, 31 trades, 3 frozen setups; best full month `+0.998 USDC`, worst full month `-5.591 USDC`.

The report does not contain the newest setup-validation fields, so it was not a valid test of the latest per-cluster validation patch.

Regenerated summary target ratio against 3.0 USDC/day and restarted UI so the label should show `Zielquote zu 3.0 USDC/Tag`.

## 2026-06-20 - Per-cluster setup execution and validation added

Patched Strategy V1 to allow per-entry candidates, so the frozen Router can execute each Cluster with its locally learned setup instead of one global setup.

Cluster Router now splits the 730-day training internally: first 75% setup-train, last 25% setup-validation; `trade_allowed` requires positive full training and positive validation after fees.

Tests green: `python -m pytest tests/test_strategy_v1.py tests/test_cluster_router_report.py tests/test_backtest_summary.py -q`, `python -m compileall src tests`, `python -m pytest -q`; activeContext updated for restart handoff.

## 2026-06-20 - UI target wording audited

Audited `run_20260620_130018`: split is correct 730d training then 365d blindtest, data usage matches reports, completed-run progress fields are intentionally empty.

Patched Cluster Router summary target ratio from 1.5 to the user goal `3.0 USDC/day` and changed UI label to `Zielquote zu 3.0 USDC/Tag`; regenerated summary for `run_20260620_130018`.

Tests green: `python -m pytest tests/test_backtest_summary.py tests/test_ui_app_import.py -q`, `python -m compileall src tests`, `python -m pytest -q`.

## 2026-06-20 - UI ETA for running backtests added

Added running-run UI fields for progress percent, progress stage, elapsed runtime and estimated remaining runtime based on `progress.json` and run start file time.

Tests green: `python -m pytest tests/test_backtest_ui_controller.py tests/test_ui_app_import.py -q`, `python -m compileall src tests`, `python -m pytest -q`; UI restarted.

`run_20260620_122605` completed while investigating: Cluster Router result `-7.49 USDC`, `-0.0205 USDC/day`, 31 trades.

## 2026-06-20 - Long phase progress persistence fixed

Observed `run_20260620_122605` is not stuck: Strategy V1 finished and Cluster Router setup search is running, but `progress.json` stayed at split/75%.

Patched pipeline to persist progress stages after split: buy_hold, strategy_v0, strategy_v1, cluster_router; manually updated current run progress to `cluster_router` 89%.

Tests green after syntax fix: `python -m pytest tests/test_preparation_pipeline.py tests/test_backtest_ui_controller.py -q`, `python -m compileall src tests`, `python -m pytest -q`.

## 2026-06-20 - Local setup search per cluster added

Expanded Cluster Router training to test multiple fixed LONG-only setup candidates per cluster on the full timeline; selected setup details are stored in router artifact/reports.

Tests green: `python -m pytest tests/test_cluster_router_report.py tests/test_backtest_summary.py -q`, `python -m compileall src tests`, `python -m pytest -q`.

Restarted UI completely and started new central backend run `run_20260620_122605`; UI loader sees it as `running` at data preparation.

## 2026-06-20 - UI active/latest toggle patched

Patched UI run view: auto-refreshes current active run every 5 seconds when not viewing latest completed, and refresh button toggles `Letzten Lauf laden` / `Aktuellen Lauf anzeigen`.

Tests green: `python -m pytest tests/test_backtest_ui_controller.py tests/test_ui_app_import.py -q`, `python -m compileall src tests`, `python -m pytest -q`; restarted UI via BAT.

Observed new run `run_20260620_110015` completed after full-timeline gate: Cluster Router `0 trades / 0.0 USDC/day` because no setup passed; Strategy V1 was `-5.02 USDC`.

## 2026-06-20 - Cluster router period diagnostics added and new run started

Added Cluster Router blindtest daily/monthly distributions plus best/worst day and best/worst full month fields; summary now carries Cluster Router positive/negative day counts and best/worst day PnL.

Tests green: `python -m pytest tests/test_cluster_router_report.py tests/test_backtest_summary.py tests/test_preparation_pipeline.py -q`, `python -m compileall src tests`, `python -m pytest -q`.

Started new central backend run `run_20260620_110015`; runtime/UI loader shows it as `running` at data preparation, and `cluster_router_report.json` is not available until completion.

## 2026-06-20 - Cluster router full-timeline gate patched

Patched Cluster Router to run setup tests and blindtest on the full candle timeline with `allowed_entry_times`, instead of compressing cluster candles.

Added Strategy V1 entry-time gate test; tests green: `python -m pytest tests/test_strategy_v1.py tests/test_cluster_router_report.py tests/test_backtest_summary.py -q`, `python -m compileall src tests`, `python -m pytest -q`.

Started UI via `ETHUSDC_BotV2_UI_starten.bat`; next backtest should be started with the UI button so the user sees the running run.

## 2026-06-20 - Cluster router summary preferred

Evaluated `run_20260620_065500`: Strategy V1 stayed `-6.66 USDC`, but new Cluster Router report produced `+21.93 USDC`, `2.5373 USDC/day`, 82 trades, 2 frozen setups.

Patched `backtest_summary.json` priority to prefer `cluster_router_report.json` over Strategy V1 when present, then regenerated summary for `run_20260620_065500`.

Tests green: `python -m pytest tests/test_backtest_summary.py tests/test_backtest_ui_controller.py -q`, `python -m compileall src tests`, `python -m pytest -q`; UI loader now shows Cluster Router result.

## 2026-06-20 - Running run visibility fixed

Started controller backtest `run_20260620_065500`; runtime state is running, but UI last-run loader previously showed old completed run because no summary exists until completion.

Patched UI controller/app so active running runs without `backtest_summary.json` show via `progress.json` instead of falling back to old summaries.

Tests green: `python -m pytest tests/test_backtest_ui_controller.py tests/test_ui_app_import.py -q`, `python -m pytest -q`; verified loader returns `run_20260620_065500 running`.

## 2026-06-19 - Minimal cluster-router report added

Added first time-safe training-only `cluster_router_report.json` path: opportunity detection, simple recurring situation buckets, local setup approval, frozen router artifact, blindtest through allowed clusters only.

Integrated into existing preparation pipeline without new start path and without live/order collection; no new backtest started.

Tests green: `python -m pytest tests/test_cluster_router_report.py tests/test_preparation_pipeline.py tests/test_backtest_ui_controller.py -q`, `python -m compileall src tests`, `python -m pytest -q`.

## 2026-06-19 - Diagnose run 173059 analyzed

Analyzed `run_20260619_173059`: selected `situation_router_lb20_th0.01_tp0.018_ctx`, context filter true, training `+10.06 USDC` / `0.01378 USDC/day`, blindtest `-6.66 USDC` / `-0.01826 USDC/day` / 71 trades.

Gross blindtest PnL was positive `+7.52 USDC`, but fees `14.19 USDC` turned it negative; stop-loss exits caused `-42.92 USDC` net while take-profit exits added `+36.70 USDC` net.

`target_model_chain` still proves no real Situation->Cluster->Setup->Router chain: router_frozen false, setup_learning_done false, cluster_count 0.

## 2026-06-19 - Strategy V1 reporting gap closed

No new backtest started. Added next-run diagnostics for blindtest trades, gross PnL, fees, slippage placeholder, exit reasons, signal/no-trade counts, daily/monthly distributions and candidate train/blind outcomes.

Added `target_model_chain` report section showing current implementation is still Strategy V1 candidate search and whether Situation/Cluster/Setup/Router chain exists.

Tests green: `python -m pytest tests/test_strategy_v1.py tests/test_strategy_v1_report.py -q`, `python -m compileall src tests`, `python -m pytest -q`.

## 2026-06-19 - 3 USDC/day audit analysis

Audited `run_20260619_152612`: completed full 730d/365d split, valid ETHUSDC/BTCUSDC/ETHBTC/exchange_info, selected `trend_pullback_lb45_th0.01_tp0.015`, blindtest `-5.02 USDC` / `-0.0138 USDC/day` / 28 trades.

Main finding: data/split did not break; current Strategy V1 search space is far below target even in training (`0.0119 USDC/day`, only `0.79%` of 1.5 USDC/day lower target), and it is still strategy-candidate search rather than full Situation->Cluster->Router->Setup model.

Live/microstructure data is not collected/used; reports correctly block bookTicker/orderbook as live_collection_required and aggTrades/trades as not available for current historical blindtest.

## 2026-06-19 - UI last-run fallback fixed

Found local runtime state pointing to unfinished `run_20260619_155916` without `backtest_summary.json`, so `Letzten Lauf laden` returned empty.

Changed UI controller to first try runtime active run, then fall back to the newest report folder with `backtest_summary.json`.

Verified real load now returns `run_20260619_152612`; tests: `python -m pytest tests/test_backtest_ui_controller.py -q`, `python -m compileall src tests`.

## 2026-06-19 - Target feasibility diagnosis added

Checked full path: latest 1095-day split is relative to current data; ETHUSDC/exchange_info/BTCUSDC/ETHBTC are used; no fixed historical dates found.

Added report/UI fields for best training USDC/day and target feasibility against `1.5-3.0 USDC/day`.

Run `run_20260619_152612`: completed, same selected `trend_pullback_lb45_th0.01_tp0.015`, blindtest `-5.02 USDC`, best training `0.0119 USDC/day`, status `target_out_of_reach_current_space`.

Conclusion: current Strategy V1 search space is ~0.8% of the 1.5 USDC/day lower target even in training; next blocker is model class/search space, not UI/data/split.

## 2026-06-19 - Trend-pullback threshold bug fixed

Found Strategy V1 bug: `trend_pullback` mostly ignored `entry_threshold_pct`, causing noisy/fee-heavy trades and a fully negative family.

Fixed trend-pullback entry to require threshold-sized long trend and recovery; added targeted nearby trend-pullback candidates. Tests green: `compileall`, full `pytest -q`.

Backtests: stale interrupted `run_20260619_093343`; clean `run_20260619_094207` improved to robust training score `+8.0711`, selected `trend_pullback_lb45_th0.01_tp0.015`, blindtest `-5.02 USDC` / 28 trades.

Follow-up `run_20260619_095824` with 588 candidates found same winner/result; next blocker is poor generalization despite robust-positive training, not data/split.

## 2026-06-19 - Strategy V1 candidate-space extended again

Checked `run_20260619_053202`: 400 candidates, all families negative after intrabar/stability; best was range_breakout final score `-1.4644`.

Extended normal candidate-space to 560 candidates with extra TP/SL/Hold combinations and optional trailing-stop exits; intrabar TP/SL and stability scoring remain active.

Tests green: `python -m compileall src tests`; `python -m pytest -q`.

Started central UI-controller backtest `run_20260619_062700`: completed, data usable/used for ETHUSDC/exchange_info/BTCUSDC/ETHBTC, selected same range candidate, `-9.68 USDC`, 21 trades, still `no_robust_positive_candidate`.

Next blocker: Strategy V1 entry/setup families are not expressive enough; added exit variants did not beat existing range_breakout.

## 2026-06-18 - Clean restart stability run checked

Checked `run_20260618_164530`: data valid/used, result `+2.30 USDC` / 8 trades, selected `range_breakout_lb360_th0.01_tp0.015`.

Stability rule was active and reported; selection used `adjusted_score_final`.

No UI selection bug found. Mini-fix: raised training low-activity penalty from `0.02` to `0.08` per missing trade under 24 to avoid too-rare candidates overriding minimum activity.

## 2026-06-18 - UI data-check wording clarified

Checked local data ages: ETHUSDC about 5.4 days old, BTCUSDC/ETHBTC under 1 day, exchange_info about 5.4 days old; all below 7-day update threshold.

No repeated candle-download bug found. UI start text now says local data check; download is only implied by real download/update progress events.

## 2026-06-18 - New UI run after 0.08 low-activity penalty

Checked `run_20260618_170408`: valid data, selected `range_breakout_lb30_th0.01_tp0.015`, 31 training trades, final training score `3.1517`.

Result: `-5.96 USDC` / 20 blindtest trades. Low-activity fix worked mechanically; next issue is poor generalization of current candidate space/scoring, not data validity.

## 2026-06-18 - Training stability scoring bug fixed

Found scoring bug: inactive training months and negative-month dominance were too weak, and sub-24-trade candidates could re-win after stability changes.

Fixed training-only score: inactive month penalty, stronger negative-month dominance penalty, and explicit sub-24-trade robustness penalty. No new backtest started.

## 2026-06-18 - Strategy V1 intrabar exit simulation fixed

Checked `run_20260618_172138`: fix active but same selected candidate/result; report generation took about 5 minutes, not obviously fake-fast.

Found core simulation bug: TP/SL used only candle close, ignoring 1m high/low. Fixed to use OHLC intrabar exits; if TP and SL both touch in same candle, stop-loss wins conservatively.

Checked new UI run `run_20260618_200150`: valid data, same selected candidate, blindtest `-8.48 USDC` / 20 trades. Intrabar fix reduced selected training raw score from about `+3.52` to `+0.28`; final training score is negative, so current normal candidate space has no robust positive candidate.

Patch recovery checked after Ctrl+C: Strategy V1 candidate-space extension and `no_robust_positive_candidate` report rule are present; intrabar and stability scoring remain active. No backtest started.


## 2026-06-12

Created clean project structure.

Created:
- .clineignore
- .clinerules
- docs
- memory-bank

No bot code created yet.
Old READMEs are not used as truth.

## 2026-06-12 - Foundation test added

Created:
- tests/test_project_foundation.py

Purpose:
- Verify required foundation files exist.
- Verify minimal confirmed truth is present.
- Verify old READMEs are not treated as truth.

No trading logic created.

## 2026-06-12 - Foundation consistency check

Checked:
- .clinerules
- README.md
- docs
- memory-bank

Result:
- No contradictions found in the new project basis.
- ETHUSDC / USDC / Binance Spot / LONG-only is clear.
- 730 days training plus 365 days blindtest is clear.
- Blindtest must not learn.
- No capital stop because of calculated loss.
- UI / Paper / Test Trade / Live come later.
- Old READMEs, old reports, old code and old bot folders are not truth.

## 2026-06-12 - Minimal common skeleton created

Created:
- src/common/paths.py
- src/common/config.py
- src/common/logging.py
- tests/test_common_skeleton.py

Updated:
- memory-bank/techContext.md

Scope:
- Technical project base only.
- No trading code.
- No backtest code.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Test:
- python -m pytest
- Result: 10 passed in 0.03s

## 2026-06-12 - Minimal quality checks stabilized

Checked:
- python -m pytest
- python -m ruff check .
- python -m ruff format --check .

Adjusted:
- Ruff-only import / format cleanup.

Final result:
- pytest: 10 passed in 0.04s
- ruff check: All checks passed.
- ruff format --check: 13 files already formatted.

Scope:
- Technical quality standard only.
- No trading code.
- No backtest code.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

## 2026-06-12 - Run identity and report paths created

Created:
- src/common/run_identity.py
- src/common/report_paths.py
- tests/test_run_identity_and_report_paths.py

Purpose:
- Technical run IDs.
- Isolated report directories under reports/backtests/<run_id>.
- Minimal run_id validation against unsafe paths.

Scope:
- Technical run/report foundation only.
- No trading code.
- No backtest code.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 16 passed in 0.04s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 16 files already formatted.

## 2026-06-12 - Runtime state foundation created

Created:
- src/common/runtime_state.py
- tests/test_runtime_state.py

Purpose:
- Technical runtime state file at configs/runtime_state.json.
- Minimal status validation for idle, running, completed and failed.
- Minimal active_run_id validation against unsafe paths.

Scope:
- Technical runtime-state foundation only.
- No trading code.
- No backtest code.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 23 passed in 0.05s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 18 files already formatted.

## 2026-06-12 - Blindtest and Test Trade purpose documented

Updated documentation:
- docs/BACKTEST_TRUTH.md
- docs/UI_TRUTH.md
- memory-bank/productContext.md

Confirmed additions:
- Blindtest should later provide an expectation frame for Paper and Live, not only total profit or loss.
- Paper/Live results clearly worse or better than the blindtest frame are analysis triggers.
- Later Test Trade button means exactly one complete trade after conscious configuration takeover, with diagnostic comparison data, then automatic stop.

Scope:
- Documentation only.
- No code changed.

## 2026-06-12 - Blindtest expectation report schema created

Created:
- src/reports/blindtest_expectation_schema.py
- tests/test_blindtest_expectation_schema.py

Adjusted:
- .gitignore now ignores only root runtime reports via /reports/ so src/reports/ can be versioned.

Purpose:
- Technical schema for future blindtest expectation reports.
- Stores monthly results and expectation range fields.
- Allows negative pnl, final_result and total_pnl.
- Rejects negative trade and no_trade counts.

Scope:
- Schema and validation only.
- No trading code.
- No backtest calculation.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 30 passed in 0.06s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 22 files already formatted.

## 2026-06-12 - Blindtest expectation report IO created

Created:
- src/reports/blindtest_expectation_io.py
- tests/test_blindtest_expectation_io.py

Purpose:
- Save BlindtestExpectationSummary as readable JSON in reports/backtests/<run_id>/blindtest_expectation.json.
- Load the same JSON back through the schema.

Scope:
- Technical writer/reader only.
- No trading code.
- No backtest calculation.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 36 passed in 0.07s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 24 files already formatted.

## 2026-06-12 - Backtest run request schema created

Created:
- src/backtest/run_request.py
- tests/test_backtest_run_request.py

Purpose:
- Technical request schema for a later Backtest start.
- Validates confirmed ETHUSDC / USDC / Binance Spot / 730 / 365 settings.
- Rejects forbidden modes and unsafe run_id values.

Scope:
- Schema and validation only.
- No trading code.
- No backtest execution.
- No backtest calculation.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 50 passed in 0.08s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 26 files already formatted.

## 2026-06-12 - Backtest run request IO created

Created:
- src/backtest/run_request_io.py
- tests/test_backtest_run_request_io.py

Purpose:
- Save BacktestRunRequest as readable JSON in reports/backtests/<run_id>/run_request.json.
- Load the same JSON back through the request schema.

Scope:
- Technical writer/reader only.
- No trading code.
- No backtest execution.
- No backtest calculation.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 58 passed in 0.10s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 28 files already formatted.

## 2026-06-12 - Backtest run initialization created

Created:
- src/backtest/run_initializer.py
- tests/test_backtest_run_initializer.py

Purpose:
- Create a new run_id.
- Create a default BacktestRunRequest.
- Create the Run-Report folder.
- Save run_request.json.
- Set runtime_state.json to running with active_run_id.

Scope:
- Technical initialization only.
- No trading code.
- No real backtest.
- No backtest calculation.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 68 passed in 0.13s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 30 files already formatted.

## 2026-06-12 - Backtest run finalization created

Created:
- src/backtest/run_finalizer.py
- tests/test_backtest_run_finalizer.py

Purpose:
- Mark a run as completed in runtime_state.json.
- Mark a run as failed in runtime_state.json with last_error.
- Ensure the Run-Report folder exists.

Scope:
- Technical finalization only.
- No trading code.
- No real backtest.
- No backtest calculation.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 76 passed in 0.15s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 32 files already formatted.

## 2026-06-12 - Short handoff rules added

Updated:
- .clinerules/04-token-discipline.md
- .clinerules/05-testing-and-handoff.md

Purpose:
- Final reports max 10 lines.
- Use Changed / Tests / Result / Next format.
- Avoid repeated long negative lists unless there is risk.
- Closely related files may be handled in one task.

## 2026-06-12 - Backtest run progress created

Created:
- src/backtest/run_progress.py
- tests/test_backtest_run_progress.py

Purpose:
- Save and load technical run progress in reports/backtests/<run_id>/progress.json.

Tests:
- python -m pytest
- python -m ruff check . --no-cache
- python -m ruff format --check . --no-cache

## 2026-06-12 - Candle schema and dataset validation created

Created:
- src/data/candle_schema.py
- src/data/candle_dataset.py
- tests/test_candle_schema.py
- tests/test_candle_dataset.py

Purpose:
- Validate technical ETHUSDC 1m candle data contracts before any later data loading.

## 2026-06-12 - Candle CSV IO created

Created:
- src/data/candle_csv_io.py
- tests/test_candle_csv_io.py

Purpose:
- Save and load local ETHUSDC 1m candle datasets as CSV without download or Binance access.

## 2026-06-12 - Candle quality report created

Created:
- src/data/candle_quality.py
- tests/test_candle_quality.py

Purpose:
- Build a technical quality report for local ETHUSDC 1m CandleDataset data.

## 2026-06-12 - Local candle data catalog created

Created:
- src/data/data_catalog.py
- tests/test_data_catalog.py

Purpose:
- Reference local ETHUSDC 1m candle CSV files via configs/data_catalog.json.

## 2026-06-12 - Local candle loader created

Created:
- src/data/local_candle_loader.py
- tests/test_local_candle_loader.py

Purpose:
- Load local ETHUSDC 1m CandleDataset data through configs/data_catalog.json and build quality reports.

## 2026-06-12 - Data preparation report created

Created:
- src/data/data_preparation_report.py
- tests/test_data_preparation_report.py

Purpose:
- Save/load a technical local candle data readiness report per run.

## 2026-06-12 - Test runtime optimized

Changed:
- tests/test_candle_quality.py
- src/data/candle_quality.py

Purpose:
- Avoid generating a full 730+365 day candle list in unit tests while keeping EXPECTED_MIN_CANDLES unchanged.

## 2026-06-12 - Data preparation runtime optimized

Changed:
- tests/test_data_preparation_report.py
- src/data/data_preparation_report.py

Purpose:
- Avoid generating and writing a full 730+365 day candle CSV in unit tests while keeping EXPECTED_MIN_CANDLES unchanged.

## 2026-06-12 - Train/blind candle split created

Created:
- src/data/train_blind_split.py
- tests/test_train_blind_split.py

Purpose:
- Split ETHUSDC 1m CandleDataset into technical 730 day training and 365 day blindtest windows.

## 2026-06-12 - Train/blind split report created

Created:
- src/data/train_blind_split_report.py
- tests/test_train_blind_split_report.py

Purpose:
- Save/load technical run report for training and blindtest candle windows.

## 2026-06-12 - Backtest preparation pipeline created

Created:
- src/backtest/preparation_pipeline.py
- tests/test_preparation_pipeline.py

Purpose:
- Run technical preparation: initialize run, load local candles, save data and split reports, update progress, finalize run.

## 2026-06-12 - Buy-and-Hold benchmark created

Created:
- src/backtest/buy_hold_benchmark.py
- tests/test_buy_hold_benchmark.py

Purpose:
- Calculate and save a simple LONG-only Spot Buy-and-Hold benchmark for the blindtest window.

## 2026-06-12 - Preparation pipeline benchmark extended

Changed:
- src/backtest/preparation_pipeline.py
- tests/test_preparation_pipeline.py

Purpose:
- Successful preparation now also saves buy_hold_benchmark_report.json.

## 2026-06-12 - Backtest summary report created

Created:
- src/reports/backtest_summary.py
- tests/test_backtest_summary.py

Purpose:
- Build/save/load a compact UI-readable summary from data, split and Buy-and-Hold reports.

## 2026-06-12 - Pipeline summary output added

Changed:
- src/backtest/preparation_pipeline.py
- tests/test_preparation_pipeline.py

Purpose:
- Pipeline now saves backtest_summary.json for successful runs and data-preparation failures when possible.

## 2026-06-12 - Minimal Tkinter benchmark UI created

Created:
- src/ui/backtest_ui_controller.py
- src/ui/app.py
- tests/test_backtest_ui_controller.py

Purpose:
- Start existing benchmark pipeline from Tkinter and display BacktestSummary values.

## 2026-06-12 - Binance public kline downloader created

Created:
- src/data/binance_kline_client.py
- src/data/binance_candle_downloader.py
- tests/test_binance_kline_client.py
- tests/test_binance_candle_downloader.py

Purpose:
- Download public Binance Spot ETHUSDC 1m klines to local CSV and update data_catalog.json.

## 2026-06-12 - UI data download controller added

Created/changed:
- src/ui/data_download_controller.py
- src/ui/app.py
- tests/test_data_download_controller.py
- tests/test_ui_app_import.py

Purpose:
- UI can trigger public ETHUSDC 1m data download/update before benchmark backtest.

## 2026-06-12 - Download progress added

Changed:
- src/data/binance_candle_downloader.py
- src/ui/data_download_controller.py
- src/ui/app.py
- tests/test_binance_candle_downloader.py
- tests/test_data_download_controller.py

Purpose:
- ETHUSDC 1m download now reports loaded candles, percent progress and latest timestamp to the UI.

## 2026-06-12 - Windows UI launcher added

Created/changed:
- ETHUSDC_BotV2_UI_starten.bat
- README.md
- tests/test_windows_launcher.py

Purpose:
- Start the Tkinter UI by double-clicking a Windows batch file or via python -m src.ui.app.

## 2026-06-12 - Backtest dashboard UI improved

Changed:
- src/ui/app.py
- src/ui/backtest_ui_controller.py
- tests/test_backtest_ui_controller.py

Purpose:
- UI now shows a larger scrollable dashboard with last run, data quality, windows and Buy-&-Hold sections.

## 2026-06-12 - Strategy V0 training/blindtest engine added

Created/changed:
- src/backtest/strategy_v0.py
- src/backtest/strategy_v0_report.py
- src/backtest/preparation_pipeline.py
- src/reports/backtest_summary.py
- strategy/pipeline/summary tests

Purpose:
- Train fixed LONG-only Strategy V0 candidates, freeze best training candidate, run blindtest, save report, and prefer V0 in summary.

## 2026-06-12 - Incremental ETHUSDC 1m update added

Changed:
- src/data/binance_candle_downloader.py
- src/ui/data_download_controller.py
- tests/test_binance_candle_downloader.py
- tests/test_data_download_controller.py

Purpose:
- Existing local ETHUSDC 1m CSVs are now updated incrementally; full download only happens when local data is missing.

## 2026-06-12 - Strategy V1 fixed-stake backtest added

Created/changed:
- src/backtest/strategy_v1.py
- src/backtest/strategy_v1_report.py
- src/backtest/preparation_pipeline.py
- src/reports/backtest_summary.py
- Strategy V1 report/pipeline/summary tests

Purpose:
- Compare multiple LONG-only Strategy V1 families on training, freeze best candidate, blindtest with fixed 100 USDC stake, and prefer V1 in summary.

## 2026-06-12 - Backtest data ensure flow added

Created/changed:
- src/data/candle_data_ensure.py
- UI data/backtest controllers and Tkinter app
- preparation pipeline and Strategy V1 report stake/profile handling
- related tests

Purpose:
- Backtest start now checks/updates ETHUSDC 1m data before the pipeline and blocks runs with insufficient candles.

## 2026-06-12 - UI workflow progress and error handling improved

Changed:
- Backtest is now the central UI action; data check/update runs automatically.
- Free positive Stake USDC input added next to presets.
- UI progress callbacks show data check, download/update, pipeline, training, blindtest and completion/failure phases.
- Binance/network timeout errors are mapped to a clear user message.

Purpose:
- Avoid silent runs, separate required data loading, and unclear timeout failures in real UI use.

## 2026-06-12 - Stake input simplified

Changed:
- Removed preset stake dropdown from normal UI workflow.
- UI now has one field: Einsatz pro Trade (USDC), default 100.
- Any positive numeric stake is accepted and passed to Strategy V1.

Purpose:
- Reduce UI confusion while keeping automatic data ensure before backtest start.

## 2026-06-12 - USDC truth and Binance resume hardened

Changed:
- User-facing stake text now uses USDC only.
- Strategy V1 stake fields now use generic quote naming.
- Binance kline client has explicit request timeout/error handling.
- Candle downloader now retries failed pages and saves pages for resume.

Purpose:
- Keep ETHUSDC / USDC truth consistent and avoid losing partial downloads after timeout.

## 2026-06-13 - UI and smoke report display unified

Changed:
- UI loads active/last run from configs/runtime_state.json and reports/backtests/<run_id>/backtest_summary.json.
- Existing ETHUSDC 1m progress events now include data kind, status and age for UI display.
- Runtime-state tests preserve an existing runtime_state.json.

Tests:
- python -m compileall src tests
- python -m pytest -q

## 2026-06-13 - Handoff after Strategy V1 run analysis

Current project path:
- C:\TradingBot\ETHUSDC_BotV2_Cline

One start/report truth:
- UI and BAT/smoke both use src.ui.backtest_ui_controller.run_backtest_for_ui(...).
- Report paths are centralized in src/common/report_paths.py.
- UI loads active run from configs/runtime_state.json and reports/backtests/<run_id>/backtest_summary.json.

Last good run:
- run_20260613_082541, status completed.
- Strategy V1 result: about +2.30 USDC/year, 8 blindtest trades.
- Buy&Hold is separate and must not be confused with Strategy V1.

Data status:
- ETHUSDC 1m candles are current and used.
- exchange_info is loaded/checked but not yet used by strategy logic.
- BTCUSDC, ETHBTC, aggTrades and microstructure are currently not_wired.

Main bottleneck:
- Strategy V1 has only 24 fixed candidates: 4 families x 3 lookbacks x 2 parameter sets.
- Selected candidate was restrictive: range_breakout_lb360_th0.01_tp0.015.
- normal/conservative/aggressive profiles do not materially change candidate search yet.
- Reports store only the selected candidate, not all 24 training candidates.

Last patch:
- UI label corrected so Strategy V1 summary values are not shown as Buy&Hold.
- Tests passed: python -m compileall src tests; python -m pytest -q.

Next recommended start task:
- Do not start with BTCUSDC/ETHBTC wiring.
- First add Strategy V1 transparency: store all training candidates with params, train trade count, train PnL, train PnL/day, optional blind trade count, score and chosen/not-chosen reason.
- Then expand candidate space/profiles deliberately; plan BTCUSDC/ETHBTC context only after candidate evidence is visible.

Do not next:
- No second start logic, no BotV1Cline, no fake trades, no blindtest learning, no Live/Paper/Testtrade, no real orders.

## 2026-06-13 - Strategy V1 transparency/context wiring before next run

Changed:
- BTCUSDC and ETHBTC 1m context candle ensure/download paths wired through the existing UI/BAT `run_backtest_for_ui(...)` start path.
- Data catalog now supports ETHUSDC, BTCUSDC and ETHBTC 1m entries.
- Strategy V1 candidate space expanded by profile and can optionally require BTCUSDC + ETHBTC positive context alignment.
- `strategy_v1_report.json` now stores all training candidate evaluations for transparency.
- Tests remain isolated from real configs/data/reports.

Tests:
- `python -m compileall src tests`
- `python -m pytest -q`

Run started:
- Started real smoke/BAT workflow with `scripts\run_backtest_smoke.py`.
- PID: `1692`.
- At handoff no new run_id yet; runtime still `run_20260613_082541` completed.
- Do not patch while it runs; next check should inspect process, runtime and newest report folder.

## 2026-06-13 - Data overview and 7 day update rule added

Changed:
- ETHUSDC 1m data freshness now uses a 7 day threshold before incremental update.
- Added public ETHUSDC exchange_info cache/status.
- Added data_overview_report.json with used/not-used data areas.
- UI displays data-area status from saved reports.

Tests:
- python -m compileall src tests
- python -m pytest -q

## 2026-06-18 - Context data blocker fix started

Changed:
- Context ensure now validates required candle count, gaps and freshness.
- Incomplete BTCUSDC/ETHBTC CSVs now trigger backfill/resume instead of only normal incremental update.
- `run_backtest_for_ui(...)` now blocks if context data remains incomplete.
- Strategy V1 now minimally applies ETHUSDC exchange_info filters in simulation.

Tests:
- `python -m compileall src tests`
- `python -m pytest -q`

Current run/process:
- Last completed run remains `run_20260613_092650`.
- Context backfill PID `20976` was stopped on user request.
- Last observed before stop: BTCUSDC `550000` candles through `2024-06-28T07:47:00Z`, ETHBTC `250000` through `2023-12-02T23:59:00Z`.
- GPT handoff report created: `memory-bank/GPT_HANDOFF_CONTEXT_BLOCKER_2026_06_18.md`.

Next:
- Use only the open UI for data ensure/backtest so the user can observe and report visible errors.

## 2026-06-18 - Visible UI run with context completed

Checked:
- Runtime now points to `run_20260618_071808`, status `completed`.
- Reports checked: summary, data overview, Strategy V1, progress, run request.

Result:
- BTCUSDC `1586713` rows, last `2026-06-18T06:20:00Z`, usable/used true.
- ETHBTC `1586725` rows, last `2026-06-18T06:44:00Z`, usable/used true.
- exchange_info usable/used true.
- Strategy V1 context aligned and available, but selected candidate is non-context.
- Result `+2.2964 USDC`, `0.006291 USDC/day`, `8` trades; minimal better than `run_20260613_092650`.

Next:
- No more data/download work; minimally inspect Strategy V1 scoring/candidate behavior.

## 2026-06-18 - Strategy V1 candidate diagnostics added

Checked:
- `run_20260618_071808` Strategy V1 candidate audit and Strategy V1 code.

Result:
- 144 candidates: 72 context, 72 non-context.
- Context with trades: 68; context zero trades: 4.
- Best context: `range_breakout_lb120_th0.01_tp0.015_ctx`, score `+2.3067`, 17 trades.
- Best non-context/selected: `range_breakout_lb360_th0.01_tp0.015`, score `+3.5500`, 18 trades.
- No technical context bug found; issue is weak scoring/robustness against rare candidates.

Changed:
- `strategy_v1_report.py` now stores candidate counts, best context/non-context, top 10 and selection diagnosis.
- Added report diagnostic test.

Tests:
- `python -m compileall src tests`
- `python -m pytest -q`

Next:
- If approved, minimally adjust Strategy V1 scoring/validity for low-trade/low-robustness candidates; next backtest only via UI.

## 2026-06-18 - Strategy V1 low-activity scoring penalty

Changed:
- Implemented training-only adjusted score with low-activity penalty.
- Rule: target `24` training trades over 730 days, about 1 trade/month.
- Penalty: each missing trade below 24 costs `0.02 USDC` in adjusted score.
- Report now stores raw score, adjusted score, low-activity penalty, penalty flag and trades/month.

Reason:
- Old selected candidate had only 18 training trades (`0.75/month`) and only narrowly beat a 31-trade candidate.
- The rule improves robustness without forcing a bad/context candidate.

Expected old-run effect:
- Theoretical winner on `run_20260618_071808` candidate audit becomes `range_breakout_lb30_th0.01_tp0.015`, 31 trades, non-context.

Tests:
- `python -m compileall src tests`
- `python -m pytest -q`

Next:
- Start next real backtest visibly through UI only, then inspect new report fields.

## 2026-06-18 - Catalog regression fixed after invalid UI run

Checked:
- `run_20260618_153414` completed with `-5.96 USDC` and 20 trades.
- Run is not a valid context/scoring comparison: BTCUSDC and ETHBTC were `not_available` due to missing Catalog entries.

Cause:
- `candle_data_ensure._save_default_catalog` overwrote `configs/data_catalog.json` with ETHUSDC only.
- Existing valid context CSVs were not re-upserted by Context Ensure.

Changed:
- ETHUSDC ensure now upserts ETHUSDC and preserves BTCUSDC/ETHBTC.
- Context ensure now upserts existing valid BTCUSDC/ETHBTC CSVs.
- `configs/data_catalog.json` repaired to ETHUSDC, BTCUSDC, ETHBTC.

Files:
- BTCUSDC and ETHBTC CSVs are physically present.

Tests:
- `python -m compileall src tests`
- `python -m pytest -q`

Next:
- Start next UI backtest visibly; only evaluate if BTCUSDC/ETHBTC are usable/used.

## 2026-06-18 - Central data ensure inventory and clean button

Changed:
- Backtest UI start checks ETHUSDC 1m, BTCUSDC 1m, ETHBTC 1m and ETHUSDC exchange_info.
- 1m data policy remains 7-day freshness with append/resume/backfill, no unnecessary CSV deletion.
- Data Catalog writes are upsert-only for ensure paths.
- Data overview now classifies microstructure: aggTrades/trades not available for current historical blindtest; bookTicker/orderbook require live collection.
- Added UI button `Alle Daten löschen / Bot clean machen` with two confirmations.
- Clean action deletes downloaded candles/live data/backtest reports and resets Catalog/runtime state; keeps source, configs folder, memory, docs and tests.

Tests:
- `python -m compileall src tests`
- `python -m pytest -q`

Next:
- Start next real backtest visibly through UI and verify BTCUSDC/ETHBTC usable/used before judging result.

## 2026-06-18 - Valid context run after scoring fix analyzed

Checked:
- `run_20260618_160502` reports only.

Result:
- Valid context run: ETHUSDC, BTCUSDC, ETHBTC and exchange_info usable/used.
- Selected `range_breakout_lb30_th0.01_tp0.015`, non-context.
- raw/adjusted score `+3.5166`, low-activity penalty `0`, 31 training trades, 1.2926 trades/month.
- Blindtest result `-5.96 USDC`, 20 trades.

Diagnosis:
- Low-activity fix increased activity and selected the expected candidate.
- Result got worse, so trade count alone is too simple.
- Next needed metric is training-only stability: monthly PnL, positive/negative training months, training drawdown and profit concentration.
- Current report lacks training-trade distribution, so this cannot be reconstructed honestly from the completed run alone.

Next:
- If approved, add training-only stability diagnostics to candidate audit before changing score again.

## 2026-06-18 - Strategy V1 training stability scoring implemented

Changed:
- Candidate evaluation now computes training-positive/negative/active months, total months, trades/month, training max drawdown, best/worst trade, top-trade profit share and concentration warning.
- Final adjusted score now subtracts low-activity, stability, drawdown and concentration penalties.
- Strategy V1 report now stores selected raw/before-stability/final score, selected stability diagnosis, best before/after stability, top 10 by final score, training stability metrics and selection reason.

Reason:
- `run_20260618_160502` was valid context but selected a 31-trade candidate that lost `-5.96 USDC`; trade count alone was insufficient.

Tests:
- `python -m compileall src tests`
- `python -m pytest -q`

Next:
- Start UI backtest visibly; then inspect new stability fields. Existing old reports cannot honestly identify the new winner because they lack trade/month distribution.

## 2026-06-25 - Derived-Timeframes an Router-Diagnose angeschlossen

Changed:
- Bestaetigt: 5m/15m/30m/1h/4h/1d waren vorher nur im Datenreport sichtbar.
- Zeit-sichere HTF-Feature-Snapshots werden jetzt je Trainings-Kandidaten-Entry aus vollstaendig geschlossenen Kerzen gebaut.
- Router-Report zeigt Verfuegbarkeit, Nutzung, verwendete Timeframes, Missing-Grund und Kandidaten-Coverage.
- Keine Aenderung an Gates, Scores, Pool-Auswahl, Trades oder Smoke-/Full-Pfad.

Tests:
- `python -m compileall src tests`
- `python -m pytest -q`

Next:
- UI-nahen Smoke fuer Report-/Coverage-Pruefung; danach training-only Nutzen einzelner HTF-Metriken untersuchen.
