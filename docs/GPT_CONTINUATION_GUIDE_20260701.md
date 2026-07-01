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

Stand nach lokalem ERH-v1-Run:

- `strategy_version = erh_v1_htf_regime_research_20260701`
- `status = no_training_walkforward_candidate`
- 8 Varianten getestet
- 0 Varianten eligible
- 0 Blindtest-Kandidaten ausgewertet
- Training-Regime-Diagnose:
  - 4h-Trainingsbars: 4380
  - aktive Score>=3-Regimebars: 334
  - Score-Verteilung: 0=762, 1=1566, 2=1116, 3=494, 4=324, 5=118
- Beste grobe Variante nach Verlust war `erh_score3_arm30_give30`, aber:
  - 149 Validation-Trades
  - ca. `-32.41 USDC`
  - Profit Factor ca. `0.72`
  - positive Folds: `1/6`
  - robust/slippage/fold/monotonicity checks fehlgeschlagen

Konsequenz:

- kein UI-Full-Backtest fuer ERH-v1;
- kein Blindtest, weil Training/Walkforward nicht bestanden wurde;
- kein blindes Lockern von Score, Orderflow, Trail oder Stop.

Wenn Arena.ai erneut gefragt wird, aktuellen Prompt verwenden:

```text
docs/ARENA_AI_REQUEST_AFTER_ERH_V1_20260701.md
```

## 7. Arena.ai Auftrag

Wenn externe Hilfe genutzt wird, verwende als aktuellen Prompt:

```text
docs/ARENA_AI_REQUEST_AFTER_R2V3_PATH_GATE_20260701.md
```

Die Antwort darf nicht blind eingebaut werden. Waehle den besseren Vorschlag,
begruende warum, baue ihn minimal research-only, und stoppe wieder, wenn die
Evidenz nicht reicht.

## 8. Uebergabeformat nach jedem Patch

Am Ende immer berichten:

- geaenderte Dateien
- geloeschte Dateien, falls Cleanup
- welcher Ansatz getestet wurde
- Training-/Walkforward-Ergebnis
- ob Blindtest ueberhaupt erlaubt wurde
- ob UI-Backtest gestartet werden soll oder nicht
- ob Tests gruen sind
- naechster kleinster sinnvoller Schritt
