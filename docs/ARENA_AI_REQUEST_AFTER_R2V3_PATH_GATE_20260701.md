# Arena.ai Anfrage nach R2-v3 Path-Gate-Fehlschlag

Stand: 2026-07-01

Bitte antworte nicht mit einem weiteren TP/SL-Tuning fuer R2. R2 wurde jetzt
methodisch sauber geprueft und soll nur weiterverfolgt werden, wenn du eine
wirklich neue, begruendete Signal-Family siehst. Ansonsten bitte einen
Zeitskalen-Pivot vorschlagen.

## Projekt

ETHUSDC Spot Long-only Bot auf Binance.

Ziel:

- 730 Tage Training / Walkforward.
- 365 Tage Blindtest.
- Kein Blindtest-Lernen.
- Kein Lookahead.
- Kein Short, Margin, Futures, Leverage.
- 100 USDC Einsatz pro Trade.
- Ziel langfristig Richtung 3 USDC/Tag, aber nie durch Gate-Lockerung oder
  Fake-Trades.

## Lokale Daten

Vorhanden:

- ETHUSDC 1m OHLCV plus vollstaendige Binance-Kline-Felder:
  quote volume, trade count, taker-buy base, taker-buy quote.
- BTCUSDC 1m mit denselben Kline-Feldern.
- ETHBTC 1m mit denselben Kline-Feldern.
- ETHUSDT 1m mit denselben Kline-Feldern.
- USDCUSDT 1m mit denselben Kline-Feldern.
- ETHUSDC aggTrade-Minutenfeatures:
  agg trade count, raw trade count, quote volume, taker buy/sell imbalance,
  taker buy share, max agg trade quote, vwap.
- Binance exchange_info Filter.
- ETHUSDC derived HTF 5m/15m/30m/1h/4h/1d.

Nicht verwenden:

- Orderbook/BookTicker/Depth fuer historischen Backtest, solange keine
  validierte 30+ Tage Historie existiert.
- On-chain/Futures/Options/Makro ohne lokale zeitstempelsichere Historie.

## Bisherige Befunde

### ECMD-L

Cross-market dislocation, flush/absorption, leadership reload.

Ergebnis:

- Kein robustes Training-Walkforward-Template.
- Bester Training-Execution-Kandidat ca. negativ.
- Nicht integrieren.

### EPX-L R1

Participation/rotation breakout.

Ergebnis:

- Viele Signale.
- Zu wenig Forward-MFE.
- Nur ca. 10-14% Tradeability statt benoetigter 30%.
- Nicht integrieren.

### EPX-L R2-v2

BTC-Lift -> ETH-Catch-Up.

R2-v2 fand zuerst scheinbar gute Forward-MFE:

- Beste Variante:
  - ca. 31 Validation-Signale
  - ca. 35.48% altes MFE/MAE-tradeable
  - ca. 8.67x Lift vs Baseline
  - 6 qualifying folds
- Zweite Variante:
  - ca. 26 Validation-Signale
  - ca. 34.62% altes MFE/MAE-tradeable
  - ca. 8.46x Lift
  - 4 qualifying folds

Aber Phase-2-Execution mit realistischen Kosten war negativ:

- 8 Exit-Surfaces getestet.
- `status = no_execution_candidate`
- 0 Kandidaten eligible fuer Blindtest.
- Rohprobe ohne alte Kontext-Exits, nur TP/SL/Hold, war ebenfalls negativ.

### EPX-L R2-v3 Path-Gate

Danach wurde die vermutete Ursache getestet:

Altes MFE/MAE-Gate misst nur, ob MFE irgendwann existiert, aber nicht ob Target
vor Stop erreichbar ist.

Neues R2-v3 First-Touch-Gate:

- Entry: next 1m open nach Signal.
- Target-Probe: 0.60%.
- Stop-Probe: 0.40%.
- Horizon: 10 Minuten.
- Stop vor Target, wenn beide in derselben Kerze beruehrbar sind.
- Path-tradeable nur wenn:
  - Target first,
  - Drawdown vor Target <= 0.30%,
  - Target innerhalb 7 Minuten.

Ergebnis:

- `strategy_version = epx_l_r2v3_path_gate_20260701`
- `status = no_path_gate_candidate`
- 2 eingefrorene R2-v2 Varianten getestet.
- 0 Varianten eligible fuer Execution.
- Blindtest-Kandidaten: 0.

Bester Befund:

- Validation-Signale: 26
- Path-tradeable: 6
- Path-tradeable Rate: ca. 23.08%
- Baseline Path-tradeable Rate: ca. 2.47%
- Lift: ca. 9.33x
- Target-before-stop Ratio: ca. 42.11%
- Qualifying Folds: 2

Zweiter Befund:

- Validation-Signale: 31
- Path-tradeable Rate: ca. 22.58%
- Target-before-stop Ratio: ca. 47.83%
- Qualifying Folds: 3

Interpretation:

R2 findet zwar Situationen, die relativ zur Baseline besser sind, aber nicht
genug absolut handelbare Situationen. Target kommt zu oft nicht vor Stop,
Signalzahl und Fold-Abdeckung sind zu klein. R2 als kurzfristiges
8-15-Minuten-Catch-Up-Muster ist unter aktuellem Kostenmodell nicht
integrationsreif.

## Was Arena.ai jetzt bitte liefern soll

Bitte liefere entweder:

1. Eine fundamental neue ETH-spezifische Signal-Family, die nicht wieder nur
   kurzfristiger Catch-Up/Snapback/Flush ist,

oder

2. Einen Zeitskalen-Pivot auf 1-4h ETH-Regime-Following mit konkreten
   Features, Entry, Exit, Validierung und Abbruchkriterien.

Wichtig:

- Kein weiteres R2 TP/SL-Tuning.
- Kein allgemeines RSI/EMA/Momentum-Rezept.
- Keine Strategie aus dem Internet.
- Bitte erklaere, warum die neue Idee ueber die Kosten kommt.
- Bitte direkt so formulieren, dass Codex sie research-only implementieren
  kann.

## Gewuenschter Output

Bitte liefere:

1. Name der neuen Hypothese.
2. Warum sie anders ist als ECMD/EPX-R1/R2.
3. Welche vorhandenen Rohdaten verwendet werden.
4. Konkrete Features.
5. Setup-Regeln.
6. Trigger-Regeln.
7. No-Trade-Regeln.
8. Exit-/Hold-Logik.
9. Kleine Parameter-Startmenge, maximal 5-15 Varianten.
10. Training/Walkforward-Validierungsplan.
11. Blindtest-Regeln.
12. Abbruchkriterien.
13. Reportfelder, die Codex schreiben muss.

Bitte sei ehrlich: Wenn du meinst, dass 8-15m Spot-Long-only mit ca. 0.22%
Roundtrip-Kosten strukturell zu schwer ist, sag das klar und gib den besten
Zeitskalen-Pivot an.
