# GPT Deep Continuation Plan - ETHUSDC Activity-First Bot

Stand: 2026-06-27.

Diese Datei ist fuer GPT/Codex als ausfuehrlicher Arbeitsplan gedacht. Die
verbindliche Wahrheit bleibt `README.md`. Wenn diese Datei und `README.md`
widersprechen, gilt `README.md`.

## 0. Wichtigster aktueller Hinweis

Der zuletzt vom Nutzer gepostete "neue" Backtest ist **kein neuer V13-Run**.

Gepostet wurde erneut:

- Run-ID: `run_20260627_082716`
- Report-Version: `activity_first_v12_validation_guard`
- Candidate-Space: `trade_allowed_blocked`
- Blindtest-Trades: 0

Lokal existiert aktuell kein neuerer Run-Ordner als `run_20260627_082716`.
Das bedeutet: Entweder wurde die UI nicht komplett neu gestartet, der neue Run
wurde nicht gestartet, oder die UI hat noch den alten aktiven/letzten Run
angezeigt.

Naechster Pflichtschritt vor jeder weiteren Performance-Aussage:

1. UI komplett schliessen.
2. Sicherstellen, dass keine alte Python-UI-Instanz mehr den alten Importstand
   haelt.
3. UI ueber `C:\TradingBot\ETHUSDC_BotV2_Cline\ETHUSDC_BotV2_UI_starten.bat`
   neu starten.
4. Full-Backtest starten.
5. Der neue Run muss eine neue Run-ID haben, spaeter als
   `run_20260627_082716`.
6. Im neuen Report muss stehen:
   `candidate_generation_version = activity_first_v13_validation_optimized_pool`.

Wenn wieder `run_20260627_082716` erscheint, ist kein neuer V13-Full-Run
gelaufen.

Nach einem weiteren UI-Startversuch wurde geprueft, warum kein neuer Run
angelegt wurde. Befund:

- Kein Python-Cache.
- UI-Prozess lief, aber kein neuer Run-Ordner entstand.
- Datenprüfung vor der Run-ID-Erstellung brach wegen korrupter
  `data/live_microstructure/ETHUSDC/status.json` ab.
- Die Datei enthielt NUL-Bytes statt JSON.
- Fix wurde lokal eingebaut:
  - `src/data/live_microstructure.py`: kaputte Statusdatei wird als fehlend
    behandelt.
  - Status wird atomar ueber Temp-Datei + Replace geschrieben.
  - `tests/test_live_microstructure.py`: Regressionstests fuer korrupte
    Statusdatei und atomaren Rewrite.
- Danach lief `ensure_all_backtest_market_data_ready()` erfolgreich durch.

Wichtig fuer GPT: Wenn kein neuer Run-Ordner entsteht, zuerst Daten-Ensure und
Runtime-State pruefen, nicht Strategie-/Router-Logik veraendern.

## 1. Zielbild des Bots

Der Bot ist ausschliesslich fuer ETHUSDC Binance Spot LONG-only gedacht. Er soll
nicht irgendeine Standardstrategie kopieren. Ziel ist eine ETH-spezifische
Situations-/Regime-Erkennung:

- Was ist die aktuelle ETH-Situation?
- Kam eine aehnliche Situation in den letzten ca. 3 Jahren mehrfach vor?
- Welche Regel war in diesen historischen Situationen nach Kosten sinnvoll?
- Bestaetigen Orderflow, aggTrades, HTF und Kontextmaerkte diese Situation?
- Wenn keine robuste Wiederholung erkennbar ist: No-Trade.

Das langfristige Ziel ist mindestens 3 USDC/Tag bei 100 USDC Einsatz im
365-Tage-Blindtest. Das ist ein Zielwert, aber kein Grund, Gates zu lockern,
Blindtest zu optimieren oder Fake-Trades zu erzeugen.

## 2. Harte Verbote

Diese Regeln duerfen nicht gebrochen werden:

- Kein Short, Margin, Futures, Leverage.
- Keine echten Orders.
- Kein Paper/Live ohne ausdrueckliche Nutzerfreigabe.
- Kein Blindtest-Lernen.
- Kein Lookahead.
- Kein Optimieren auf Smoke, 7/14/30 Tage oder den letzten Blindtest.
- Kein Hartcodieren des besten Blindtest-Einzelkandidaten.
- Keine separate Backtest-Engine.
- Keine alte V0/V1/Cluster-/Buy-Hold-Engine reaktivieren.
- Keine Datenquelle als Handelsfeature verwenden, nur weil sie vorhanden ist.
- BookTicker/Depth nicht historisch simulieren; erst nach mindestens 30 echten
  sauberen Tagen Sammlung pruefen.

## 3. Aktueller technischer Stand

Eine Engine:

```text
ETHUSDC_BotV2_UI_starten.bat
  -> src.ui.app
  -> run_backtest_for_ui
  -> zentraler Daten-Ensure
  -> run_backtest_preparation_pipeline
  -> activity_first_router
  -> backtest_summary.json
```

Full und Smoke muessen derselbe Pfad bleiben. Smoke ist nur ein kuerzerer
Techniktest, keine Performance-Wahrheit.

Aktueller lokaler Patch:

- `candidate_generation_version = activity_first_v13_validation_optimized_pool`
- `base_candidate_generation_version = activity_first_v11_eth_regime_expanded`
- V13 ist technisch eingebaut, aber noch nicht durch einen Full-Backtest
  bestaetigt.

V13 tut:

- lernt Basiskandidaten und Filter auf `selection_train`
- prueft Kandidaten einzeln auf `selection_validation`
- behaelt die validation-erlaubten Kandidaten als Potenzial-Bibliothek
- baut den Handels-Pool nicht mehr starr per Top-N
- fuegt Kandidaten nur hinzu, wenn der gemeinsame Validation-Pool besser wird
  und weiterhin Aktivitaet, Fees, Profit Factor und Drawdown besteht
- benutzt keine Blindtestdaten zur Auswahl

## 4. Wichtige Runs und was sie bedeuten

### `run_20260626_210349`

- Version: `activity_first_v10_context_market_filter`
- Ergebnis: +7.66 USDC, +0.02097 USDC/Tag
- Trades: 98
- Bedeutung: 0-Trade-Blocker war gebrochen, Daten konnten Entscheidungen
  beeinflussen.
- Nicht uebernehmen: viel zu weit unter 3 USDC/Tag.

### `run_20260627_063203`

- Fee-Rescue aktiv, aber ohne Effekt.
- Ergebnis gleich wie `run_20260626_210349`.
- Bedeutung: Fee-Rescue war nicht der Engpass.

### `run_20260627_071724`

- Version: `activity_first_v11_eth_regime_expanded`
- Training: bester Kandidat ca. +0.15 USDC/Tag
- Blindtest: -99.76 USDC, Konto fast zerstoert
- Trades: 349
- Bedeutung: Mehr Suchraum fand Training-Potenzial, aber Pool-Auswahl war
  overfittet und zu breit.
- Nicht uebernehmen.

### `run_20260627_082716`

- Version: `activity_first_v12_validation_guard`
- Training: bester Kandidat ca. +0.1377 USDC/Tag
- Vor Validation: 226 trade_allowed Kandidaten
- Nach Validation: 53 trade_allowed Kandidaten
- V12-Top-Pool auf Validation:
  - +7.83 USDC
  - +0.0435 USDC/Tag
  - 187 Trades
  - Fee/Gross ca. 0.827
  - Max DD ca. 29.56%
- Blockiert wegen `rejected_by_fees`.
- Blindtest: 0 Trades.
- Bedeutung: V12 hat den V11-Crash verhindert. Es ist kein alter 0-Trade-Bug.
  Die starre Top-N-Poolbildung war noch zu grob.

### `run_20260627_114634`

- Version: `activity_first_v13_validation_optimized_pool`
- V13-Validation-Pool: 3 Kandidaten
- Validation-Pool: ca. +0.3127 USDC/Tag
- Blindtest: -10.23 USDC, -0.0280 USDC/Tag
- Trades: 189
- Blindtest-Max-DD: ca. 41.29%
- Bedeutung: V13 war besser als V11, weil kein Konto-Crash entstand, aber noch
  nicht robust genug.
