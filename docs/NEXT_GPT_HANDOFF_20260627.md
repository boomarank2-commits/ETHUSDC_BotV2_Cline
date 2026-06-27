# NEXT GPT HANDOFF - 2026-06-27

Diese Datei ist ein Arbeitszettel fuer GPT/Codex. Die normative Wahrheit bleibt
`README.md`. Wenn sich README und diese Datei widersprechen, gilt README.

Ausfuehrlicher Handlungsplan:
`docs/GPT_DEEP_CONTINUATION_PLAN_20260627.md`.

## Aktueller Stand

Projekt:

- Pfad: `C:\TradingBot\ETHUSDC_BotV2_Cline`
- Branch: `spec/activity-first-rebuild-20260623`
- Bot-Ziel: ETHUSDC Binance Spot LONG-only.
- Zielwert: 3 USDC/Tag bei 100 USDC Einsatz im 365-Tage-Blindtest.
- Keine echten Orders, kein Paper/Live, kein Short/Margin/Futures/Leverage.
- Genau eine Engine: `activity_first_router`.
- Full und Smoke muessen derselbe Backtestpfad bleiben.

## Letzte bestaetigte Runs

### `run_20260626_210349`

Erster positiver V10-Full-Run nach Datenintegration.

- `candidate_generation_version`: `activity_first_v10_context_market_filter`
- Ergebnis: +7.66 USDC total, +0.02097 USDC/Tag
- Trades: 98
- Candidate-Space: `trade_allowed_found`
- Daten: 8 usable, 8 verwendet
- Status: Positiv, aber weit unter 3 USDC/Tag
- Nicht uebernehmen.

### `run_20260627_063203`

Full-Run nach Fee-Rescue-Patch.

- Ergebnis exakt wie `run_20260626_210349`
- Fee-Rescue-Patch war aktiv (`learning_scope` sichtbar)
- `eligible_gross_edge_fee_rescue_candidate_count`: 0
- Keine Verbesserung
- Schluss: Fee-Rescue ist nicht der Engpass.

### `run_20260627_071724`

Full-Run nach V11-ETH-Regime-Suchraumerweiterung.

- `candidate_generation_version`: `activity_first_v11_eth_regime_expanded`
- Kandidaten: 1118
- `trade_allowed_setup_count`: 139
- `selected_candidate_count`: 25
- Training bester Kandidat: +0.1485 USDC/Tag
- Blindtest: -99.76 USDC total, -0.2733 USDC/Tag
- Trades: 349
- Max Drawdown: ueber 100%
- Entscheidung: NICHT UEBERNEHMEN

### `run_20260627_082716`

Full-Run nach V12-Validation-Guard.

- `candidate_generation_version`: `activity_first_v12_validation_guard`
- `base_candidate_generation_version`: `activity_first_v11_eth_regime_expanded`
- Training bester Kandidat: ca. +0.1377 USDC/Tag
- `pre_validation_trade_allowed_count`: 226
- `post_validation_trade_allowed_count`: 53
- V12-Top-Pool auf `selection_validation`:
  - ca. +7.83 USDC
  - ca. +0.0435 USDC/Tag
  - 187 Trades
  - Fee/Gross ca. 0.827
  - Max DD ca. 29.56%
- Blockiert wegen `validation_pool_rejection_reason = rejected_by_fees`
- Blindtest: 0 Trades, korrekt geblockt
- Entscheidung: NICHT UEBERNEHMEN

Diagnose: V12 hat den V11-Crash verhindert. Es ist kein alter 0-Trade-Bug.
Der Engpass ist nun die starre Top-N-Poolbildung: 53 Kandidaten bestehen die
interne Validation einzeln, aber der gemeinsame Top-Pool ist zu teuer/instabil.

### `run_20260627_114634`

Full-Run nach V13-Validation-Optimized-Pool.

