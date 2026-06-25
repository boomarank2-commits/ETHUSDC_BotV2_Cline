# Current Truth Map - ETHUSDC_BotV2_Cline

Stand: 2026-06-25

Diese Datei ist der Navigationsanker fuer neue GPT-/Codex-Agenten. Sie ersetzt keine Fach-Contracts, sondern legt fest, welche Dateien aktuell fuehrend sind und welche Dateien nur Kontext oder Archiv sind.

## 1. Fuehrende Wahrheit

Neue Agenten lesen zuerst diese Reihenfolge:

1. `docs/CURRENT_TRUTH_MAP.md`
2. `docs/FINAL_ONE_YEAR_BLINDTEST_TRUTH.md`
3. `specs/07_FINAL_ONE_YEAR_BLINDTEST_CONTRACT.md`
4. `README.md`
5. `AGENTS.md`
6. `docs/DATA_TRUTH.md`
7. `docs/BACKTEST_TRUTH.md`
8. `docs/ROUTER_TRUTH.md`
9. `specs/00_MASTER_GOAL.md`
10. `specs/01_BACKTEST_CONTRACT.md`
11. `specs/02_SMOKE_TEST_CONTRACT.md`
12. `specs/03_STRATEGY_ENGINE_CONTRACT.md`
13. `specs/04_UI_CONTRACT.md`
14. `specs/05_REPORTING_CONTRACT.md`
15. `specs/06_ACCEPTANCE_TESTS.md`
16. `memory-bank/activeContext.md`
17. `memory-bank/NEXT_WORK_STATE.md`
18. `memory-bank/progress.md`

Wenn sich Dateien widersprechen, gilt diese Prioritaet:

`CURRENT_TRUTH_MAP` > `FINAL_ONE_YEAR_BLINDTEST_TRUTH` > `specs/07` > aktuelle Memory-Dateien > aeltere Docs.

## 2. Harte Projektregeln

Der Bot ist:

- ETHUSDC
- USDC als Quote-/Kapitalbasis
- Binance Spot
- LONG-only
- ein gemeinsamer Kapital-/Zeitkontext
- ein gemeinsamer Router-/Backtestpfad

Verboten:

- Short
- Margin
- Futures
- Leverage
- echte Orders ohne ausdrueckliche Freigabe
- Blindtest-Lernen
- Lookahead
- Fake-Trades
- paralleles Addieren mehrerer Kandidaten als separate Konten
- neue Schutz-/Strategielogik ohne Nachweis und bewusste Uebernahme

## 3. Finales Ziel

Das finale Ziel ist ein 365-Tage-Blindtest nach 730 Tagen Training/Optimierung.

Zielrichtung:

- 100 USDC Einsatz pro Trade
- langfristig Richtung 3 USDC/Tag im 365-Tage-Blindtest
- nur realistisch nach Gebuehren, Slippage, Binance-Regeln und Kapital-/Zeitkontext

Smoke 1/7/14/30 ist nur technische Kurzpruefung desselben Backtestpfads. Smoke ist keine finale Performance-Wahrheit.

## 4. Lokale Daten und GitHub-Regel

Heruntergeladene Marktdaten sind keine GitHub-Code-Artefakte.

Nicht zu GitHub pushen:

- `data/`
- grosse CSV-/ZIP-/DB-/Parquet-Dateien
- lokale aggTrade-Partitionen
- lokale Live-Microstructure-Snapshots
- lokale Download-Zwischenstaende

Nach GitHub gehoeren:

- Code
- Tests
- Docs/Specs/Truth-Dateien
- kleine Status-/Reportdateien nur dann, wenn sie bewusst zur Analyse gebraucht werden

Grund: Die Daten koennen mehrere Gigabyte gross werden, sind reproduzierbar aus Binance/Live-Sammlung und wuerden das Repo unnoetig schwer machen. Die Wahrheit liegt im Code, in den Contracts und in den Ergebnisreports, nicht in rohen Marktdaten im Git.

