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

Dieser Schritt wurde umgesetzt. Siehe BRH-v1-DIAG unten.

## 9. Aktueller Research-Schritt: BRH-v1-DIAG

Aus den drei externen Antworten wurde eine kombinierte Diagnose gebaut:

- Agentenmodus/Antwort 3 als Basis:
  - Train-vs-Blind Decay
  - Distribution Shift
  - 72h Horizon-/MFE-/MAE-Profil
  - Orderflow-Filter-Overfit
- Antwort 2 ergaenzt:
  - Same-window ETH Attribution / `signal_minus_eth`
- Antwort 1 ergaenzt:
  - Konzentration, Leave-one/two-out PF, Selection-Bias

Dateien:

- `src/research/brh_v1_diagnostics.py`
- `scripts/run_brh_v1_diagnostics.py`
- `tests/test_brh_v1_diagnostics.py`

Regeln:

- rein diagnostisch;
- keine Strategieparameter geaendert;
- keine neue Variante ausgewaehlt;
- kein zweiter Varianten-Blindtest;
- kein UI-/Router-Backtest;
- verwendet den vorhandenen BRH-v1-Report und das vorhandene Validation-
  Trade-Ledger.

Lokaler Run:

- `strategy_version = brh_v1_attribution_decay_diagnostics_20260702`
- `status = diagnostic_complete`
- `selected_variant_id = erv_risk_on_orderflow_cooldown_72h`
- Output:
  `reports/research/brh_v1_diag/brh_v1_diagnostic_report.json`

Kernaussagen:

- Threshold-Verifikation:
  - Blindtest-Quantile passen exakt zur training-only Recalculation.
  - `thresholds_training_only = true`
  - Damit kein stiller Quantile-Lookahead gefunden.
- Distribution Shift:
  - Risk-On-Bars/Tag Blind vs. Training ca. `0.639`.
  - Das ist weniger, aber kein harter <50%-Regimekollaps.
- Horizon Decay:
  - Im Blindtest waren kuerzere Horizonte nicht besser.
  - 72h Mean PnL je Trade ca. `+0.211 USDC`.
  - 24h Mean PnL je Trade ca. `-0.830 USDC`.
  - Deshalb kein klarer Beleg, dass nur die starre 72h-Haltezeit das Problem
    ist.
- Same-window ETH Attribution:
  - `signal_minus_same_window_eth` ist praktisch `0`.
  - Das ist erwartbar: BRH ist fixed Spot-Long im ausgewaehlten Fenster.
  - Ein Edge kann nur aus besserer Auswahl der ETH-Exposure-Fenster kommen,
    nicht aus Alpha innerhalb des Fensters.
- Konzentration / Fragilitaet:
  - Training selected variant:
    - 45 Trades
    - total ca. `+135.41 USDC`
    - Median Trade ca. `+1.95 USDC`
    - Top-2 Trades ca. `36.9%` des Gesamt-PnL
    - Leave-two-out PF ca. `2.86`
  - Blindtest selected variant:
    - 22 Trades
    - total ca. `+4.65 USDC`
    - Median Trade ca. `-0.37 USDC`
    - Top-1 Trade ca. `337%` des Gesamt-PnL
    - Top-2 Trades ca. `572%` des Gesamt-PnL
    - Leave-one-out PF ca. `0.76`
    - Leave-two-out PF ca. `0.53`
- Selection Forensics:
  - BRH-v1 Auswahlregel war `highest_training_profit_factor_then_pnl`.
  - Fold-Winner wechselten zwischen mehreren Varianten.
  - Max pairwise Entry-Jaccard ca. `0.75`, mean ca. `0.146`.

Interpretation:

- BRH-v1 war methodisch sauberer als fruehere Spuren.
- Der leicht positive Blindtest ist aber nicht robust genug.
- Das Hauptproblem ist nicht nachweislich 72h-Horizon-Decay, sondern
  Blindtest-PnL-Konzentration / geringe Stichprobe / Selection-Fragilitaet.
- Aktuelle BRH-v1-Form bleibt archiviert und nicht integrationsfaehig.

Dieser Schritt wurde umgesetzt. Siehe BRH Window Selection Edge Check unten.

## 10. Aktueller Research-Schritt: BRH Window Selection Edge Check