- `candidate_generation_version`: `activity_first_v13_validation_optimized_pool`
- Pool auf `selection_validation`: 3 Kandidaten, ca. +0.3127 USDC/Tag
- Blindtest: -10.23 USDC, -0.0280 USDC/Tag
- Trades: 189
- Max DD: ca. 41.29%
- Zwei Pool-Kandidaten waren diagnostisch positiv, einer stark negativ.
- Hauptproblem: zu aehnliche Continuation-Regime-Varianten im gleichen Pool.

V14 wurde lokal eingebaut, aber noch nicht full-run-bestaetigt:

- `candidate_generation_version`: `activity_first_v14_conservative_regime_pool`
- maximal 1 Kandidat pro Strategie-Familie/Regime
- neuer Kandidat nur bei mindestens ca. +0.03 USDC/Tag inkrementeller
  Validation-Verbesserung
- kein Blindtest-Lernen, kein Gate-Lockern

## Historischer lokaler Patch nach `run_20260627_082716`

V13 wurde lokal eingebaut, aber noch nicht full-run-bestaetigt.

Wichtig: Wenn der Nutzer erneut `run_20260627_082716` postet, ist das weiterhin
der alte V12-Run. Ein echter V13-Run muss eine neue Run-ID haben und im Report
`activity_first_v13_validation_optimized_pool` zeigen.

Nach einem UI-Startversuch ohne neuen Run wurde ein technischer Daten-Ensure-
Blocker gefunden und gefixt: `data/live_microstructure/ETHUSDC/status.json` war
korrupt/mit NUL-Bytes gefuellt. `src/data/live_microstructure.py` behandelt
kaputte Statusdateien jetzt als fehlend und schreibt Status atomar. Tests in
`tests/test_live_microstructure.py` wurden ergaenzt. Danach lief
`ensure_all_backtest_market_data_ready()` erfolgreich durch.

- Neuer Report-String:
  `activity_first_v13_validation_optimized_pool`
- `base_candidate_generation_version` bleibt:
  `activity_first_v11_eth_regime_expanded`
- Die 53+ validation-erlaubten Kandidaten bleiben als Potenzial-Bibliothek
  sichtbar.
- Der Handels-Pool wird nicht mehr pauschal Top-N genommen.
- Pool wird auf `selection_validation` konservativ aufgebaut:
  - maximal 8 Kandidaten
  - maximal 2 pro Familie
  - keine mehrfachen Base-Candidate-Duplikate
  - Kandidat nur hinzufügen, wenn der gemeinsame Pool netto besser wird
  - gemeinsamer Pool muss Aktivitaet, Fees, Profit Factor und Drawdown bestehen
- Kein Blindtest-Lernen.
- Kein Gate-Lockern.

Bereits gelaufen waehrend V13-Patch:

```bat
python -m compileall src tests
python -m pytest tests\test_activity_first_router_report.py -q
python -m pytest -q
git diff --check
```

## Diagnose V11-Fail

V11 war kein Datenproblem. Die Daten waren da und wurden verwendet:

- ETHUSDC 1m
- Kline Quote/Trade/Taker-Felder
- HTF 5m-1d
- aggTrades
- BTCUSDC
- ETHBTC
- ETHUSDT
- USDCUSDT
- exchange_info

Das Problem war Overfit und Pool-Auswahl:

- Der erweiterte Suchraum fand viele Training-positive Kandidaten.
- Die Auswahl nahm 25 Kandidaten in den Pool.
- Viele Kandidaten waren im Training positiv, aber im Blindtest stark negativ.
- Der Pool summierte viele schlechte Blindtest-Trades und zerstoerte das Konto.
- Einzelkandidaten-Diagnose der 25 Pool-Kandidaten zeigte:
  - 6 von 25 waren im Blindtest einzeln positiv.
  - Bester einzelner Kandidat:
    - `eth_regime_expanded_eth_continuation_after_impulse_entry_lb30_th0.0085_tp0.04_sl0.016_hold1440_context_usdcusdt_deviation_filter`
    - Training: +0.1211 USDC/Tag
    - Blindtest einzeln: ca. +0.1167 USDC/Tag
    - Blindtest Trades: 66
    - Blindtest PF: ca. 1.69
    - Blindtest DD: ca. 6.67%
  - Viele andere Kandidaten waren massiv negativ, besonders:
    - `eth_range_compression_breakout_entry` mit HTF/Context-Filtern
    - `eth_opening_range_reclaim_entry` mit HTF-Filtern
    - einige aggressive `eth_us_impulse_entry` Varianten