## 5. Daten-Nutzung im Backtest

Download bedeutet nicht automatisch Handelsentscheidung.

Aktueller Status:

- ETHUSDC 1m OHLCV: verwendet.
- Binance exchange_info/Filter: verwendet.
- ETHUSDC derived 5m/15m/30m/1h/4h/1d: diagnostisch verwendet, noch nicht als Gate/Score.
- BTCUSDC/ETHBTC/ETHUSDT/USDCUSDT: Datenbereitstellung vorbereitet; harte Router-Nutzung muss separat belegt werden.
- Vollstaendige Kline-Felder wie Quote-Volumen, Trade Count, Taker-Buy: Datenbasis vorbereitet; harte Router-Nutzung muss separat belegt werden.
- ETHUSDC aggTrade-Minutenfeatures: Datenbasis vorbereitet; harte Router-Nutzung muss separat belegt werden.
- Spread/BookTicker/Top-20-Depth: wird live gesammelt; vor mindestens 30 echten Tagen validierter Abdeckung nicht als Backtestquelle verwenden.

Ziel ist, heruntergeladene Daten schrittweise nutzbar zu machen. Jede Datenquelle muss diesen Weg gehen:

1. lokal vorhanden
2. freshness/Qualitaet geprueft
3. im Data Overview als verfuegbar gemeldet
4. lookahead-sicher als Feature ableitbar
5. training-only Gewinner/Verlierer-Trennung zeigen
6. erst danach als Score-/Gate-Kandidat erlaubt
7. erst nach Blindtest-Bestaetigung als uebernehmbarer Strategiebaustein erlaubt

Keine Datenquelle darf nur deshalb in den Handel eingreifen, weil sie heruntergeladen wurde.

## 6. Aktueller technischer Stand

Erledigt:

- Pool-Overlap-Guard aktiv: Kandidaten werden nicht mehr als parallele getrennte Konten addiert.
- Derived Timeframes 5m/15m/30m/1h/4h/1d werden aus 1m-Candles lookahead-sicher erzeugt.
- Derived Timeframes sind diagnostisch am Router angebunden.
- HTF Training Edge Diagnostics sind im Router-Report vorbereitet: Gewinner/Verlierer im Training werden je Timeframe/Metrik verglichen.
- Zentraler UI-Daten-Ensure ist eingebaut: Smoke und Full rufen denselben Datencheck vor der Pipeline auf.
- ETHUSDC, BTCUSDC, ETHBTC, ETHUSDT, USDCUSDT, vollstaendige Kline-Felder, exchange_info und ETHUSDC aggTrade-Minutenfeatures werden als Datenbasis vorbereitet.
- Live Spread/Depth Sammlung wird gestartet/geprueft, ist aber erst nach mindestens 30 echten Tagen validierter Abdeckung als Backtestquelle bewertbar.

Nicht erledigt:

- Neue Daten sind noch nicht aggressiv in Gates/Scores/Kandidatenauswahl eingebaut.
- ETHUSDT, USDCUSDT, aggTrades, Orderflow, Spread/Depth sind noch nicht als harte Handelsentscheidung validiert.
- 365-Tage-Full-Blindtest ist noch nicht als Zielerreichung bestaetigt.
- Kein Paper/Live/Testtrade als Trading-Freigabe.

## 7. Dateien mit Archiv-/Altlast-Risiko

Diese Dateien duerfen gelesen werden, aber nicht als alleinige operative Wahrheit gelten:

- `.clinerules/*`: historischer Arbeitsrahmen; bei Widerspruch gilt diese Truth Map.
- `memory-bank/activeContext.md`: enthaelt viel Verlauf und alte Runs; fuer aktuelle Kurzfassung gilt diese Truth Map.
- `memory-bank/progress.md`: append-only Verlauf; fuer aktuelle Prioritaet gilt diese Truth Map.

Bereinigt oder reduziert:

- `AGENTS.md` wurde auf die aktuelle Read-Order und Zielwahrheit aktualisiert.
- `docs/UI_TRUTH.md` wurde auf die aktuelle Backtest-UI-Phase aktualisiert.
- `docs/IMPLEMENTATION_PLAN.md` wurde auf den aktuellen Daten-/Feature-/Router-Plan aktualisiert.
- `memory-bank/techContext.md` wurde auf den aktuellen technischen Stand aktualisiert.
- `memory-bank/openQuestions.md` wurde auf nicht-blockierende Reportfragen reduziert.
- `.clinerules/02-no-assumptions.md` wurde auf diese Truth Map als erste Wahrheit reduziert.
- `.clinerules/03-bot-truth.md` wurde auf diese Truth Map als erste Wahrheit reduziert.
- `docs/BACKTEST_ROUTER_CONTRACT.md` wurde entfernt, weil es als alte doppelte Router-Wahrheit missverstaendlich war.

## 8. Aktueller naechster sinnvoller Schritt

Nach dem letzten Patch soll ein sichtbarer UI-/Controller-naher Lauf gestartet werden.

Zweck des naechsten Laufs:

- Daten-Ensure wirklich ausfuehren
- fehlende/alte Daten laden oder aktualisieren
- neuen Report erzeugen
- pruefen, ob `derived_timeframe_training_edge_analysis` im Router-Report erscheint
- pruefen, ob neue Datenquellen im Data Overview korrekt als available/used/not_ready/missing markiert werden

Wichtig: Der naechste Lauf ist noch kein Live-Faehigkeitsbeweis. Er kann lange dauern und mehrere Gigabyte herunterladen.

## 9. Was danach zu analysieren ist

Nach einem neuen Report muss geprueft werden:

1. Wurden alle Pflichtdaten erfolgreich vorbereitet?
2. Sind Smoke und Full weiterhin derselbe Pipeline-/Router-Pfad?
3. Sind HTF Training Edge Diagnostics vorhanden?
4. Trennen HTF-Metriken Gewinner und Verlierer im Training sichtbar?
5. Sind aggTrades/Orderflow nur vorbereitet oder schon genutzt?
6. Bleiben BookTicker/Orderbuch vor 30 echten Tagen `not_ready` / nicht routerwirksam?
7. Gibt es irgendeinen Hinweis, dass ein neues Feature ohne Training-only Beleg in Gates/Scores gelangt ist?

Erst wenn eine Metrik im Training sauber trennt, darf ein kleiner, expliziter Score-/Gate-Kandidat gebaut werden.

## 10. Monatlicher Ziel-Workflow

Wenn ein 365-Tage-Blindtest nach 730 Tagen Training einen uebernehmbaren Kandidaten zeigt:

1. Nutzer prueft Kennzahlen: USDC/Tag, bester/schlechtester Tag, bester/schlechtester Monat, Drawdown, Tradezahl, positive/negative Tage.
2. Nutzer uebernimmt die Strategie bewusst in der UI.
3. Bot laeuft fuer den kommenden Monat mit dieser uebernommenen Konfiguration.
4. Beim naechsten Monatslauf werden Daten aktualisiert und erneut die letzten 3 Jahre betrachtet.
5. Wieder 2 Jahre Training/Optimierung und 1 Jahr Blindtest.
6. Nur bei erneut ueberzeugendem Ergebnis wird der neue Kandidat uebernommen.

Keine automatische Live-Uebernahme ohne Nutzerentscheidung.

## 11. Keine falschen naechsten Schritte

Nicht tun:

- nicht den alten Cluster-Router flicken
- nicht Gates lockern, nur um Trades zu erzwingen
- nicht direkt auf 7/14/30 optimieren
- nicht Orderbook/BookTicker ohne 30-Tage-Abdeckung verwenden
- nicht Blindtest-Ergebnisse zum Lernen verwenden
- nicht Paper/Live/Echtorder-Logik bauen
- nicht Rohdaten oder Reports als Code-Truth behandeln
