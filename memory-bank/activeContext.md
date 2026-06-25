# Active Context

Project: `C:\TradingBot\ETHUSDC_BotV2_Cline`

Latest analyzed run:
- `run_20260623_061114`: `0.00 USDC`, 0 trades, `optimizer_failed_to_find_target_relevant_search_space`, no robust positive candidate.
- Cause: `target_activity` ran, but found no trade_allowed replacement: 4 target_activity cluster rows / 20 setup tests; 2 target-math rejects and 2 training-net rejects. Best activity had high activity (~6872 trades/year) but negative net edge after fees; best edge stayed far too inactive.
- `run_20260622_154319`: `0.00 USDC`, 0 trades, `router_too_inactive`, no robust positive candidate.
- Cause: old 12-trade/year setup was correctly blocked, but no replacement setup was found; 109/109 rows skipped in Full-Training precheck: 61 target-math, 48 activity.

Current patch:
- Derived-Timeframes waren bisher nur Datenstatus. `activity_first_router` und Kandidatensuche nutzten ausschließlich 1m-Candles.
- Neu: Kandidaten-Entry-Diagnosen erhalten lookahead-sichere 5m/15m/30m/1h/4h/1d-Snapshots aus der zuletzt vollständig geschlossenen HTF-Kerze.
- Router-Reports enthalten `derived_timeframes_available`, `derived_timeframes_used_by_router`, `used_timeframes`, `missing_timeframe_reason` und Coverage/Return-Diagnosen je Best-/Pool-Kandidat.
- HTF-Metriken ändern bewusst noch keine Gates, Scores, Kandidatenauswahl oder Trades. Smoke und Full bleiben derselbe Pipeline-/Router-Pfad.
- Daten-/Feature-Baustein ergänzt: lookahead-sichere abgeleitete ETHUSDC-Timeframes 5m/15m/30m/1h/4h/1d aus vorhandenen 1m-Candles; nur vollständig geschlossene Buckets werden als Feature-Kerzen gezählt.
- `data_preparation_report.json` zeigt jetzt ETHUSDC-1m vorhanden, `derived_timeframes_available`, Counts je abgeleitetem Timeframe sowie BTCUSDC/ETHBTC/trades/aggTrades/bookTicker/orderbook available/missing. BookTicker/Orderbook bleiben missing und ungenutzt.
- Keine Strategie-, Router-, Smoke-/Full-Engine- oder Live/Paper-Änderung.
- Finaler UI-naher Lauf `run_20260623_163853`: completed, 0 Trades, `optimizer_search_space_failed`, Best training 0.06237. Nach Patch werden positive/aktive Kandidaten vollständig bewertet statt alle per Precheck zu verstecken; Hauptblocker bleibt realer Suchraum: Aktivität/Target-Math/Training-Net.
- `run_20260623_155039` Ursache: 123/123 Kandidaten `skipped_after_training_precheck=True`; Best-Candidate mit 0.0624 USDC/Tag war nicht trade_allowed, weil nur 1 Trade/14d, target_math_not_reachable_current_activity.
- Gemeinsamer Summary-Fehler gepatcht: Bei 0 trade_allowed zeigte UI `Best training USDC/Tag=0.0000`, obwohl Router best_* Kandidaten hatte; Summary nutzt jetzt Best-Candidates aus `rejection_summary`.
- UI-naher Controller-Lauf `run_20260623_112707`: 0 Trades, `optimizer_search_space_failed`, Opportunity-Mining aktiv mit 4829 Fenstern/31 Clustern; neu berechnete Summary ergibt Best training USDC/Tag 0.06237 statt 0.0000.
- UI-Smoke `run_20260623_105958` geprüft: Smoke/Full nutzen denselben Codepfad; 0 Trades kam aus gemeinsamem Router. Neuer gemeinsamer Patch: `opportunity_mining` nutzt geminte MFE/MAE-Opportunity-Cluster jetzt als erlaubten Cluster-Suchraum im echten `_build_router_pass`.
- UI-Smoke `run_20260623_102333` geprüft: `opportunity_mining` lief wirklich (4829 Opportunity-Fenster; Pass-Kandidaten 70/18/4/33), best_activity/best_target/best_fee_survivor vorhanden; 0 Setups wegen Aktivität/Target-Math/negativer Net.
- Gepatcht: Router skaliert Mindest-Trade-/Zielaktivitätswerte auf Trainingsfenster; 14 Trainingstage: 3 Trades/Tag = 42 und 6 Trades/Tag = 84 erwartete Trades, keine Jahres-Absolute im Smoke.
- Smoke-Test-Modus eingebaut: UI-Button `Smoke-Test starten`, Dauer 1/7/14/30 Tage Blindtest, Pipeline-Settings `run_type`, 2:1 Split und Reports mit `run_type=smoke_test`.
- Smoke nutzt dieselbe Backtest-/Router-/Optimizer-Engine wie Full-Backtest; nur Zeitraum/Split ist kürzer. Kein Leistungsnachweis, keine Strategieübernahme, keine Live-Freigabe.
- Smoke abgesichert: UI-Backtest ruft `run_backtest_preparation_pipeline` -> aktuellen `build_cluster_router_report`; neuer Test beweist alle vier Suchpässe inkl. `opportunity_mining`, neue Best-Felder und frozen/no-learning Verhalten.
- Status-Brücke gepatcht: `optimizer_search_space_failed` wird in Diagnostics/Summary nicht mehr als `router_too_inactive` fehlklassifiziert.
- Router erweitert performance-relevant: Training-only Opportunity-Mining, Ziel-Aktivitätsklassen, Target-Relevanz aus Aktivität+Edge+Fees, vierter `opportunity_mining`-Suchpass und breitere aktive Kandidaten.
- `NEXT_WORK_STATE.md` ist tokenarmer Neustart-Anker; `.clinerules/07_COST_DISCIPLINE_AND_WORKFLOW.md` und `.clineignore` reduzieren automatische Kontextkosten.
- Rejection diagnostics now include `search_pass_summary` and `rejected_by_other` so 0-setup failures show pass-wise candidate/rejection counts immediately.
- 0 trade_allowed setups is treated as optimizer/search-space failure, not success.
- Search order: primary -> `activity_expansion` -> `target_activity` training-only pass if still 0 setups.
- Report/diagnostics include best_found_candidate, best_activity_candidate, best_edge_candidate, best_balanced_candidate and rejection summary.
- Old target-math-dead rare setups remain blocked; no V1 fallback, no blindtest learning, no fake trades.

Next action:
- UI-nahen Smoke nur zur Prüfung der neuen HTF-Reportfelder/Coverage starten. Danach training-only entscheiden, ob eine einzelne HTF-Metrik zunächst als Diagnosevergleich und erst nach Beleg als Score-/Gate-Feature dienen darf.

Tests latest:
- `python -m compileall src tests` green.
- `python -m pytest -q` green.