- Diagnostisch im Blindtest:
  - `eth_us_impulse_entry...orderflow_taker_buy_quote_imbalance_filter`:
    ca. +7.13 USDC
  - `eth_continuation_after_impulse_lb30...`: ca. +4.25 USDC
  - `eth_continuation_after_impulse_lb15...`: ca. -21.60 USDC
- Schluss: Fast gleiche Continuation-Regime-Varianten duerfen nicht parallel in
  den Pool, wenn ihr inkrementeller Validation-Nutzen klein ist.

## Aktueller lokaler Patch nach `run_20260627_114634`

V14 wurde lokal eingebaut, aber noch nicht full-run-bestaetigt.

- Neuer Report-String:
  `activity_first_v14_conservative_regime_pool`
- Der V13-Optimizer bleibt, ist aber konservativer:
  - maximal 1 Kandidat pro Strategie-Familie/Regime
  - neuer Kandidat nur, wenn er den gemeinsamen Validation-Pool um mindestens
    ca. +0.03 USDC/Tag verbessert
  - `incremental_validation_quote_per_day` wird pro akzeptiertem Schritt
    dokumentiert
- Kein Blindtest-Lernen.
- Kein Gate-Lockern.

Vor dem naechsten Full-Run:

```bat
python -m compileall src tests
python -m pytest -q
git diff --check
```

## 5. Datenstand und Verwendung

Der Bot hat derzeit 8 usable/verwendete Datenbereiche:

- ETHUSDC 1m OHLCV
- vollstaendige ETHUSDC Kline-Felder:
  - quote volume
  - trade count
  - taker-buy base/quote
- abgeleitete ETHUSDC HTF 5m/15m/30m/1h/4h/1d
- Binance exchange_info / Spot-Filter
- ETHUSDC aggTrade-Minutenfeatures
- BTCUSDC
- ETHBTC
- ETHUSDT
- USDCUSDT

Nicht als Backtestfeature verwenden:

- Spread / BookTicker / Depth, solange keine 30 echten sauberen Tage vorliegen
- On-chain/Futures/Options/Makro, solange keine timestamp-sichere, lokale,
  lookahead-freie Integration existiert

## 6. Warum nicht alle 139 oder 226 Kandidaten handeln?

Viele Kandidaten sind keine verschiedenen echten Marktchancen, sondern sehr
aehnliche Varianten derselben Situation:

- anderer Lookback
- anderer TP/SL/Hold
- anderer Filter
- gleicher ETH-Impuls
- gleicher Entry-Zeitpunkt oder stark ueberlappende Trades

Mit 100 USDC gemeinsamem Kapital darf der Bot nicht so tun, als haette jede
Variante ein eigenes Konto. Wenn 20 Varianten beim gleichen ETH-Impuls feuern,
ist das nicht 20-mal echtes Alpha. Es ist oft dieselbe Wette mehrfach.

Deshalb braucht der Bot:

- Kandidaten-Bibliothek: moegliche Situationen behalten
- Handels-Pool: nur robuste, nicht zu stark ueberlappende Kandidaten aktivieren
- Router: bei aktueller Situation passende Regel waehlen oder No-Trade

## 7. Naechster Pflichtschritt

Nicht weiter umbauen, bevor V13 einmal wirklich full gelaufen ist.

Ausfuehren:

```bat
python -m compileall src tests
python -m pytest -q
git diff --check
```

Dann:

1. UI komplett schliessen.
2. UI neu starten.
3. Full-Backtest starten.
4. Danach Report lesen.

Pflichtfelder im neuen V13-Report:

- `candidate_generation_version`
- `base_candidate_generation_version`
- `selection_validation_guard_used`
- `validation_optimized_pool_used`
- `selection_validation.pre_validation_trade_allowed_count`
- `selection_validation.post_validation_trade_allowed_count`
- `selection_validation.pool_selection.pool_selection_version`
- `selection_validation.pool_selection.candidate_library_count`
- `selection_validation.pool_selection.selected_count`
- `selection_validation.pool_selection.accepted_steps`
- `selection_validation.validation_pool_passed`
- `selection_validation.validation_pool_rejection_reason`
- `blindtest_trade_count`
- `blindtest_quote_per_day`
- `blindtest_max_drawdown`