Aus den externen Antworten wurde nicht sofort BRH-v2 gebaut. Stattdessen wurde
zuerst eine engere training-only Frage geprueft:

```text
Hat BRH-v1 im Training/Walkforward bessere ETHUSDC-Exposure-Fenster selektiert
als ein einfacher BTC-Risk-On-Baseline-Hold innerhalb derselben Folds?
```

Dateien:

- `src/research/brh_window_selection_edge.py`
- `scripts/run_brh_window_selection_edge_check.py`
- `tests/test_brh_window_selection_edge.py`

Regeln:

- rein training-only;
- verwendet vorhandenen BRH-v1-Report und Validation-Trade-Ledger;
- verwendet nur Markt-/Fold-Daten vor dem Blindtest;
- kein neuer Blindtest;
- keine neue Varianten-Auswahl fuer UI/Router;
- keine Strategieparameter aendern;
- Baseline ist einfacher BTC-Risk-On 72h Hold innerhalb derselben Validation-
  Folds;
- Entry/Exit bleiben lookahead-sicher: Signal auf geschlossener Row, Entry am
  naechsten Open, Exit nach `hold_hours`.

Lokaler Run:

- `strategy_version = brh_window_selection_edge_check_20260702`
- `status = window_selection_edge_found`
- `passing_variant_count = 3`
- Output:
  `reports/research/brh_window_selection_edge/brh_window_selection_edge_report.json`

Bester training-only Kandidat nach Window-Selection-Edge:

```text
variant_id = erv_risk_on_orderflow_cooldown_72h
selected_window_mean_pnl_usdc ~= +2.521
baseline_all_risk_on_mean_pnl_usdc ~= +1.084
baseline_non_overlap_risk_on_mean_pnl_usdc ~= +2.030
window_selection_edge_after_cost_usdc ~= +1.438
non_overlap_selection_edge_after_cost_usdc ~= +0.491
folds_with_positive_selection_edge = 6
worst_fold_selection_edge_after_cost_usdc ~= +0.147
```

Weitere passing Varianten:

- `erv_risk_on_ethbtc_dip_72h`
  - Edge gegen all-risk-on ca. `+1.393 USDC`
  - positive Edge-Folds: `5`
  - worst Fold ca. `-0.264 USDC`
- `erv_risk_on_any_eth_dip_72h`
  - Edge gegen all-risk-on ca. `+1.425 USDC`
  - positive Edge-Folds: `5`
  - worst Fold ca. `-0.264 USDC`

Interpretation:

- BRH/ERV ist nicht wertlos: die Window-Auswahl hatte im Training messbaren
  Mehrwert gegen naive BTC-Risk-On-Exposure.
- Aber der beste Kandidat ist wieder exakt die alte v1-Auswahl
  `erv_risk_on_orderflow_cooldown_72h`.
- Diese alte v1-Auswahl wurde bereits frozen blindgetestet und war nur schwach
  positiv (`+4.65 USDC`, ca. `+0.013 USDC/Tag`).
- Deshalb darf daraus kein neuer UI-Full-Backtest und kein zweiter Blindtest
  entstehen.

Dieser Schritt wurde umgesetzt. Siehe BRH Selection Edge Robustness v2Check
unten.

## 11. Aktueller Research-Schritt: BRH Selection Edge Robustness v2Check

Nach den externen Antworten wurde nicht direkt eine neue Strategie gebaut,
sondern ein strenger Gatekeeper:

```text
brh_selection_edge_robustness_v2check_20260702
```

Dateien:

- `src/research/brh_selection_edge_robustness_v2check.py`
- `scripts/run_brh_selection_edge_robustness_v2check.py`
- `tests/test_brh_selection_edge_robustness_v2check.py`

Regeln:

- rein training-only;
- verwendet den vorhandenen BRH-v1-Report und das Validation-Trade-Ledger;
- schneidet alle Marktdaten vor `blindtest_start` ab;
- kein neuer Blindtest;
- kein UI-Full-Backtest;
- keine UI-/Router-Integration;
- alte v1-Variante darf als Benchmark teilnehmen, aber nicht erneut als
  Blindtest-Erfolg verwendet werden.

