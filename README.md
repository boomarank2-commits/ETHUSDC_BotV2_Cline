# ETHUSDC Bot V2 - VERBINDLICHE EINZIGE ARBEITSWAHRHEIT

Stand: 2026-06-27 nach `run_20260627_114634` und lokalem V14-Conservative-Regime-Pool-Patch.

Diese Datei ist fuer Menschen, GPT, Codex und jeden kuenftigen Agenten
verpflichtend. Sie ist die einzige normative Arbeitswahrheit des Projekts.
Andere Docs, Specs, Memory-Dateien und alte Reports sind nur Hintergrund oder
Archiv. Bei Widerspruch gilt immer diese README.

Ausfuehrlicher GPT-Fortsetzungsplan:
`docs/GPT_DEEP_CONTINUATION_PLAN_20260627.md`.

## 1. Auftrag

Der Bot untersucht ausschliesslich ETHUSDC auf Binance Spot und sucht eine
ETH-spezifische, kostenrealistische LONG-only Konfiguration.

Das Ziel ist langfristig eine robuste Richtung von 3 USDC pro Tag bei 100 USDC
Einsatz im 365-Tage-Blindtest. Das ist ein Zielwert, keine Garantie und niemals
ein Grund, Gates zu lockern oder Trades zu erzwingen.

Verboten sind:

- Short, Margin, Futures, Leverage und echte Orders
- Paper-/Live-Freigabe ohne ausdrueckliche Nutzerentscheidung
- Lookahead, Blindtest-Lernen und Fake-Trades
- parallele Kandidaten als getrennte Konten
- Optimierung auf Smoke-Ergebnisse oder den letzten 7/14/30 Tagen
- eine zweite Backtest-Engine, Summary-Fallbacks oder versteckte Vergleichsstrategie

## 2. Genau ein Backtestpfad

Es gibt exakt eine Entscheidungsengine: `activity_first_router`.

```text
ETHUSDC_BotV2_UI_starten.bat
  -> src.ui.app
  -> run_backtest_for_ui
  -> zentraler Daten-Ensure
  -> run_backtest_preparation_pipeline
  -> activity_first_router
  -> backtest_summary.json
```

Full und Smoke nutzen diesen identischen Pfad, dieselbe Simulation, denselben
Router und denselben gemeinsamen Kapital-/Zeitkontext.

- Full: 730 Tage Training + 365 Tage Blindtest.
- Smoke: identischer Code mit kuerzerem 2:1 Trainings-/Blindtestfenster.
- Smoke ist nur ein Techniktest, niemals Performance-Wahrheit.

V0, V1, Cluster-Router und Buy-and-Hold sind keine erlaubten Engines,
Vergleiche oder Summary-Fallbacks.

## 3. UI starten

Zum UI-Start immer `ETHUSDC_BotV2_UI_starten.bat` im Projektordner verwenden.
Der Button "Backtest starten" ist der einzige Full-Backtest. Die daneben
liegenden Smoke-Buttons nutzen denselben Pfad mit einem kuerzeren Zeitraum.
Alternativ startet `python -m src.ui.app` dieselbe UI.

Wichtig: Nach Codeaenderungen die UI komplett schliessen und neu starten.
Python haelt importierte Module im laufenden Prozess. Ein noch offenes UI-Fenster
kann sonst alten Router-Code ausfuehren.

## 4. Monatsmodell: Konfiguration, nicht Dauerlernen

Der Bot darf nicht alle zehn Minuten neu lernen. Er darf alle zehn Minuten nur
eine ETH-Phase mit bereits geschlossenen Daten erkennen und eine vor dem Monat
eingefrorene Regel waehlen.

Der spaetere Monatsablauf lautet:

1. Daten bis zu einem klaren Stichtag aktualisieren und abschliessen.
2. In 730 Trainingstagen Kandidaten und ETH-Regime ausschliesslich mit
   historischen, zu diesem Zeitpunkt verfuegbaren Daten untersuchen.
3. Gewinner-/Verlierer-Trennung, Kosten, Profit Factor, Drawdown, Aktivitaet und
   Stabilitaet im Training pruefen.
4. Eine Konfiguration mit Regel-Hash, Datenstichtag, Features und Schwellenwerten
   einfrieren.