Wichtig: Diese Einzelkandidaten-Diagnose darf nicht fuer Auswahl auf denselben
Blindtest benutzt werden. Sie ist nur zur Fehlerdiagnose da.

## Was jetzt NICHT tun

- Nicht einfach Gates lockern.
- Nicht den besten Blindtest-Einzelkandidaten hart codieren.
- Nicht Blindtestdaten fuer Schwellen/Poolauswahl verwenden.
- Nicht mehr externe Daten blind anbauen.
- Nicht BookTicker/Depth rueckwirkend simulieren.
- Nicht auf Smoke optimieren.
- Nicht live/paper/uebernehmen.
- Nicht V11 unveraendert erneut full laufen lassen; das kostet Zeit und
  bestaetigt nur den bekannten Overfit.

## Naechster technischer Schritt: V12 interne Trainings-Validierung

Ziel:

V12 soll V11 nicht verwerfen, sondern Overfit innerhalb des Trainings abfangen,
bevor der 365-Tage-Blindtest beruehrt wird.

### Grundidee

Die 730 Trainingstage werden intern in zwei Teile geteilt:

1. `selection_train`: frueherer Teil der Trainingstage
2. `selection_validation`: spaeterer Teil der Trainingstage

Kandidaten und Filter duerfen auf `selection_train` gelernt werden. Bevor sie in
den finalen Pool kommen, muessen sie auf `selection_validation` positiv und
kostenrobust sein.

Der 365-Tage-Blindtest bleibt komplett eingefroren und wird erst danach
ausgefuehrt.

## Lokal nach dieser Diagnose umgesetzt

V12 wurde lokal begonnen/eingebaut. Der Patch ist noch nicht durch einen
Full-Backtest bestaetigt.

Geaenderte Kernlogik:

- `src/router/__init__.py`
  - neuer Report-String: `activity_first_v12_validation_guard`
  - `base_candidate_generation_version` bleibt
    `activity_first_v11_eth_regime_expanded`
  - interner Split der offiziellen Trainingstage in `selection_train` und
    `selection_validation`
  - Kandidaten und Filter werden auf `selection_train` gelernt
  - nur auf `selection_validation` robuste Kandidaten duerfen in die engere
    Poolauswahl
  - Poolauswahl maximal 8 Kandidaten, maximal 2 pro Familie, keine mehrfachen
    Varianten desselben Base-Candidates
  - geplanter Pool wird auf `selection_validation` als gemeinsames Konto
    gestresst
  - falls der Validation-Pool scheitert, wird der Blindtest korrekt blockiert
- `tests/test_activity_first_router_report.py`
  - erwartet jetzt V12-Reportfelder
  - prueft Sichtbarkeit des Validation-Guards
- `README.md`
  - V11-Fail `run_20260627_071724` dokumentiert
  - V12 als aktuelle lokale Wahrheit dokumentiert

Bereits gelaufen:

```bat
python -m compileall src tests
python -m pytest tests\test_activity_first_router_report.py -q
python -m pytest -q
git diff --check
```

V12 ist technisch startbar, aber noch nicht durch einen Full-Backtest bestaetigt.

### Minimaler V12-Patch

1. In `src/router/__init__.py` einen internen Trainingssplit einfuehren.
   Vorschlag:
   - letzte 25% oder 180 Tage der 730 Trainingstage als Validation
   - Rest als Selection-Train
   - fuer Smoke proportional kuerzer, aber gleicher Pfad

2. Candidate generation bleibt wie V11.

3. Baseline- und Filter-Learner sollen idealerweise nur auf `selection_train`
   lernen.
   - Wenn das zu gross wird: erster Patch darf Kandidaten weiter auf gesamtem
     Training bauen, muss aber vor Pool-Auswahl jeden Kandidaten auf
     `selection_validation` evaluieren. Das ist weniger sauber, aber ein
     akzeptabler Zwischenpatch, solange im Report klar steht:
     `validation_leakage_risk = thresholds_learned_on_full_training`.

