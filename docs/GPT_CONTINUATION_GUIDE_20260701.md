# GPT / Codex Continuation Guide - 2026-07-01

Diese Datei ist die aktuelle Arbeitsanweisung fuer GPT, Codex oder jeden
anderen Agenten, der das Projekt weiterentwickelt.

## 1. Ziel

Baue keinen beliebigen Tradingbot. Baue einen ETHUSDC-spezifischen
Research-/Backtestprozess:

- Binance Spot
- ETHUSDC
- LONG-only
- 100 USDC Einsatzbasis
- 730 Tage Training / Optimierung
- danach 365 Tage Blindtest
- Ziel: mindestens 3 USDC/Tag im Blindtest

Das Ziel darf nur durch echte, vor dem Trade bekannte Muster erreicht werden.
Blindtest-Lernen, Lookahead, Fake-Trades oder harte Gate-Lockerung sind
verboten.

## 2. Wie gearbeitet werden soll

Arbeite wie ein guter Research-Engineer, nicht wie ein Ergebnis-Faker:

1. Lies zuerst `README.md` und `AGENTS.md`.
2. Bestimme den aktuellen Backtestpfad, bevor du patchst.
3. Aendere immer nur eine fachliche Hypothese auf einmal.
4. Trenne Training, Walkforward/Validation und Blindtest strikt.
5. Erzeuge einen Report, der zeigt:
   - welche Datenquelle verfuegbar war;
   - ob sie wirklich verwendet wurde;
   - ob sie Training-Gewinner von Training-Verlierern trennt;
   - ob sie Score/Gate/Filter veraendert;
   - wie viele Kandidaten zusaetzlich trade_allowed werden;
   - ob Blindtest-Trades entstehen;
   - ob 3 USDC/Tag naeher kommt.
6. Wenn ein Ansatz scheitert, schreibe den Befund auf und hoere auf, denselben
   Ansatz ueber TP/SL/Hold/Gates zu erzwingen.
7. Nach jeder Codeaenderung:

```bat
python -m compileall src tests scripts
python -m pytest -q
git diff --check
```

## 3. Aktueller Hauptbot

Der produktive Backtestpfad bleibt:

```text
activity_first_router
```

Smoke und Full muessen denselben Pfad verwenden. Falls du zwei Engines findest,
ist das ein Bug: die UI muss auf den einen gepatchten Pfad zeigen, oder der alte
Pfad muss entfernt werden.

## 4. Lokale Rohdaten

Diese Daten sind lokal vorhanden, aber nicht fuer GitHub bestimmt:

```text
data/candles/ETHUSDC_1m.csv
data/candles/BTCUSDC_1m.csv
data/candles/ETHBTC_1m.csv
data/candles/ETHUSDT_1m.csv
data/candles/USDCUSDT_1m.csv
data/exchange_info/ETHUSDC_exchange_info.json
data/market_features/agg_trades/ETHUSDC/*.csv
data/live_microstructure/ETHUSDC/*.jsonl
```

Klines enthalten OHLCV plus Binance-Kline-Orderflow:

- quote asset volume
- number of trades
- taker buy base volume
- taker buy quote volume

AggTrade-Minutenfeatures liefern z. B.:

- agg trade count
- raw trade count / compacted trade count
- taker buy / taker sell imbalance
- max agg trade quote
- vwap-nahe Minutenmetriken

Derived Timeframes duerfen aus ETHUSDC 1m gebaut werden:

- 5m
- 15m
- 30m
- 1h
- 4h
- 1d

Regel: Eine hoeherzeitige Kerze darf erst verwendet werden, nachdem sie im
historischen Ablauf vollstaendig geschlossen war.

## 5. Was nicht erneut gebaut werden soll

Diese Spuren sind abgeschlossen und nicht integrationsfaehig:

### Attempt 053

Nicht reproduziert. Die alte behauptete Performance darf nicht als Wahrheit
uebernommen werden.

### ERRO-L v1

Feste Version und Ablation waren negativ. Nicht in den Router integrieren.

### ECMD-L v1

Signal-Funnel hatte Signale, aber kein robustes Walkforward-Execution-Template.
Nicht ueber Exit-/Hold-Tuning erzwingen.

### EPX-L / R2-v2 / R2-v3

R2-v2 fand Tradeability-Kandidaten, aber Execution scheiterte. R2-v3
First-Touch/Path-Gate zeigte:

- `status = no_path_gate_candidate`
- 2 Varianten geprueft
- 0 Varianten fuer Execution/Blindtest zugelassen
- Blindtest-Kandidaten ausgewertet: 0
- bester Pfad hatte relativen Lift, aber zu geringe absolute Path-Qualitaet
  und zu niedrige Target-before-Stop-Rate