5. Diese Konfiguration auf 365 historischen Blindtesttagen pruefen, ohne
   Nachlernen oder erneute Auswahl.
6. Nur nach ueberzeugendem Blindtest darf der Nutzer sie bewusst fuer den
   naechsten Monat uebernehmen.
7. Waehrend des Monats darf die eingefrorene Konfiguration nur zwischen
   `Trend/Impuls`, `Ruecklauf/Reclaim`, `Range/unklar` und `No-Trade` wechseln.
   Sie darf keine neuen Parameter lernen.
8. Zum naechsten Monatsstichtag beginnt ein neuer, zeitlich sauberer Lauf.

Aktuell existiert keine uebernehmbare Monatskonfiguration. Der beste positive
Full-Run ist weit unter dem Ziel; der aggressive V11-Run war im Blindtest klar
negativ. Eine Uebernahme ist verboten, bis ein neuer Full-Run den 365-Tage-
Blindtest stabil und deutlich positiv besteht.

## 5. Datenwahrheit und verpflichtende Reihenfolge

| Quelle | Lokal | Router-Status nach `run_20260627_114634` / lokalem V14-Patch | Naechster erlaubter Schritt |
|---|---:|---|---|
| ETHUSDC 1m OHLCV | Ja | verwendet | Basis beibehalten |
| ETHUSDC Kline Quote/Trades/Taker-Buy | Ja | handelsentscheidend im V11-Run, aber overfittet moeglich | nur mit Validation-Optimized-Pool erlauben |
| ETHUSDC 5m-1d | abgeleitet | Diagnose/Filterkandidaten und potenziell handelsentscheidend | nur geschlossene HTF-Kerzen, nur mit Validation-Optimized-Pool |
| Binance exchange_info | Ja | verwendet | Fees, LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL beibehalten |
| ETHUSDC aggTrade-Minutenfeatures | Ja | handelsentscheidend verwendet, V11-Pool overfittete | nur mit Validation-Optimized-Pool erlauben |
| ETHUSDT | Ja | handelsentscheidend als Kontextfilter verwendet | nur mit Validation-Optimized-Pool erlauben |
| ETHBTC / BTCUSDC | Ja | Kontextmarkt-Feature-Store 100% ausrichtbar | nur Training-only Filter/Score plus Validation-Optimized-Pool |
| USDCUSDT | Ja | Kontextmarkt-Feature-Store 100% ausrichtbar | Quote-Stabilitaet nur mit Validation-Optimized-Pool |
| BookTicker / Depth | live gesammelt | gesperrt | fruehestens nach 30 sauberen echten Tagen |
| Raw Trades | absichtlich nein | gesperrt | aggTrades reichen zunaechst aus |
| On-chain / Futures / Optionen / Makro | nein | gesperrt | erst nach klarer, zeitstempelsicherer Begruendung |

Download bedeutet nie automatisch Handelsentscheidung. Jede Quelle muss diese
Reihenfolge durchlaufen:

1. vollstaendig, frisch und qualitaetsgeprueft lokal vorhanden
2. lookahead-sicher an jeder 1m-Entscheidung ausrichtbar
3. Training-only Gewinner-/Verlierer-Trennung dokumentiert
4. hoechstens ein kleiner separater Filter-/Score-Kandidat
5. dieselben Kosten-, PF-, Drawdown- und Aktivitaetsgates bestehen
6. vor Blindtest einfrieren
7. erst nach Blindtest als uebernehmbarer Baustein zulassen

## 6. Bestaetigte Full-Runs

### `run_20260626_210349`

Dieser Run ist die aktuell wichtigste Wahrheit aus den Reports.

Kernwerte:

- Typ: `full_backtest`
- Status: `completed`
- Version: `activity_first_v10_context_market_filter`
- Candidate-Space: `trade_allowed_found`
- Start/Ende: 100.00 -> 107.66 USDC
- Gesamt-PnL: +7.66 USDC (+7.66%)
- Gewinn/Tag: +0.02097 USDC/Tag
- Ziel: 3.00 USDC/Tag
- Zielquote: ca. 0.0070
- Trades: 98 gesamt, ca. 0.27 pro Tag
- Positive/negative Tage: 38 / 44
- Bester/schlechtester Tag: +5.58 / -4.79 USDC
- Training bester Kandidat: ca. +0.03 USDC/Tag
- Datenbereiche: 8 usable, 8 im Backtest verwendet, 3 nicht verfuegbar