## 8. Wenn V13 blockiert

Nicht Gates lockern.

Dann V14 bauen: ETH-Regime-Bibliothek und Situations-Router.

V14-Ziel:

- Nicht einfach Top-N-Kandidaten handeln.
- Stattdessen pro ETH-Situation entscheiden:
  - Trend/Impuls
  - Fortsetzung nach Impuls
  - Flush/Reclaim
  - Range Compression / Breakout
  - US-Session-Impuls
  - Quote-/USDC-Stoerung
  - BTC/ETH-Kontext zieht mit oder widerspricht
  - No-Trade

V14 Report muss zeigen:

- Kandidatenbibliothek nach Familie
- Kandidatenbibliothek nach Regime
- Train/Validation Treffer pro Regime
- Fee/Gross pro Regime
- Drawdown pro Regime
- Ueberlappung/Korrelation der Kandidaten
- Welche Regimes blockiert wurden
- Welche Regimes handelbar blieben
- Warum ein Signal gehandelt oder nicht gehandelt wurde

Technische V14-Idee:

1. Baue eine Kandidatenbibliothek aus allen validation-geprueften Kandidaten.
2. Gruppiere Kandidaten nach:
   - Familie
   - Lookback-Bereich
   - TP/SL/Hold-Klasse
   - Filterquelle
   - Entry-Regime
3. Berechne je Gruppe:
   - Selection-Train PnL/Tag
   - Selection-Validation PnL/Tag
   - PF
   - Fee/Gross
   - Max DD
   - Trade-Anzahl
   - aktive Tage
   - Signal-Ueberlappung
4. Erlaube nur Gruppen, die in Train und Validation positiv und kostenrobust
   sind.
5. Zur Laufzeit/Blindtest pro Signalzeitpunkt:
   - aktive Regime bestimmen
   - alle passenden Kandidatenvorschlaege sammeln
   - nur einen Kandidaten waehlen
   - bei Konflikt No-Trade oder Kandidat mit bester validation-stabiler
     Regime-Score
6. Pool bleibt ein gemeinsames Konto.

## 9. Wenn V13 positiv, aber weit unter 3 USDC/Tag bleibt

Dann nicht sofort uebernehmen.

Naechste sinnvolle Schritte:

1. Report dokumentieren.
2. Positive Blindtest-Trades nach Regime/Familie analysieren.
3. Negative Blindtest-Trades nur diagnostisch betrachten, nicht zum Lernen
   verwenden.
4. V14-Regime-Bibliothek trotzdem bauen, aber selection/validation basiert
   weiter nur auf Training.
5. Danach neuer Full-Run.

## 10. Wenn V13 deutlich positiv wird

Auch dann nicht sofort live.

Erst bauen:

- Monatskonfigurations-Export
- Regel-Hash
- Datenstichtag
- Featureliste
- erlaubte Regime
- No-Trade-Regeln
- UI-Button "Uebernehmen" erst nach bestaetigtem Full-Run
- klare Warnung: Live/Paper nur nach Nutzerfreigabe

## 11. Ziel 3 USDC/Tag

3 USDC/Tag bei 100 USDC Einsatz ist extrem ambitioniert. Der Bot darf dieses
Ziel nicht durch Ueberoptimierung vortaeuschen. GPT soll aggressiv in der
Analyse sein, aber konservativ in der Freigabe:

- viele Kandidaten pruefen: ja
- viele Daten nutzen: ja
- ETH-spezifische Situationen modellieren: ja
- Blindtest schoenrechnen: nein
- Gates lockern, damit 3 USDC erscheint: nein
- Kapital mehrfach verwenden: nein
- Live/Paper ohne klare Bestaetigung: nein

Der richtige Weg ist:

1. Daten vollstaendig und frisch halten.
2. ETH-Situationen breit erkennen.
3. Kandidatenbibliothek gross halten.
4. Handelsentscheidung eng und robust machen.
5. Blindtest als echte Wahrheit behandeln.
6. Erst bei stabiler, wiederholbarer Out-of-Sample-Leistung uebernehmen.