Nicht weiter ueber TP/SL/Hold/Gates retten.

## 6. Aktueller Research-Schritt: ERH-v1

Aus den zwei Arena.ai-Antworten wurde ERH-v1 als bessere naechste Grundlage
gewaehlt:

- `src/research/erh_v1.py`
- `scripts/run_erh_v1_research.py`
- `tests/test_erh_v1_research.py`

ERH-v1 ist ein 4h/1h-Regime-Persistence-Ansatz:

- ETHUSDC 4h Trend-Regime
- ETHBTC 4h Leadership als Kern
- BTCUSDC 4h Risk-/Crash-Filter
- ETHUSDT/USDCUSDT Cross-Quote-/Peg-Filter
- ETHUSDC Kline-Orderflow auf 4h aggregiert
- 1h Entry-Timing innerhalb aktiver 4h-Regimes

ERH-v1 ist weiterhin research-only. Erst wenn Training/Walkforward besteht,
darf der Runner genau einen eingefrorenen Blindtest ausfuehren. Keine UI- oder
Router-Integration vor bestaetigter Evidenz.

Stand nach lokalem ERH-v1-Run nach Next-Open-Korrektur:

- `strategy_version = erh_v1_htf_regime_research_20260701`
- `status = no_training_walkforward_candidate`
- 8 Varianten getestet
- 0 Varianten eligible
- 0 Blindtest-Kandidaten ausgewertet
- Wichtiger Bugfix: Signale auf geschlossenen 1h/4h-Kerzen werden nicht mehr
  auf dem Open derselben bereits geschlossenen Kerze gehandelt. Entry entsteht
  nur als Pending Entry und wird am naechsten 1h-Open ausgefuehrt.
- Beste Variante nach PnL war trotzdem nur `erh_score4_arm30_give30`:
  - 123 Validation-Trades
  - ca. `-98.53 USDC`
  - Profit Factor ca. `0.286`
  - positive Folds: `0/6`
  - Median Trade PnL ca. `-0.916 USDC`
  - Max Drawdown > `100 USDC`

Konsequenz:

- kein UI-Full-Backtest fuer ERH-v1;
- kein Blindtest, weil Training/Walkforward nicht bestanden wurde;
- kein blindes Lockern von Score, Orderflow, Trail oder Stop;
- ERH-v1 ist archiviert, ausser ein zukuenftiger Agent findet einen neuen,
  konkreten technischen Fehler. Reines Hysterese-/Gate-Tuning ist verboten.

Wenn Arena.ai erneut gefragt wird, aktuellen Prompt verwenden:

```text
docs/ARENA_AI_REQUEST_AFTER_ERH_V1_20260701.md
```

Arena.ai hat danach sinnvollerweise keinen neuen Strategieversuch empfohlen,
sondern ERH-v1-DIAG:

- `src/research/erh_v1_diagnostics.py`
- `scripts/run_erh_v1_diagnostics.py`
- `tests/test_erh_v1_diagnostics.py`

Dieser Diagnose-Run darf keine Parameter aendern und keinen Blindtest starten.
Er trennt:

- Frequenzproblem
- echter Edge-Fehlschlag
- Implementierungs-/Gate-Definitionsfehler
- Validierungs-/Fold-Mismatch

Stand nach lokalem ERH-v1-DIAG:

- `strategy_version = erh_v1_signal_funnel_diagnostic_20260701`
- `status = diagnostic_complete`
- `suspected_root_cause_category = B_genuine_edge_problem`
- Empfehlung: ERH-v1 als wahrscheinlich nicht handelbaren Edge behandeln,
  solange kein konkreter Implementierungsbug gefunden wird.

Wichtige Zahlen:

- Hard-Gate aktive 4h-Bars: 416
- Hard-Gate Episoden: 178
- Score>=3 aktive 4h-Bars: 334
- Score>=3 Episoden: 146
- Score>=4 aktive 4h-Bars: 248
- Score>=4 Episoden: 119
- Keine massive NaN-/Join-Anomalie in den Kernfeatures:
  - ETH Trend Gate true rate ca. 50.3%
  - ETHBTC Trend Gate true rate ca. 38.6%
  - ETHBTC Slope Gate true rate ca. 41.7%
  - Orderflow Gate true rate ca. 40.4%
  - BTC not crash Gate true rate ca. 95.7%
  - USDC/Basis fast immer true; das ist ein Sanity-Filter und kein Blocker.

Unconditional-Regime-Return-Test nach Next-Open-Korrektur:

- Score>=3:
  - 146 Episoden
  - total ca. `-72.80 USDC`
  - Profit Factor ca. `0.442`
  - Win Rate ca. `30.14%`
  - Avg Return/Episode ca. `-0.499%`
- Score>=4:
  - 119 Episoden
  - total ca. `-77.90 USDC`
  - Profit Factor ca. `0.332`
  - Win Rate ca. `29.41%`
  - Avg Return/Episode ca. `-0.655%`
- Buy-and-hold ueber denselben Full-Train-Zeitraum lag bei ca. `+28.99 USDC`.

Interpretation:

- ERH-v1 scheitert nicht daran, dass es keine Regime oder keine Trades gibt.
- ERH-v1 scheitert auch nicht offensichtlich an einem NaN-/Join-Bug.
- Die definierte Regime-Idee filtert im Training schlechter als einfaches
  ETH-Halten und erzeugt nach Kosten keinen Edge.

Konsequenz:

- kein UI-Full-Backtest fuer ERH-v1;
- kein ERH-v1-Exit-/Gate-Tuning;
- ERH-v1 ist nicht der naechste Pfad.

## 7. Aktueller Research-Schritt: ETH Edge Existence Scan

Aus den zwei letzten Arena.ai-Antworten wurde der zweite Vorschlag gewaehlt:
nicht weiter ERH-v1 retten, sondern direkt messen, ob vorhandene Features
ueberhaupt nach Kosten positive Long-only Forward-Returns zeigen.

Dateien:

- `src/research/eth_edge_scan.py`
- `scripts/run_eth_edge_existence_scan.py`
- `tests/test_eth_edge_scan.py`

Regeln des Scans:

- training-only, kein Blindtest;
- keine Strategie, keine Trades, keine UI-/Router-Integration;
- jedes Feature wird in Quintile geteilt;
- Forward-Horizonte: 1h, 4h, 12h, 24h, 72h;
- Feature-Zeile `i` darf erst nach Close bekannt sein;
- hypothetischer Entry: Zeile `i+1` Open;
- Exit: `horizon` Stunden spaeter;
- Kostenmodell: bestehendes Spot-Roundtrip-Modell, ca. `0.22%`;
- Edge-Kandidat nur, wenn bestes Quintil nach Kosten positiv ist und in
  mindestens 3 Folds stabil positiv bleibt.

Lokaler Run:

- `strategy_version = eth_edge_existence_scan_20260701`
- `status = edge_candidate_found`
- `edge_candidate_count = 24`
- `reversion_candidate_count = 8`
- `momentum_candidate_count = 15`
- Output:
  `reports/research/eth_edge_scan/eth_edge_existence_scan_report.json`

Top-Trainingsbefunde:

1. `btc_4h_drawdown_from_20d_high`, 72h, q4:
   - BTC naeher am 20-Tage-Hoch / Risk-On
   - Mean nach Kosten ca. `+1.426 USDC` pro 100 USDC Hypothesenhold
   - positive Folds `5/6`
   - Winrate ca. `57.4%`
2. `btc_4h_close_vs_ema20`, 72h, q4:
   - Mean nach Kosten ca. `+0.762 USDC`
   - positive Folds `4/6`
3. `ethbtc_4h_ret_6`, 72h, q0:
   - ETHBTC war relativ schwach, Reversion-Kandidat
   - Mean nach Kosten ca. `+0.722 USDC`
   - positive Folds `5/6`
4. `eth_4h_dist_to_20d_high`, 72h, q0:
   - ETH weiter weg vom 20-Tage-Hoch, Dip-/Reversion-Kandidat
   - Mean nach Kosten ca. `+0.604 USDC`
   - positive Folds `4/5`

Interpretation:

- Bisherige bestaetigungsbasierte Momentum-/Leadership-Entries waren
  wahrscheinlich zu spaet.
- Die Daten deuten eher auf 24-72h Long-Holds in BTC-Risk-On-Phasen und/oder
  ETH/ETHBTC-Dip-Reversion statt Chase-Momentum.
- Der Scan beweist noch keine handelbare Strategie, aber er gibt den naechsten
  sinnvollen research-only Pfad vor.

Dieser Schritt wurde umgesetzt. Siehe BRH/ERV-v1 unten.

## 8. Aktueller Research-Schritt: BRH/ERV-v1

Aus dem Edge-Scan wurde genau eine research-only Hypothese gebaut, keine
UI-/Router-Integration:

```text
ERV/BRH-v1:
BTC-Risk-On ETH 72h Hold + ETHBTC/ETH-Dip-Reversion-Filter
```

Dateien:

- `src/research/brh_v1.py`
- `scripts/run_brh_v1_research.py`
- `tests/test_brh_v1_research.py`

