# GPT Handoff - Context Data Blocker 2026-06-18

## Was verstanden wurde
- Projekt ist ausschließlich `C:\TradingBot\ETHUSDC_BotV2_Cline`.
- Wahrheit: ETHUSDC Spot LONG-only, Quote USDC, keine Orders/Futures/Margin/Leverage.
- Letzter echter abgeschlossener Run bleibt `run_20260613_092650`, status `completed`.
- Ergebnis dort: ca. `+2.2953 USDC`, `0.00629 USDC/day`, `8` Trades.
- Der zentrale Blocker ist nicht Strategieverbesserung, sondern unvollständige Kontextdaten BTCUSDC/ETHBTC.
- Backtests sollen ab jetzt sichtbar über die UI laufen, damit der Nutzer Fehler direkt sehen und sich melden kann.

## Was extra gemacht werden musste
- Memory war teilweise veraltet und verwies noch auf `run_20260613_082541` / PID `1692`.
- `configs/runtime_state.json` und Reports von `run_20260613_092650` mussten als aktuelle Wahrheit priorisiert werden.
- Der Datenkatalog war zwischenzeitlich nur noch ETHUSDC; BTCUSDC/ETHBTC mussten wieder eingetragen werden.
- Der Kontext-Backfill musste gestartet werden, lief aber zu lange für Tool-Timeouts und wurde deshalb zunächst als Hintergrundprozess gestartet.
- Nach Nutzerwunsch wurde der Hintergrundprozess wieder gestoppt: ab jetzt keine versteckten CLI-/Background-Läufe.

## Was im letzten Patch gemacht wurde
- `src/data/binance_candle_downloader.py`: unvollständige vorhandene CSVs werden nicht mehr nur inkrementell ab letztem Timestamp aktualisiert; es gibt Backfill/Resume für fehlende Historie.
- `src/data/context_data_ensure.py`: Context Ensure prüft jetzt Required Count, Gaps und Aktualität/Freshness.
- `src/ui/backtest_ui_controller.py`: `ensure_all_context_data_ready(...)` wird jetzt hart ausgewertet; bei fehlendem Kontext startet der Backtest nicht still weiter.
- `src/backtest/strategy_v1.py`: Strategy V1 nutzt exchange_info minimal für MIN_NOTIONAL/NOTIONAL, LOT_SIZE und PRICE_FILTER in der Simulation.
- `src/data/exchange_info.py`: Filter-Loader und Rundungsfunktionen ergänzt; `used_in_backtest=True`, wenn nutzbar.
- `src/data/data_overview.py`: exchange_info wird als verwendet gemeldet; Kontextnutzung bleibt abhängig von echten nutzbaren Kontextdaten.
- Tests ergänzt/angepasst für Context-Block, Backfill-Verhalten und exchange_info-Verwendung.
- Memory-Dateien aktualisiert.

## Validierung
- `python -m compileall src tests` erfolgreich.
- `python -m pytest -q` erfolgreich.
- Kein neuer Backtest-Run wurde abgeschlossen.
- Letzter completed Run bleibt `run_20260613_092650`.

## Aktueller Datenstatus beim Stopp des Hintergrundprozesses
- BTCUSDC war zuletzt auf ca. `550000` Candles gewachsen, letzter Timestamp `2024-06-28T07:47:00Z`.
- ETHBTC war zuletzt noch bei `250000` Candles, letzter Timestamp `2023-12-02T23:59:00Z`.
- Hintergrundprozess PID `20976` wurde auf Nutzerwunsch gestoppt.

## Was in Zukunft Zeit und Tokens spart
- Direkt sagen: zuerst nur UI starten, keine CLI-/Background-Prozesse.
- Direkt erlauben, ob Daten-Backfill im Hintergrund laufen darf oder sichtbar in UI bleiben muss.
- Wenn Reports analysiert werden sollen: genaue Run-ID nennen und sagen, welche JSONs Wahrheit sind.
- Wenn Memory veraltet sein kann: explizit sagen, welche Runtime/Run-ID Vorrang hat.
- Bei großen Downloads: vorher entscheiden, ob nur PID/Status gemeldet werden soll oder ob gewartet werden darf.
- Keine alten Reports/Archive lesen lassen, außer sie sind ausdrücklich Wahrheit.

## Nächster empfohlener Ablauf
1. UI öffnen.
2. Backtest/Start über UI auslösen.
3. UI soll sichtbar Kontextdaten prüfen/nachladen.
4. Wenn Fehler oder Timeout sichtbar wird, Nutzer meldet sich mit Screenshot/Text.
5. Erst wenn BTCUSDC und ETHBTC vollständig nutzbar sind, darf Strategy V1 wirklich mit Kontext laufen.