Neue Pruefungen gegenueber dem vorherigen Window-Check:

- deterministic random/unconditional ETH-72h-Baseline;
- ETH Buy-and-Hold-Baseline fuer denselben Validation-Zeitraum;
- Edge nach Entfernung der Top-2-Gewinner;
- Leave-one-out und leave-two-out PF;
- Top-1/Top-2-PnL-Konzentration;
- Mindestanzahl Trades;
- positive Folds;
- worst Fold muss positiv sein;
- PF-Obergrenze als Overfit-Schutz;
- Kostenrobustheit bleibt Pflicht.

Lokaler Run:

- `strategy_version = brh_selection_edge_robustness_v2check_20260702`
- `status = new_training_only_candidate_found`
- `passing_variant_count = 1`
- Output:
  `reports/research/brh_selection_edge_robustness_v2check/brh_selection_edge_robustness_v2check_report.json`

Bester/passing Kandidat:

```text
variant_id = brh_btc_risk_on_72h
already_blindtested_in_v1 = false
trades = 68
validation_pnl ~= +138.06 USDC
validation_usdc_per_day ~= +0.251
profit_factor ~= 2.36
leave_one_out_pf ~= 2.07
leave_two_out_pf ~= 1.89
top1_share ~= 20.9%
top2_share ~= 34.5%
random_baseline_trimmed_edge ~= +1.49 USDC/Fenster
strategy_minus_buy_hold_usdc_per_day ~= +0.240
```

Warum nur diese Variante besteht:

- `brh_btc_risk_on_72h` ist breit genug, nicht bereits blindgetestet und hat
  keine harte Konzentrationsverletzung.
- `erv_risk_on_orderflow_cooldown_72h`, die alte v1-Auswahl, scheitert am
  strengeren Check:
  - `45 < 48` Validation-Trades;
  - worst Fold nicht positiv;
  - PF oberhalb der Overfit-Obergrenze.
- Andere Filtervarianten scheitern vor allem an PF-Overfit-Obergrenze,
  worst Fold, Edge-Folds oder Small-Sample-Problemen.

Interpretation:

- BRH-v1 bleibt archiviert.
- Der neue Check rechtfertigt keinen UI-Full-Backtest.
- Der neue Check rechtfertigt auch keine Router-Integration.
- Er rechtfertigt nur den naechsten kleinen Schritt:
  einen separaten frozen Research-Blindtest-Runner fuer genau
  `brh_btc_risk_on_72h`.

Dieser Schritt wurde umgesetzt. Siehe BRH BTC-Risk-On Frozen Blindtest unten.

## 12. Aktueller Research-Schritt: BRH BTC-Risk-On Frozen Blindtest

Nach dem v2Check wurde genau der freigegebene Kandidat frozen blindgetestet:

```text
brh_btc_risk_on_72h
```

Dateien:

- `src/research/brh_btc_risk_on_frozen_blindtest.py`
- `scripts/run_brh_btc_risk_on_frozen_blindtest.py`
- `tests/test_brh_btc_risk_on_frozen_blindtest.py`

Regeln:

- genau diese Variante;
- keine neue Variantensuche;
- keine Parameteraenderung;
- keine Nutzung des Blindtests zur Auswahl;
- keine UI-/Router-Integration;
- genau ein frozen Research-Blindtest;
- der Runner bricht ab, wenn der v2Check nicht exakt
  `brh_btc_risk_on_72h` als nicht bereits blindgetestete Variante freigegeben
  hat.

Lokaler Run:

- `strategy_version = brh_btc_risk_on_72h_frozen_blindtest_20260702`
- `status = frozen_research_blindtest_completed`
- Output:
  `reports/research/brh_btc_risk_on_frozen_blindtest/brh_btc_risk_on_frozen_blindtest_report.json`

Frozen Blindtest:

```text
candidate_variant_id = brh_btc_risk_on_72h
pnl_usdc ~= +10.62
usdc_per_day ~= +0.0291
trades = 26
profit_factor ~= 1.256
median_trade_net_pnl ~= +0.493 USDC
max_drawdown ~= 18.63 USDC
leave_one_out_pf ~= 1.006
leave_two_out_pf ~= 0.852
top1_share ~= 97.7%
top2_share ~= 157.6%
```

