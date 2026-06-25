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

1. docs/CURRENT_TRUTH_MAP.md
2. docs/FINAL_ONE_YEAR_BLINDTEST_TRUTH.md
3. specs/07_FINAL_ONE_YEAR_BLINDTEST_CONTRACT.md
4. README.md
5. AGENTS.md
6. docs/DATA_TRUTH.md
7. docs/BACKTEST_TRUTH.md
8. docs/ROUTER_TRUTH.md
9. specs/00_MASTER_GOAL.md
10. specs/01_BACKTEST_CONTRACT.md
11. specs/02_SMOKE_TEST_CONTRACT.md
12. specs/03_STRATEGY_ENGINE_CONTRACT.md
13. specs/04_UI_CONTRACT.md
14. specs/05_REPORTING_CONTRACT.md
15. specs/06_ACCEPTANCE_TESTS.md
16. memory-bank/activeContext.md
17. memory-bank/NEXT_WORK_STATE.md
18. memory-bank/progress.md

Old files are not truth. If documents conflict, `docs/CURRENT_TRUTH_MAP.md` decides the current priority and archive-risk status.

## UI starten

- Windows: Doppelklick auf `ETHUSDC_BotV2_UI_starten.bat`
- Alternative per PowerShell:
  `python -m src.ui.app`

## Automatische Datenbereitstellung beim Backtest

Der Button für Smoke- oder Full-Backtest startet immer zuerst denselben zentralen
Datencheck. Fehlende Daten werden geladen, unvollständige Downloads werden
fortgesetzt und veraltete Daten werden aktualisiert. Erst wenn alle aktuell
verpflichtenden Quellen brauchbar sind, startet die gemeinsame Backtest-Pipeline.

Automatisch geprüft werden:

- ETHUSDC 1m als Hauptmarkt
- BTCUSDC und ETHBTC als bereits verwendeter Markt-/Stärkekontext
- ETHUSDT als liquider ETH-Preisfindungskontext
- USDCUSDT als Stablecoin-/Quote-Kontext
- vollständige Binance-Kline-Felder: Quote-Volumen, Trade Count und Taker-Buy-Volumen
- ETHUSDC `exchangeInfo` mit Spot-Filtern
- historische ETHUSDC `aggTrades` aus offiziellen Binance-Archiven, verdichtet auf
  lookahead-sichere Minutenmerkmale
- öffentliche ETHUSDC Best-Bid/Ask- und Top-20-Depth-Snapshots als fortlaufende
  lokale Live-Datensammlung

Kline- und `exchangeInfo`-Daten gelten nach spätestens sieben Tagen als
aktualisierungsbedürftig. Bei `aggTrades` wird die offizielle
Archiv-Veröffentlichungsverzögerung berücksichtigt. Der erste Start kann wegen
des mehrjährigen Datenumfangs lange dauern und mehrere Gigabyte übertragen.
Spätere Starts laden nur fehlende oder neue Bereiche.

Historische Raw-Trades werden zunächst nicht zusätzlich gespeichert:
`aggTrades` plus der Kline-Trade-Count erhalten die benötigte
Orderflow-Information mit deutlich weniger Speicherbedarf. BookTicker und
Orderbuch werden nicht rückwirkend erfunden. Sie dürfen erst nach mindestens
30 Tagen echter, sauberer Sammlung als Backtestquelle bewertet werden.

Smoke 1/7/14/30 und Full verwenden für Datencheck, Features, Router und Simulation
denselben Codepfad. Alle Läufe bleiben reine Simulation; es werden keine API-Keys
benötigt und keine Orders ausgelöst.

Wichtig: Mehr Daten verbessern die Untersuchungsbasis, garantieren aber weder
Profit noch ein Ziel von 3 USDC pro Tag.