## Update nach sichtbarem UI-Lauf
- Neuer UI-Lauf: `run_20260618_071808`, status `completed`.
- BTCUSDC vollständig: `1586713` Rows, letzter Timestamp `2026-06-18T06:20:00Z`, usable/used `true`.
- ETHBTC vollständig: `1586725` Rows, letzter Timestamp `2026-06-18T06:44:00Z`, usable/used `true`.
- exchange_info usable/used `true`.
- Strategy V1 Report: `context_symbols_used = [BTCUSDC, ETHBTC]`, Kontext aligned.
- Trotzdem gewählt: `range_breakout_lb360_th0.01_tp0.015`, `use_context_filter=false`.
- Kandidaten: `144` total, `72` Kontext, nur `4` Kontext mit 0 Trades.
- Bester Kontext-Kandidat: `range_breakout_lb120_th0.01_tp0.015_ctx`, Score/PnL `+2.3067`, 17 Training-Trades.
- Bester Nicht-Kontext-Kandidat: `range_breakout_lb360_th0.01_tp0.015`, Score/PnL `+3.5500`, 18 Training-Trades.
- Ergebnis: `+2.2964 USDC`, `0.006291 USDC/day`, `8` Trades; minimal besser als `run_20260613_092650`, aber weiter selected ohne Kontext.
- Nächster Schritt: Keine Daten-/Downloadarbeit mehr; klein prüfen, warum Scoring weiter seltenen Nicht-Kontext-Range-Breakout bevorzugt.

## Strategy V1 Diagnose-Update
- Technischer Bug nicht gefunden: Kontextdaten kommen bei Candidate Evaluation an; 68 von 72 Kontext-Kandidaten hatten Training-Trades.
- Kein pauschales `-1000000000` mehr für Kontext: nur 4 Kontext-Kandidaten hatten 0 Trades.
- Auswahlgrund: bester Nicht-Kontext-Kandidat hatte höheren Trainingsscore als bester Kontext-Kandidat.
- Ursache fachlich: aktueller Score ist im Kern `training_total_net_pnl` und bevorzugt seltene, profitable Range-Breakouts mit nur 18 Training-Trades.
- Report wurde minimal erweitert: Kandidaten-Zählung, beste Kontext-/Nicht-Kontext-Kandidaten, Top 10 und Selection-Diagnose.
- Tests: `python -m compileall src tests`; `python -m pytest -q`.

## Run 20260618_160502 Analysis
- Run `run_20260618_160502` is a valid context run: ETHUSDC, BTCUSDC, ETHBTC and exchange_info usable/used.
- Result: `-5.9599 USDC`, `-0.01633 USDC/day`, 20 blindtest trades.
- Selected candidate: `range_breakout_lb30_th0.01_tp0.015`, `use_context_filter=false`.
- Scores: raw/adjusted `+3.5166`, low activity penalty `0`, training trades `31`, trades/month `1.2926`, train winrate `0.4839`.
- Scoring fix worked mechanically: selected the expected 31-trade candidate instead of the 18-trade candidate.
- It did not improve blindtest; more trades generalized worse.
- Diagnosis: trade count alone is insufficient; need training-only stability diagnostics such as monthly PnL distribution, positive/negative training months and training drawdown.
- Current report does not store training trade/month distribution, so this cannot be honestly reconstructed from the completed report alone.
- Microstructure remains future data: bookTicker/orderbook require live collection and must not be fake-used in historical blindtests.

## Training Stability Scoring Update
- Blocker fixed: Strategy V1 selection now uses training-only stability metrics, not only PnL + trade count.
- Added per-candidate metrics: positive/negative/active training months, total months, trades/month, training max drawdown, best/worst training trade, top-trade profit share and concentration warning.
- Final score now subtracts low-activity, stability, drawdown and concentration penalties.
- Report fields added: selected raw/before-stability/final score, selected stability diagnosis, best candidate before/after stability, top 10 by final score, training stability metrics and selection reason.
- Existing `run_20260618_160502` cannot reveal the new expected winner honestly because its saved report lacks training trade distribution; next UI run is needed.
- Tests: `python -m compileall src tests`; `python -m pytest -q`.
- Nächster sinnvoller Schritt: Scoring/Validitätskriterium klein prüfen, z.B. Mindest-Tradezahl oder Robustheits-/Stabilitätskomponente, ohne Daten/Downloader zu ändern.

## Scoring-Fix Update
- Freigegebener kleiner Fix umgesetzt: Low-Activity-Penalty im training-only Score.
- Regel: robustes Ziel `24` Training-Trades über 730 Trainingstage, also ungefähr 1 Trade/Monat.
- Penalty: jeder fehlende Trade unter 24 zieht `0.02 USDC` vom adjusted Score ab.
- Begründung aus `run_20260618_071808`: alter Sieger hatte 18 Trades (`0.75/Monat`), während ein fast gleich guter Kandidat 31 Trades (`1.29/Monat`) hatte.
- Reportfelder erweitert: `raw_score`, `adjusted_score`, `low_activity_penalty`, `low_activity_penalty_applied`, `train_trades_per_month`.
- Theoretisch auf alter Analyse würde statt `range_breakout_lb360_th0.01_tp0.015` nun `range_breakout_lb30_th0.01_tp0.015` gewinnen; weiterhin Nicht-Kontext, aber robuster mit 31 Training-Trades.
- Kein neuer Backtest gestartet; nächster echter Lauf nur sichtbar über UI.
- Tests: `python -m compileall src tests`; `python -m pytest -q`.