Blindtest Buy-and-Hold-Baseline:

```text
ETH buy-and-hold pnl ~= -35.84 USDC
ETH buy-and-hold ~= -0.098 USDC/Tag
strategy_minus_buy_hold ~= +0.127 USDC/Tag
```

Entscheidung:

```text
positive_blindtest_edge = true
robust_blindtest_edge = false
router_integration_allowed_now = false
ui_full_backtest_allowed_now = false
```

Interpretation:

- Der breite BTC-Risk-On-Kandidat hat den alten BRH-v1-Kandidaten uebertroffen
  und war besser als passives ETH-Halten im Blindtestfenster.
- Trotzdem ist der Effekt sehr weit vom Ziel `3 USDC/Tag` entfernt.
- Die Blindtest-Gewinne sind zu stark auf wenige Trades konzentriert.
- Nach Entfernung der zwei besten Trades faellt der PF unter 1.
- Deshalb nicht integrieren, keinen UI-Full-Backtest starten und nicht auf
  diesen Blindtest nachoptimieren.

Naechster kleinster sinnvoller Schritt:

Dieser Schritt wurde umgesetzt. BRH/ERV ist geschlossen. Siehe EREM unten.

## 13. Aktueller Research-Schritt: EREM Exposure Edge Check

Nach drei externen Antworten wurde als bestes neues Thema EREM gewaehlt:

```text
ETH Regime Exposure Management
```

Das ist bewusst kein BRH/ERV-v3. EREM sucht keinen Alpha-Trade pro Entry,
sondern prueft, ob ETH-Exposure durch Flat-Sein in BTC-Risk-Off-Regimes
drawdown-aermer als passives ETH-Halten gesteuert werden kann.

Dateien:

- `src/research/erem_exposure_edge_check.py`
- `scripts/run_erem_exposure_edge_check.py`
- `tests/test_erem_exposure_edge_check.py`

Regeln:

- rein training-only;
- kein Blindtest im ersten Schritt;
- kein UI-/Router-Backtest;
- BTC-Risk-Off wird nur aus geschlossenen BTC/ETH Feature-Rows bestimmt;
- Exposure-Aenderungen werden erst am naechsten 1h-Open umgesetzt;
- Erfolg wird relativ zu ETH Buy-and-Hold und Drawdown gemessen;
- Ziel ist nicht `3 USDC/Tag`, sondern robuste Drawdown-Vermeidung.

Lokaler Run:

- `strategy_version = erem_exposure_edge_check_20260702`
- `status = erem_training_edge_found`
- `passing_variant_count = 1`
- Output:
  `reports/research/erem_exposure_edge_check/erem_exposure_edge_check_report.json`

Bester/passing Kandidat:

```text
variant_id = erem_btc_drawdown_q35_or_ema_below0
erem_pnl ~= +117.65 USDC
buy_hold_pnl ~= +12.51 USDC
strategy_minus_buy_hold ~= +0.163 USDC/Tag
positive_return_improvement_folds = 5/6
maxdd_improvement_folds = 6/6
time_in_market ~= 40.7%
top1_avoided_block_share ~= 8.4%
top2_avoided_block_share ~= 15.3%
```

Dieser Check erlaubte genau einen frozen EREM-Research-Blindtest.

## 14. Aktueller Research-Schritt: EREM Frozen Blindtest

Nach dem EREM Exposure Edge Check wurde genau der freigegebene Kandidat frozen
blindgetestet:

```text
erem_btc_drawdown_q35_or_ema_below0
```

Dateien:

- `src/research/erem_frozen_blindtest.py`
- `scripts/run_erem_frozen_blindtest.py`
- `tests/test_erem_frozen_blindtest.py`

Regeln:

- genau diese Variante;
- keine neue Variantensuche;
- keine Parameteraenderung;
- keine Nutzung des Blindtests zur Auswahl;
- keine UI-/Router-Integration;
- genau ein frozen Research-Blindtest;
- der Runner bricht ab, wenn der EREM Edge Check keinen Kandidaten freigibt.

Lokaler Run:

- `strategy_version = erem_frozen_blindtest_20260702`
- `status = erem_frozen_blindtest_completed`
- Output:
  `reports/research/erem_frozen_blindtest/erem_frozen_blindtest_report.json`