Was dieser Run beweist:

- Der alte 0-Trade-Blocker ist gebrochen.
- Full/UI/Smoke-Pfad kann die neue Activity-First-Engine ausfuehren.
- aggTrades und Kontextmaerkte koennen echte Handelsfilter erzeugen.
- Der Bot ist nicht mehr nur Datenstatus/Diagnose; Daten koennen Entscheidungen
  veraendern.

Was dieser Run nicht beweist:

- Er erreicht nicht 3 USDC/Tag.
- Er ist keine Live-/Paper-Freigabe.
- Er bestaetigt noch nicht den spaeter eingebauten Fee-Rescue-Patch.
- Er beweist nicht, dass BookTicker/Depth, On-chain, Futures, Optionen oder
  Makro genutzt werden duerfen.

### `run_20260627_063203`

Dieser Run war der erste Full-Backtest nach dem Fee-Rescue-Patch.

Kernwerte:

- Typ: `full_backtest`
- Status: `completed`
- Version im Report: `activity_first_v10_context_market_filter`
- Candidate-Space: `trade_allowed_found`
- Start/Ende: 100.00 -> 107.66 USDC
- Gesamt-PnL: +7.66 USDC (+7.66%)
- Gewinn/Tag: +0.02097 USDC/Tag
- Ziel: 3.00 USDC/Tag
- Trades: 98 gesamt, ca. 0.27 pro Tag
- Datenbereiche: 8 usable, 8 im Backtest verwendet, 3 nicht verfuegbar

Diagnose:

- Der Fee-Rescue-Patch war aktiv: Learned Rules enthalten `learning_scope`.
- Es wurden aber keine `gross_edge_fee_rescue_eth_candidate` Regeln gefunden.
- `eligible_gross_edge_fee_rescue_candidate_count` war 0.
- Das Ergebnis blieb exakt gleich wie `run_20260626_210349`.
- Daraus folgt: Nicht die Datenanbindung ist jetzt der Engpass, sondern der
  ETH-Basissuchraum. Es gab nur 392 Basiskandidaten und nur 4 netto-positive
  ETH-Kandidaten.

### `run_20260627_071724`

Dieser Run war der erste Full-Backtest nach der V11-ETH-Regime-Erweiterung.

Kernwerte:

- Typ: `full_backtest`
- Status: `completed`
- Version im Report: `activity_first_v11_eth_regime_expanded`
- Candidate-Space: `trade_allowed_found`
- Training bester Kandidat: ca. +0.15 USDC/Tag
- Start/Ende: 100.00 -> 0.24 USDC
- Gesamt-PnL: -99.76 USDC (-99.76%)
- Gewinn/Tag: -0.2733 USDC/Tag
- Ziel: 3.00 USDC/Tag
- Trades: 349 gesamt, ca. 0.96 pro Tag
- Datenbereiche: 8 usable, 8 im Backtest verwendet, 3 nicht verfuegbar
- Ausgewaehlter Kandidat:
  `eth_regime_expanded_eth_us_impulse_entry_lb5_th0.011_tp0.055_sl0.022_hold2160_orderflow_taker_buy_quote_imbalance_filter`

Diagnose:

- V11 hat den 0-Trade-Blocker nicht zurueckgebracht; Trades und Datenpfade
  funktionieren.
- V11 hat aber stark overfittet: Training sah besser aus, Blindtest war massiv
  negativ.
- Die Ursache ist nicht ein fehlender Download, sondern eine zu breite
  Pool-Auswahl ohne interne Validierung.
- 25 Kandidaten wurden in den Pool genommen; einige Einzelkandidaten waren
  diagnostisch positiv, viele andere zerstoerten den gemeinsamen Kapitalpfad.
- Blindtest-Einzelkandidaten duerfen nicht als Auswahlgrund benutzt werden.
  Diese Diagnose ist nur Fehleranalyse, kein Lernsignal.
- V11 unveraendert darf nicht erneut als naechster Full-Run gestartet werden.