## Catalog Regression Update
- Neuer UI-Lauf `run_20260618_153414` completed, Ergebnis `-5.96 USDC`, 20 Trades.
- Dieser Lauf ist für Kontext-/Scoring-Bewertung ungültig/nicht sauber vergleichbar, weil BTCUSDC/ETHBTC im Data Catalog fehlten und daher `not_available` waren.
- CSV-Dateien waren physisch vorhanden: `data/candles/BTCUSDC_1m.csv` und `data/candles/ETHBTC_1m.csv`.
- Ursache: ETHUSDC-Ensure schrieb den Catalog per Full-Overwrite nur mit ETHUSDC; Context-Ensure trug vorhandene valide Kontextdateien nicht wieder in den Catalog ein.
- Fix: ETHUSDC-Ensure nutzt jetzt Catalog-Upsert; Context-Ensure upsertet valide vorhandene Kontextdateien.
- `configs/data_catalog.json` wurde wieder auf ETHUSDC, BTCUSDC, ETHBTC repariert.
- Tests: `python -m compileall src tests`; `python -m pytest -q`.
- Nächster Schritt: UI-Backtest sichtbar neu starten und nur bewerten, wenn BTCUSDC/ETHBTC wieder usable/used sind.

## Data Ensure / Clean UI Update
- Central UI start now checks ETHUSDC 1m, BTCUSDC 1m, ETHBTC 1m and ETHUSDC exchange_info before pipeline.
- 1m datasets use 7-day freshness logic and append/resume/backfill behavior; Catalog writes are upsert-only.
- Data overview now reports microstructure inventory separately: aggTrades/trades as not available for current historical blindtest, bookTicker/orderbook as live_collection_required.
- Added UI button `Alle Daten löschen / Bot clean machen` with two confirmations.
- Clean action deletes downloaded candles/live-data folders/backtest reports and resets Catalog/runtime state, but keeps source/config folders/memory/docs/tests.
- Tests: `python -m compileall src tests`; `python -m pytest -q`.

## Clean-Restart / Stability Run Check
- Clean wurde neu gestartet; geprüft wurde `run_20260618_164530`, status completed, Daten gültig/used für ETHUSDC, exchange_info, BTCUSDC, ETHBTC.
- Ergebnis: `+2.30 USDC`, 8 Blindtest-Trades; gewählt `range_breakout_lb360_th0.01_tp0.015`, non-context.
- Stability-Regel war aktiv, Reportfelder vorhanden, Auswahl nutzt `adjusted_score_final`.
- Kein UI-Selection-Bug gefunden; finaler Score bevorzugte 18 Training-Trades, weil Stability/Drawdown-Penalty 0 war.
- Mini-Fix: Low-Activity-Penalty von `0.02` auf `0.08` je fehlendem Training-Trade unter 24 erhöht.
- Kein neuer Backtest gestartet; nach Tests UI-Backtest sichtbar erneut starten.

## Patch Recovery nach Ctrl+C
- Geprüft: `strategy_v1.py`, `strategy_v1_report.py`, Strategy-V1-Tests und Memory waren bereits geändert.
- Fertig vorhanden: minimale Candidate-Space-Erweiterung, Intrabar-Scoring, Stability-Score und Reportregel `no_robust_positive_candidate`.
- Blocker bleibt fachlich: `run_20260618_200150` hatte nach ehrlicher Intrabar-Simulation `-8.48 USDC` / 20 Trades und keinen robust positiven finalen Trainingsscore.
- Kein Backtest/Download/Background-Prozess gestartet; nur Tests ausführen und danach UI sichtbar prüfen.

## 2026-06-19 Candidate-Space Follow-up
- Baseline `run_20260619_053202`: completed, valid/used ETHUSDC/exchange_info/BTCUSDC/ETHBTC, 400 candidates, best final training score `-1.4644`, `no_robust_positive_candidate`, result `-9.68 USDC` / 21 trades.
- Fix: Strategy V1 normal candidate-space extended to 560 candidates with extra TP/SL/Hold and trailing-stop exits; report positive status string is now `robust_positive_candidate_found` when applicable.
- Tests: `python -m compileall src tests`; `python -m pytest -q` green.
- New central UI-controller run `run_20260619_062700`: completed, same selected candidate/result, still `no_robust_positive_candidate`.
- Next blocker: entry/setup families are too weak; added exit variants did not create a robust positive candidate.