Frozen Blindtest:

```text
candidate = erem_btc_drawdown_q35_or_ema_below0
erem_pnl ~= -0.53 USDC
buy_hold_pnl ~= -37.00 USDC
strategy_minus_buy_hold ~= +0.100 USDC/Tag
erem_maxdd ~= 58.69 USDC
buy_hold_maxdd ~= 140.05 USDC
time_in_market ~= 34.9%
top1_avoided_block_share ~= 36.2%
top2_avoided_block_share ~= 46.5%
```

Entscheidung:

```text
return_not_worse_than_buy_hold = true
drawdown_better_than_buy_hold = true
top1_avoided_block_concentration_ok = true
return_to_maxdd_ratio_better_than_buy_hold = true
robust_blindtest_edge = true
router_integration_allowed_now = true
ui_full_backtest_allowed_now = false
```

Interpretation:

- BRH/ERV bleibt geschlossen.
- EREM bestaetigt kein `3 USDC/Tag` Profit-Alpha.
- EREM bestaetigt aber robustes Exposure-/Drawdown-Management gegen passives
  ETH-Halten.
- Der Nutzer hat am 2026-07-02 klargestellt: `3 USDC/Tag` war nie ein
  Versprechen, sondern ein Wunsch/Zielwert. Darum wurde EREM als defensives
  Zwischenziel akzeptiert.
- EREM wurde danach minimal in den gemeinsamen `activity_first_router`
  integriert. Der aktuelle UI-Full-Backtest sieht EREM jetzt.

Aktuelle Router-Integration:

- Datei: `src/router/__init__.py`
- Version: `erem_defensive_router_v1_20260702`
- Kandidat: `erem_btc_drawdown_q35_or_ema_below0`
- Familie: `erem_exposure_management`
- Nur Training kalibriert Thresholds.
- Blindtest bleibt eingefroren.
- Keine Variantensuche im Blindtest.
- Keine alten BRH/ERV/VEC/AFP-Gates wurden gelockert.
- Smoke/Full bleiben derselbe Routerpfad.
- Reportfelder:
  - `router_artifact.erem_defensive_router_integration`
  - `rejection_summary.erem_defensive_router_integration`
  - `selected_setups[0].strategy_family = erem_exposure_management`

Naechster kleinster sinnvoller Schritt:

```text
UI-Full-Backtest starten und danach den neuen Reportordner analysieren.
Nicht sofort live/paper uebernehmen. Erwartung: defensive Risiko-/Drawdown-
Verbesserung; 3 USDC/Tag bleibt Wunsch/Zielwert, kein Patch-Versprechen.
```

## 15. Research-Schritt: VEC-v1 Exhaustion Scan

Historisch wurde VEC-v1 gebaut, weil der Nutzer zu diesem Zeitpunkt lieber
`3 USDC/Tag` Profit-Alpha als nur Drawdown-/Exposure-Management wollte.
Diese Spur bleibt wichtig als negativer Befund, wird aber nach der spaeteren
EREM-Akzeptanz nicht gerettet. VEC-v1 war ein getrennter
Microstructure-Alpha-Scan:

```text
VEC-v1 = Volume Climax & Selling Exhaustion Reversion
```

Dateien:

- `src/research/vec_v1_exhaustion_scan.py`
- `scripts/run_vec_v1_exhaustion_scan.py`
- `tests/test_vec_v1_exhaustion_scan.py`

Regeln:

- research-only;
- Training/Walkforward only;
- kein Blindtest;
- keine UI-/Router-Integration;
- Entry erst am naechsten geschlossenen 15m/1h Bar-Open;
- nur ETHUSDC Kline-Orderflow:
  `quote_volume`, `trade_count`, `taker_buy_quote_volume`;
- Features:
  `quote_volume_ratio_20d`, `sell_imbalance`, `bar_return`,
  `close_location`;
- Varianten:
  - `vec_15m_sell_climax_reclaim_4h`
  - `vec_15m_sell_climax_reclaim_8h`
  - `vec_1h_sell_climax_reclaim_8h`
  - `vec_1h_sell_climax_reclaim_12h`

Lokaler Run:

- `strategy_version = vec_v1_exhaustion_scan_20260702`
- `status = no_vec_training_edge`
- Output:
  `reports/research/vec_v1_exhaustion_scan/vec_v1_exhaustion_scan_report.json`

Training/Walkforward-Ergebnis:

```text
passing_variant_count = 0 / 4

vec_15m_sell_climax_reclaim_4h:
  trades = 6
  pnl ~= +2.57 USDC
  usdc_per_day ~= +0.0047
  pf ~= 2.99
  positive_folds = 3
  rejection = min trades, positive folds, leave-two-out PF,
              top2 concentration, worst fold

vec_15m_sell_climax_reclaim_8h:
  trades = 6
  pnl ~= +6.53 USDC
  usdc_per_day ~= +0.0119
  pf ~= 2.11
  median trade < 0
  positive_folds = 2
  rejection = min trades, positive folds, median trade,
              leave-two-out PF, top2 concentration, worst fold

vec_1h_*:
  trades = 2 je Variante
  pnl negativ
```

Entscheidung:

```text
vec_frozen_blindtest_conditionally_allowed = false
ui_full_backtest_allowed_now = false
```

Interpretation:

- VEC-v1 ist nicht robust genug.
- Die positiven 15m-Miniwerte sind zu selten und zu konzentriert.
- Nicht durch Gate-Lockerung retten.
- Kein frozen VEC-Blindtest.
- Kein UI-Full-Backtest.
- Kein Router-Patch.

Naechster kleinster sinnvoller Schritt:

```text
Wenn externe Hilfe genutzt wird: Arena.ai mit
docs/ARENA_AI_REQUEST_AFTER_VEC_V1_20260702.md fragen.

Wenn lokal weitergebaut wird: nur einen neuen, klar getrennten Research-Scan
mit echten aggTrade-Minutenfeatures bauen. Nicht dieselbe VEC-Kline-Idee
weichspuelen.
```

Dieser Schritt wurde umgesetzt. Siehe AFP-v1 unten.

## 16. Aktueller Research-Schritt: AFP-v1 Flow Persistence Scan

Nach den Arena.ai-Antworten wurde bewusst nicht der OFA/VEC-Climax-Pfad als
Hauptlinie gewaehlt. Besser war die AFP-Mischung:

```text
AFP-v1 = Aggregate Flow Persistence Long
```

Grund:

- VEC-v1 scheiterte an extrem seltenen Climax/Reclaim-Konjunktionen.
- AFP-v1 testet die echte noch ungenutzte Datenquelle:
  ETHUSDC aggTrade-Minutenfeatures.
- AFP-v1 hat einen Sanity-Kill-Switch vor jeder Varianten-Simulation.

Dateien:

- `src/research/afp_v1_flow_persistence_scan.py`
- `scripts/run_afp_v1_flow_persistence_scan.py`
- `tests/test_afp_v1_flow_persistence_scan.py`

Regeln:

- research-only;
- Training/Walkforward only;
- kein Blindtest;
- keine UI-/Router-Integration;
- zuerst aggTrade-Daten-Audit;
- dann Sanity-Forward-Return nach 5m Buy-Flow-Persistenz-Quintilen;
- Varianten werden nur simuliert, wenn mindestens 5/6 Sanity-Folds bestehen.

Daten:

- ETHUSDC 1m Klines fuer Execution-OHLC.
- ETHUSDC aggTrade-Minutenfeatures:
  - `agg_trade_count`
  - `raw_trade_count`
  - `taker_buy_quote_volume`
  - `taker_sell_quote_volume`
  - `vwap`
  - `max_agg_trade_quote`

Wichtige technische Klarstellung:

- 47.022 Minuten hatten keine aggTrade-Zeile.
- Alle diese Minuten hatten in den Klines `trade_count == 0`.
- Das sind also echte Null-Trade-Minuten, keine kaputten Archive.
- Sie werden als Null-Flow behandelt, nicht interpoliert.

Lokaler Run:

- `strategy_version = afp_l_v1_flow_persistence_scan_20260702`
- `status = afp_sanity_failed`
- Output:
  `reports/research/afp_v1_flow_persistence_scan/afp_v1_flow_persistence_report.json`

Daten-Audit:

```text
total_minutes = 1,576,800
available_minutes = 1,576,800
completeness_ratio = 1.0
missing_minutes = 0
zero_trade_minutes_without_agg_rows = 47,022
```

Sanity-Ergebnis:

```text
passing_folds = 0 / 6
required_passing_folds = 5
sanity_pass = false
variant_count = 0
passing_variant_count = 0
```

Fold-Befund:

```text
In jedem Fold war das Top-Persistenz-Quintil nach Kosten negativ.
Die Quintile lagen grob um -0.21 bis -0.23 USDC pro 15m Forward-Probe.
Das entspricht im Kern dem Roundtrip-Kostenblock; Buy-Flow-Persistenz
ueberwand die Kosten nicht.
```

Entscheidung:

```text
frozen_blindtest_conditionally_allowed = false
ui_full_backtest_allowed_now = false
```

Interpretation:

- AFP-v1 ist der erste echte aggTrade-Kernscan.
- Der negative Befund ist deshalb wichtiger als VEC:
  nicht nur Kline-Orderflow, sondern echte aggTrade-Flow-Persistenz schafft
  schon den Sanity-Kill-Switch nicht.
- Keine Varianten-Simulation.
- Kein frozen AFP-Blindtest.
- Kein UI-Full-Backtest.
- Kein Router-Patch.
- Nicht durch Gate-Lockerung retten.

Naechster kleinster sinnvoller Schritt:

```text
Wenn externe Hilfe genutzt wird: Arena.ai mit
docs/ARENA_AI_REQUEST_AFTER_AFP_V1_20260702.md fragen.

Wenn lokal weitergearbeitet wird: nicht noch eine Alpha-Variante erzwingen.
Sinnvoller ist eine Kosten-/Machbarkeitsanalyse oder die Entscheidung,
EREM als robustes Exposure-/Drawdown-Zwischenziel zu integrieren/veredeln.
```

## 17. Naechster Auftrag: EREM-UI-Full-Backtest

Aktuell ist ein UI-Full-Backtest wieder sinnvoll, aber nur fuer eine klar
begrenzte Frage:

```text
Hat die neue EREM-defensive Router-Integration im echten 730/365-Backtestpfad
eine bessere Risiko-/Drawdown-Struktur und wenigstens einen plausiblen
positiven/neutralen Blindtest als reines ETH-Exposure?
```

Der naechste menschliche Schritt ist:

```text
UI oeffnen -> Full-Backtest starten -> neuen Reportordner an Codex/GPT geben.
```

Danach pruefen:

- `activity_first_router_report.json`
- `router_artifact.erem_defensive_router_integration`
- `selected_setups`
- `blindtest_total_net_pnl`
- `blindtest_quote_per_day`
- `blindtest_max_drawdown`
- Trade-Anzahl und Tagesverteilung

Wichtig:

- `3 USDC/Tag` bleibt Wunsch/Zielwert, kein Versprechen.
- Keine Uebernahme, wenn der Blindtest negativ/fragil ist.
- Kein Live/Paper.
- Keine Gates lockern, nur um das Ziel zu erzwingen.

Wenn der EREM-Full-Backtest negativ oder methodisch unklar ist, dann externe
Hilfe wieder mit allen aktuellen EREM-Routerdaten fragen. Historische Prompts:

```text
docs/ARENA_AI_REQUEST_AFTER_AFP_V1_20260702.md
docs/ARENA_AI_REQUEST_AFTER_VEC_V1_20260702.md
docs/ARENA_AI_REQUEST_AFTER_BTC_RISK_ON_BLINDTEST_20260702.md
```

Die Antwort darf nicht blind eingebaut werden. Waehle den besseren Vorschlag,
begruende warum, baue ihn minimal research-only, und stoppe wieder, wenn die
Evidenz nicht reicht.

## 18. Uebergabeformat nach jedem Patch

Am Ende immer berichten:

- geaenderte Dateien
- geloeschte Dateien, falls Cleanup
- welcher Ansatz getestet wurde
- Training-/Walkforward-Ergebnis
- ob Blindtest ueberhaupt erlaubt wurde
- ob UI-Backtest gestartet werden soll oder nicht
- ob Tests gruen sind
- naechster kleinster sinnvoller Schritt