### `run_20260627_082716`

Dieser Run war der erste Full-Backtest nach dem V12-Validation-Guard.

Kernwerte:

- Typ: `full_backtest`
- Status: `completed`
- Version im Report: `activity_first_v12_validation_guard`
- Base-Version: `activity_first_v11_eth_regime_expanded`
- Candidate-Space: `trade_allowed_blocked`
- Training bester Kandidat: ca. +0.14 USDC/Tag
- Blindtest: 0 Trades, 0.00 USDC/Tag
- Datenbereiche: 8 usable, 8 im Backtest verwendet, 3 nicht verfuegbar

Wichtige Validation-Werte:

- `pre_validation_trade_allowed_count`: 226
- `post_validation_trade_allowed_count`: 53
- der V12-Top-Pool waere auf `selection_validation` leicht positiv gewesen:
  +7.83 USDC / ca. +0.0435 USDC/Tag
- trotzdem blockiert wegen:
  - `validation_pool_fee_to_gross_ratio`: ca. 0.827, also ueber Limit 0.70
  - `validation_pool_max_drawdown`: ca. 29.56%, also ueber Limit 25%
  - `validation_pool_rejection_reason`: `rejected_by_fees`

Diagnose:

- V12 hat den V11-Kontozerstoerer korrekt verhindert.
- Das Ergebnis ist kein alter 0-Trade-Bug.
- Es gab 53 intern validierte Kandidaten als Potenzial-Bibliothek.
- Der Fehler/Engpass war die starre Top-N-Poolbildung: Sie nahm 7 Kandidaten,
  obwohl der gemeinsame Pool zu teuer und zu instabil war.

### `run_20260627_114634`

Dieser Run war der erste Full-Backtest nach dem V13-Validation-Optimized-Pool.

Kernwerte:

- Typ: `full_backtest`
- Status: `completed`
- Version im Report: `activity_first_v13_validation_optimized_pool`
- Base-Version: `activity_first_v11_eth_regime_expanded`
- Candidate-Space: `trade_allowed_found`
- Training bester Kandidat: ca. +0.14 USDC/Tag
- Validation-Pool: 3 Kandidaten, ca. +0.3127 USDC/Tag auf
  `selection_validation`
- Blindtest: -10.23 USDC, -0.0280 USDC/Tag
- Trades: 189
- Blindtest-Max-DD: ca. 41.29%

Diagnose:

- V13 hat einen echten Pool gebaut und der Blindtest wurde ausgefuehrt.
- V13 war besser als V11, weil kein Konto-Crash entstand.
- V13 war schlechter als no-trade, weil der Pool im echten Blindtest negativ
  war.
- Zwei der drei Pool-Kandidaten waren im Blindtest diagnostisch positiv:
  - `eth_us_impulse_entry...orderflow_taker_buy_quote_imbalance_filter`:
    ca. +7.13 USDC
  - `eth_continuation_after_impulse_lb30...`: ca. +4.25 USDC
- Der dritte Kandidat kippte stark:
  - `eth_continuation_after_impulse_lb15...`: ca. -21.60 USDC
- Engpass: mehrere sehr aehnliche Continuation-Regime-Varianten duerfen nicht
  parallel in den Pool, wenn ihr Zusatznutzen in Validation nur klein ist.

## 7. Lokaler V14-Patch nach `run_20260627_114634`

Problem:

V11 zeigte, dass mehr Daten und mehr ETH-Kandidaten nicht reichen. Der Router
fand viele training-positive Kandidaten, aber die Pool-Auswahl war zu breit und
zu stark auf das Training angepasst. Das Ergebnis war ein massiver Blindtest-
Verlust.

Patch V12 war der erste Schutz:

- Neuer Report-/Router-String: `activity_first_v12_validation_guard`.
- Die V11-Basiskandidaten bleiben erhalten und werden als
  `base_candidate_generation_version = activity_first_v11_eth_regime_expanded`
  dokumentiert.
- Die 730 offiziellen Trainingstage werden intern geteilt:
  - `selection_train`: frueherer Teil des Trainings
  - `selection_validation`: spaeterer Teil des Trainings, maximal ca. 180 Tage
- Basiskandidaten und Training-only Filter werden nur auf `selection_train`
  gelernt.