Regeln:

- nur Training/Walkforward fuer Auswahl verwenden;
- fixed 72h Hold als Startpunkt aus dem Edge-Scan;
- Quantile je Fold nur aus dem jeweiligen Trainingsteil kalibrieren;
- Signale nur auf neuen geschlossenen 4h-Availability-Rows;
- Entry erst am naechsten 1h-Open;
- Exit nach 72h am 1h-Open;
- Overlap/one-position-at-a-time strikt beachten;
- Kostenmodell unveraendert lassen;
- nur einen eingefrorenen Blindtest ausfuehren, wenn Training/Walkforward
  robuste Kandidaten zeigt.

Lokaler Run:

- `strategy_version = brh_v1_btc_risk_on_eth_reversion_hold_20260701`
- `status = blindtest_completed`
- `eligible_variant_count = 5 / 7`
- `blindtest_candidate_count_evaluated = 1`
- Output:
  `reports/research/brh_v1/brh_v1_research_report.json`

Training/Walkforward:

- 7 feste Varianten:
  - BTC-Risk-On 72h
  - Dual BTC-Risk-On 72h
  - BTC-Risk-On + ETHBTC-Dip
  - BTC-Risk-On + ETH-Dip
  - BTC-Risk-On + Any-Dip
  - BTC-Risk-On + Dual-Dip
  - BTC-Risk-On + Orderflow-Cooldown
- 5 Varianten eligible
- alle 5 eligible Varianten hatten `6/6` positive Folds
- Top nach Training-PnL:
  - `brh_dual_btc_risk_on_72h`
  - ca. `+142.26 USDC`
  - ca. `+0.259 USDC/Tag`
  - 52 Trades
  - PF ca. `3.65`
- Ausgewaehlt wurde training-only nach PF:
  - `erv_risk_on_orderflow_cooldown_72h`
  - ca. `+135.41 USDC`
  - ca. `+0.246 USDC/Tag`
  - 45 Trades
  - PF ca. `3.95`

Frozen Blindtest der ausgewaehlten Variante:

- PnL gesamt: `+4.647 USDC`
- USDC/Tag: `+0.0127`
- Trades: `22`
- PF: ca. `1.10`
- Positive/negative Trades: `10 / 12`
- Median Trade PnL: ca. `-0.373 USDC`
- Max Drawdown: ca. `26.58 USDC`

Interpretation:

- BRH/ERV-v1 ist der erste neue Ansatz nach den negativen Spuren, der im
  frozen Blindtest nicht direkt negativ war.
- Trotzdem ist das Ergebnis weit vom Ziel `3 USDC/Tag` entfernt.
- Der starke Training/Walkforward-Befund generalisiert im Blindtest nur sehr
  schwach.
- Das darf nicht durch Auswahlwechsel nach Blindtest, zweiten Blindtest oder
  Gate-Lockerung "repariert" werden.

Naechster kleinster sinnvoller Schritt:

BRH/ERV-v1 diagnostizieren, nicht sofort neue Strategie bauen:

```text
BRH-v1-DIAG:
Train-vs-Blind decay / regime-distribution shift / threshold stability
```

Zu pruefen:

- Haben sich die BTC-Risk-On-Thresholds im Blindtest anders verteilt?
- Waren Blindtest-Trades zu stark von wenigen Gewinnern abhaengig?
- Sind 72h-Holds im Blindtest wegen anderer Volatilitaet/Trendstruktur
  zerfallen?
- Ist Orderflow-Cooldown als Auswahlkriterium stabil oder nur Training-PF-
  Overfit?
- Haette eine andere Auswahlregel vor Blindtest rationaler sein koennen?
  Achtung: nicht nachtraeglich auf Blindtest optimieren, nur fuer eine neue
  zukuenftige Hypothese dokumentieren.

## 9. Arena.ai Auftrag

Wenn externe Hilfe genutzt wird, verwende als aktuellen Prompt:

```text
docs/ARENA_AI_REQUEST_AFTER_BRH_V1_20260701.md
```

Die Antwort darf nicht blind eingebaut werden. Waehle den besseren Vorschlag,
begruende warum, baue ihn minimal research-only, und stoppe wieder, wenn die
Evidenz nicht reicht.

## 10. Uebergabeformat nach jedem Patch

Am Ende immer berichten:

- geaenderte Dateien
- geloeschte Dateien, falls Cleanup
- welcher Ansatz getestet wurde
- Training-/Walkforward-Ergebnis
- ob Blindtest ueberhaupt erlaubt wurde
- ob UI-Backtest gestartet werden soll oder nicht
- ob Tests gruen sind
- naechster kleinster sinnvoller Schritt