4. Vor `_select_candidate_pool` eine neue Validierungsschicht:
   - Kandidat auf `selection_validation` simulieren.
   - Nur zulassen, wenn:
     - Validation-Netto > 0
     - Validation-Profit-Factor >= MIN_PROFIT_FACTOR
     - Validation-Fee/Gross <= MAX_FEE_TO_GROSS_RATIO
     - Validation-Max-DD <= MAX_DRAWDOWN_PCT
     - genug Validation-Trades oder genug aktive Tage fuer ETH-Scope
   - Report muss enthalten:
     - `selection_validation_used`
     - `selection_validation_start/end`
     - `pre_validation_trade_allowed_count`
     - `post_validation_trade_allowed_count`
     - `validation_rejection_counts`
     - fuer jeden selected candidate Training- und Validation-Werte

5. Pool-Auswahl enger machen:
   - Nicht automatisch 25 Kandidaten nehmen.
   - Vorschlag fuer V12:
     - `max_count = min(8, bisheriger max_count)`
     - `family_cap = 2`
     - keine mehrfachen Varianten desselben Base-Candidates mit nur anderem
       Filter parallel aufnehmen, solange sie hoch korreliert sind.
   - Report:
     - historisch V12: `pool_selection_version = activity_first_v12_validation_guard`
     - aktuell V13: `pool_selection_version = activity_first_v13_validation_optimized_pool`
     - `selected_pool_size`
     - `pool_rejected_by_validation`
     - `pool_rejected_by_family_cap`
     - `pool_rejected_by_base_candidate_duplication`

6. Vor Blindtest Pool-Stresstest auf `selection_validation`:
   - Aggregiere den geplanten Pool auf Validation.
   - Wenn Validation-Pool netto <= 0 oder DD > 25%, dann kein Blindtest-Trade.
   - Report:
     - `validation_pool_quote_per_day`
     - `validation_pool_trade_count`
     - `validation_pool_max_drawdown`
     - `validation_pool_passed`

7. Erst danach den 365-Tage-Blindtest ausfuehren.

### Erwartetes Ziel von V12

V12 wird wahrscheinlich weniger Trades und weniger Kandidaten auswaehlen. Das ist
gut. Ziel ist nicht sofort 3 USDC/Tag, sondern:

- kein -99% Kontozerstoerer mehr
- bessere Out-of-sample-Stabilitaet
- sichtbar weniger Overfit
- vielleicht den guten Kontext-Kandidaten isolieren statt einen schlechten Pool
  darum herum zu bauen

## Danach moegliche V14-Schritte

Nur wenn V13 stabiler ist:

1. ETH-Regime-Familien einzeln bewerten:
   - continuation
   - bounce_after_flush
   - us_impulse
   - range_compression_breakout
   - opening_range_reclaim
2. Kandidatenfamilien, die in Validation/Blindtest systematisch kippen,
   temporär deaktivieren oder strenger filtern.
3. Kontext-/Orderflow-Kombinationen nur erlauben, wenn sie Selection-Train und
   Validation verbessern.
4. Monthly-config Export erst bauen, wenn ein Full-Run deutlich besser und
   stabiler ist.

## Pflicht-Checks nach jeder Codeaenderung

```bat
python -m compileall src tests
python -m pytest -q
git diff --check
```

## Naechster sinnvoller Befehl fuer GPT

Falls nach dieser Datei weitere Codeaenderungen passiert sind, zuerst komplette
Checks laufen lassen:

```bat
python -m compileall src tests
python -m pytest -q
git diff --check
```

Wenn alles gruen ist: UI komplett neu starten und genau einen Full-Backtest mit
V13 laufen lassen. Danach zuerst nur Report lesen, besonders
`selection_validation.pool_selection`, `validation_pool_passed`,
`blindtest_quote_per_day` und `blindtest_max_drawdown`.