- Nur Kandidaten, die danach auf `selection_validation` ebenfalls die Kosten-,
  PF-, Drawdown- und Aktivitaetsregeln bestehen, duerfen in die Pool-Auswahl.
- Der Pool wird enger:
  - maximal 8 Kandidaten
  - maximal 2 Kandidaten pro Familie
  - keine mehrfachen Varianten desselben Base-Candidates parallel, wenn nur der
    Filtername anders ist
- Vor dem 365-Tage-Blindtest wird der geplante Pool auf
  `selection_validation` als gemeinsames Konto gestresst.
- Wenn dieser Validierungs-Pool netto nicht positiv, zu teuer, zu instabil oder
  zu drawdown-lastig ist, wird kein Blindtest-Trade ausgefuehrt.

Was V12 soll:

- V12 soll nicht garantiert 3 USDC/Tag liefern.
- V12 soll zuerst den V11-Overfit-Crash verhindern.
- Ein 0-Trade-Ergebnis nach V12 kann korrekt sein, wenn Training zwar Kandidaten
  findet, die interne Validierung aber keinen robusten Pool bestaetigt.
- Ein positiver V12-Full-Run ist wertvoller als ein aggressiver V11-Run mit
  hohem Trainingsergebnis und schlechtem Blindtest.

Patch V13:

- Neuer Report-/Router-String:
  `activity_first_v13_validation_optimized_pool`.
- Die 53+ Validation-Kandidaten bleiben als Potenzial-Bibliothek sichtbar.
- Der Handels-Pool wird nicht mehr pauschal als Top-N-Pool genommen.
- Stattdessen wird der Pool innerhalb von `selection_validation` konservativ
  aufgebaut:
  - Kandidaten werden nach Validation-Qualitaet betrachtet.
  - Maximal 8 Kandidaten, maximal 2 pro Familie.
  - Keine doppelten Base-Candidates mit nur anderem Filter.
  - Ein Kandidat wird nur hinzugefuegt, wenn der gemeinsame Pool danach weiter
    netto besser ist.
  - Der gemeinsame Pool muss weiterhin Aktivitaet, Fees, Profit Factor und
    Drawdown bestehen.
- Dieser Schritt benutzt weiterhin keine Blindtestdaten.
- Ziel ist nicht, die Gates zu lockern, sondern aus der validierten Bibliothek
  nur die Kombination zu handeln, die als gemeinsames Konto robust bleibt.

Patch V14:

- Neuer Report-/Router-String:
  `activity_first_v14_conservative_regime_pool`.
- Der V13-Optimizer bleibt, wird aber konservativer:
  - maximal 1 Kandidat pro Strategie-Familie/Regime
  - ein weiterer Kandidat darf den Pool nur erweitern, wenn er den
    Validation-Pool um mindestens ca. +0.03 USDC/Tag verbessert
  - der Zusatznutzen wird als `incremental_validation_quote_per_day`
    dokumentiert
- Ziel: keine fast identischen Regime-Varianten parallel handeln, solange noch
  kein echter Situations-Router existiert.
- Kein Blindtest-Lernen, kein Gate-Lockern, kein Fake-Trade.

Pflichtfelder im naechsten Report:

- `candidate_generation_version = activity_first_v14_conservative_regime_pool`
- `base_candidate_generation_version = activity_first_v11_eth_regime_expanded`
- `selection_validation_guard_used = true`
- `validation_optimized_pool_used = true`
- `conservative_regime_pool_used = true`
- `selection_validation.learning_scope = selection_train_only`
- `selection_validation.pre_validation_trade_allowed_count`
- `selection_validation.post_validation_trade_allowed_count`
- `selection_validation.pool_selection.pool_selection_version`
- `selection_validation.validation_pool_passed`
- `selection_validation.validation_pool_rejection_reason`
- `selection_policy = selection_train_validation_guard_pool_one_shared_account_context`

Technischer Status nach lokalem V14-Patch:

- `python -m compileall src tests` gruen.
- `python -m pytest -q` gruen.
- `git diff --check` gruen.
- V14 ist technisch noch nicht durch einen Full-Backtest bestaetigt.

