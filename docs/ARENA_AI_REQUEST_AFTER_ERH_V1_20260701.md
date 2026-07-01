# Arena.ai Anfrage nach ERH-v1 Fehlschlag

Ich arbeite an einem ETHUSDC Binance Spot LONG-only Bot.

Feste Regeln:

- ETHUSDC Spot
- LONG-only
- keine Futures, keine Shorts, kein Margin, kein Leverage
- keine echten Orders
- kein Lookahead
- kein Blindtest-Lernen
- 730 Tage Training / Walkforward
- danach nur bei bestandenem Training ein eingefrorener 365-Tage-Blindtest
- 100 USDC Einsatzbasis
- realistisches Kostenmodell: ca. 0.22% Roundtrip

## Bisheriger Befund

Mehrere kurzfristige 8-15-Minuten-Ansätze sind sauber gescheitert:

- ECMD-L: kein robustes Training/Walkforward-Execution-Template.
- EPX/R1/R2: relative Signale vorhanden, aber Target-before-Stop absolut zu
  niedrig.
- R2-v3 Path-Gate: `no_path_gate_candidate`.

Deshalb wurde Arena.ai nach einem Zeitskalen-Pivot gefragt.

## Umgesetzter Pivot: ERH-v1

ERH-v1 = ETH Regime Hold / ETH Multi-Timeframe Regime Trend Participation.

Codex hat die zweite Arena.ai-Antwort umgesetzt, weil sie einfacher, direkter
und weniger lookahead-riskant als ein Pivot-Low/Anchored-VWAP-Modell war.

Umgesetzt als research-only:

```text
src/research/erh_v1.py
scripts/run_erh_v1_research.py
tests/test_erh_v1_research.py
```

Nicht in UI, nicht in activity_first_router, keine Live-/Paper-Funktion.

## Verwendete Daten

Lokal vorhanden:

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

ERH-v1 verwendet aktuell:

- ETHUSDC 1m -> 1h/4h closed candles
- ETHBTC 1m -> 4h Leadership
- BTCUSDC 1m -> 4h Risk/Crash
- ETHUSDT 1m -> Cross-quote basis
- USDCUSDT 1m -> Peg/Basis
- ETHUSDC Kline-Orderflow -> 4h Taker-Buy/OFI

Noch nicht in ERH-v1 verwendet:

- separate aggTrade-Archive
- live orderbook/bookTicker/depth

Orderbook/Depth duerfen nicht historisch erfunden werden.

## ERH-v1 Kernlogik

Hard gates auf abgeschlossenen 4h-Bars:

```text
G1 ETHUSDC close > EMA20
G2 ETHBTC close > EMA20
G3 ETHBTC 6-bar slope > 0
G4 BTC drawdown from 20d high > -15%
G5 ETHUSDC 4h taker-buy-share 3avg >= 0.505
G6 USDCUSDT peg ok
G7 ETHUSDT/USDC basis ok
```

Score:

```text
S1 ETH 24h ret > 2%
S2 ETHBTC 24h ret > 1%
S3 ETHBTC above EMA20 streak >= 3
S4 ETHUSDC OFI 3sum > 0.03
S5 BTC close > EMA20
```

Varianten:

```text
REGIME_SCORE_MIN: [3, 4]
TRAIL_ARM: [0.03, 0.04]
TRAIL_GIVEBACK: [0.030, 0.045]
=> 8 Varianten
```

Entry auf 1h:

```text
Regime aktiv
AND ETHUSDC 1h close > EMA10
AND (ETHUSDC 1h ret_3 > 0 OR Pullback-Reclaim)
AND no_chase_block false
```

Exits:

```text
hard stop 6%
regime_end
trailing
time_stop after 168h if MFE < 2%
window_end
```

## ERH-v1 Ergebnis

Report:

```text
reports/research/erh_v1/erh_v1_research_report.json
```

Kern:

```text
strategy_version = erh_v1_htf_regime_research_20260701
status = no_training_walkforward_candidate
eligible_variant_count = 0 / 8
blindtest_candidate_count_evaluated = 0
```

Datenfenster:

```text
Training start:   2023-06-26T15:49:00Z
Blindtest start:  2025-06-25T15:49:00Z
Blindtest end:    2026-06-25T15:48:00Z
```

Training-Regime-Diagnose:

```text
4h training bars: 4380
active score>=3 regime bars: 334
regime score distribution:
  0: 762
  1: 1566
  2: 1116
  3: 494
  4: 324
  5: 118
```

Varianten:

```text
erh_score3_arm30_give30:
  trades 149, pnl -32.4091 USDC, PF 0.7197, positive folds 1/6

erh_score3_arm30_give45:
  trades 148, pnl -40.4884 USDC, PF 0.6689, positive folds 1/6

erh_score3_arm40_give30:
  trades 149, pnl -41.8927 USDC, PF 0.6652, positive folds 1/6

erh_score3_arm40_give45:
  trades 148, pnl -43.9152 USDC, PF 0.6506, positive folds 1/6

erh_score4_arm30_give30:
  trades 123, pnl -48.8702 USDC, PF 0.5542, positive folds 0/6

erh_score4_arm30_give45:
  trades 123, pnl -56.1874 USDC, PF 0.5174, positive folds 0/6

erh_score4_arm40_give30:
  trades 123, pnl -58.3538 USDC, PF 0.5101, positive folds 0/6

erh_score4_arm40_give45:
  trades 123, pnl -59.6142 USDC, PF 0.5026, positive folds 0/6
```

Haupt-Rejection-Gründe:

```text
positive_folds_below_4_of_6
profit_factor_below_1_40
avg_win_loss_ratio_below_1_80
median_trade_net_pnl_not_positive
max_drawdown_pct_above_0_20
robust_slippage_profit_factor_below_1_30
regime_score_monotonicity_failed fuer Score>=3 Varianten
```

## Frage an Arena.ai

Bitte nicht einfach Gates lockern.
Bitte nicht R2, ECMD, ERRO oder ERH-v1 unverändert recyceln.
Bitte kein Blindtest-Lernen.

Gesucht ist eine konkrete, neue nächste Hypothese oder eine gezielte Diagnose
des ERH-v1-Fehlschlags.

Bitte beantworte:

1. Ist der ERH-v1-Fehlschlag eher ein Implementierungs-/Designproblem oder ein
   echter Hinweis, dass HTF long-only ETHUSDC mit diesen Daten/Kosten in diesem
   Zeitraum keinen stabilen Edge zeigt?
2. Wenn Designproblem:
   - welche eine Änderung zuerst testen?
   - z. B. weniger Re-Entries pro Regime, Regime-Episode statt Bar-Gate,
     anderer Entry innerhalb Regime, andere Exit-Definition, oder Nutzung der
     separaten aggTrade-Archive?
3. Wenn neuer Ansatz:
   - bitte eine fundamental andere ETH-spezifische Hypothese liefern;
   - mit konkreten Features, Entry, Exit, Walkforward-Kriterien und
     Abbruchkriterien;
   - klein genug, dass Codex sie research-only bauen kann.
4. Wie kann man verhindern, dass weitere Versuche nur Parameter-Tuning auf
   nicht tragfähigen Signalen sind?

Wichtig: Codex soll nach deiner Antwort nur den besten, kleinsten nächsten
Schritt bauen und wieder stoppen, wenn Training/Walkforward nicht reicht.