Nach dem ersten V13-Startversuch wurde kein neuer Run-Ordner erzeugt. Ursache
war kein Python-Cache, sondern eine korrupte/halb geschriebene
`data/live_microstructure/ETHUSDC/status.json` mit NUL-Bytes. Dadurch brach die
Datenprüfung vor der Run-ID-Erstellung ab. Der Fix ist lokal eingebaut:

- `src/data/live_microstructure.py` liest kaputte Statusdateien als "missing"
  statt mit `JSONDecodeError` abzubrechen.
- Statusdateien werden atomar ueber Temp-Datei + Replace geschrieben.
- `tests/test_live_microstructure.py` prueft korrupte Statusdateien und
  atomaren Rewrite.
- `ensure_all_backtest_market_data_ready()` lief danach erfolgreich durch.

## 8. Fee-Rescue-Patch: bestaetigt, aber ohne Effekt

Nach dem positiven Run wurde ein gezielter Fee-Rescue-Patch eingebaut.

Problem:

Die Filter-Learner durften bisher fast nur Kandidaten verbessern, die schon vor
Filterung netto positiv waren. Dadurch wurden ETH-Kandidaten ignoriert, die
brutto ein Signal hatten, aber durch Fees/Noise netto kaputtgingen. Genau solche
Kandidaten sind ein sinnvoller Anwendungsfall fuer Orderflow/aggTrades/Context.

Patch:

- HTF-, Kline-Orderflow-, aggTrade- und Context-Learner nutzen jetzt
  `_filter_learning_eligible`.
- Erlaubt sind weiterhin nur ETH-Kandidaten.
- Kandidaten brauchen mindestens 40 Trades, 20 Gewinner und 20 Verlierer.
- Netto-positive ETH-Kandidaten bleiben erlaubt.
- Netto-negative ETH-Kandidaten duerfen nur dann Filter lernen, wenn sie
  Brutto-Edge haben und `fees / gross_pnl <= 1.50`.
- Die finale gefilterte Variante muss danach unveraendert alle Gates bestehen:
  Aktivitaet, Fees, Profit Factor, Drawdown.
- Kein TP/SL-Lockern.
- Kein Blindtest-Lernen.
- Kein Fake-Trade.
- Kein zweiter Backtestpfad.

Technischer Status nach Patch:

- `python -m compileall src tests` gruen
- `python -m pytest -q` gruen
- `git diff --check` gruen

Dieser Patch ist technisch aktiv, aber `run_20260627_063203` zeigte keinen
Performance-Effekt, weil keine gross-edge fee-rescue Regeln gelernt wurden. Er
darf im Code bleiben. Nach `run_20260627_071724` ist der naechste Hebel nicht
mehr "mehr Suchraum", sondern interne Validation gegen Overfit.

## 9. Pflichtreport fuer jede Quelle und jeden Run

Der Activity-First-Report muss je Quelle sichtbar machen:

- verfuegbar / verwendet / fuer Handelsentscheidung verwendet
- Gewinner-/Verlierer-Stichprobe, Mittelwerte und Differenz
- erzeugte und zugelassene Filterkandidaten
- gefilterte Signale, Trade-Effekt, Kosten, PF und Drawdown
- Kandidatenraum vor/nach der Quelle
- Blindtest-Trades, USDC/Tag und Zielverhaeltnis
- Datenstichtag, Version und ob Regeln vor Blindtest eingefroren sind
- ob `gross_edge_fee_rescue_eth_candidate` beteiligt war

Besonders nach dem naechsten Full-Run pruefen:

- `candidate_generation_version`
- ob `activity_first_v14_conservative_regime_pool` im Report steht
- ob `base_candidate_generation_version = activity_first_v11_eth_regime_expanded`
  im Report steht
- `selection_validation_guard_used`
- `validation_optimized_pool_used`
- `conservative_regime_pool_used`
- `selection_validation.learning_scope`
- `selection_validation.pre_validation_trade_allowed_count`
- `selection_validation.post_validation_trade_allowed_count`
- `selection_validation.pool_selection.selected_count`
- `selection_validation.pool_selection.accepted_steps`
- `selection_validation.validation_pool_passed`
- `selection_validation.validation_pool_rejection_reason`
- `candidate_space_status`
- `trade_allowed_setup_count`
- `selected_pool_size`
- `best_training_quote_per_day`
- `blindtest_trade_count`
- `blindtest_quote_per_day`
- `aggtrade_filter_integration`
- `context_market_filter_integration`
- `htf_filter_integration`
- `kline_orderflow_filter_integration`
- `eligible_gross_edge_fee_rescue_candidate_count`
- `learned_rules[*].learning_scope`
- ob `eth_regime_expanded` Kandidaten erzeugt, positiv sind oder trade_allowed werden

## 10. Verbindliche naechste Schritte fuer GPT/Codex

Wenn GPT/Codex hier weiterarbeitet, exakt so vorgehen:

1. Diese README zuerst lesen. Nicht alten Memory-/Spec-Dateien blind vertrauen.
2. Danach `docs/GPT_DEEP_CONTINUATION_PLAN_20260627.md` lesen.
3. Keine GitHub-Aktion starten, ausser der Nutzer verlangt es ausdruecklich.
4. Vor einem Backtest zwingend ausfuehren:
   - `python -m compileall src tests`
   - `python -m pytest -q`
   - `git diff --check`
5. Wenn ein Backtest laufen soll: UI komplett schliessen, neu starten, dann Full
   ueber den UI-Button starten.
6. Der naechste wichtige Run ist ein Full-Backtest mit dem lokalen
   V14-Conservative-Regime-Pool-Patch aus Abschnitt 7.
7. Nach dem Run zuerst nur lesen und diagnostizieren:
   - Steht `candidate_generation_version = activity_first_v14_conservative_regime_pool`?
   - Steht `base_candidate_generation_version = activity_first_v11_eth_regime_expanded`?
   - Wie viele Kandidaten waren vor Validation trade_allowed?
   - Wie viele Kandidaten blieben nach Validation trade_allowed?
   - Wie viele Kandidaten wurden vom Validation-Optimizer angenommen?
   - Hat der optimierte Validation-Pool-Stresstest bestanden?
   - Falls nein: welcher `validation_pool_rejection_reason`?
   - Wurde Blindtest ausgefuehrt oder korrekt blockiert?
   - Wurde USDC/Tag verbessert oder nur Training overfittet?
   - Sind Drawdown, Profit Factor und Fees plausibel?
8. Wenn V14 keinen Blindtest-Pool erlaubt, nicht Gates lockern. Dann zuerst
   pro Familie pruefen, welche Kandidaten an `selection_validation` scheitern.
9. Wenn V14 einen stabil positiven Blindtest liefert, Report dokumentieren und
   erst dann den naechsten kleinen Codebaustein planen.

Erlaubte naechste Codebausteine, falls der Full-Run weiterhin weit unter 3
USDC/Tag bleibt:

- ETH-spezifische Familien nach `selection_train` und `selection_validation`
  getrennt diagnostizieren.
- Schlechte Familien nur nach Trainings-Validation-Evidenz eingrenzen, nicht
  nach Blindtest-Tuning.
- Kombinierte Filter nur dann erlauben, wenn sie `selection_train` und
  `selection_validation` verbessern.
- Report um "welche Phase hat gewonnen/verloren" erweitern.
- Activity/Fee/Drawdown-Rejections pro Familie besser sichtbar machen.
- Monatskonfigurations-Export erst bauen, wenn ein Full-Run deutlich naeher am
  Ziel ist.

Verbotene naechste Codebausteine:

- Gates lockern, nur damit 3 USDC/Tag erscheint.
- Blindtestdaten fuer Auswahl/Schwellen lernen.
- Separate Smoke-Engine bauen.
- BookTicker/Depth historisch simulieren, solange keine 30 echten sauberen Tage
  vorhanden sind.
- On-chain/Futures/Options/Makro mit unklaren oder nicht zeitstempelsicheren
  Quellen einbauen.
- Live/Paper/echte Orders aktivieren.

## 11. Pflicht fuer Aenderungen

Vor Aenderungen: diese README lesen. Danach nur den kleinsten nachweisbaren
Baustein umsetzen. Nach jeder Codeaenderung zwingend:

```bat
python -m compileall src tests
python -m pytest -q
git diff --check
```

Keine Rohdaten, lokalen Reports oder Live-Snapshots committen.
