# Arena.ai Anfrage nach VEC-v1 Exhaustion Scan

Bitte analysiere den aktuellen Forschungsstand fuer einen ETHUSDC Spot
LONG-only Bot.

Repository:

```text
https://github.com/boomarank2-commits/ETHUSDC_BotV2_Cline
Branch: spec/activity-first-rebuild-20260623
```

Bitte zuerst lesen:

```text
README.md
AGENTS.md
docs/GPT_CONTINUATION_GUIDE_20260701.md
docs/IMPLEMENTATION_PLAN.md
src/research/vec_v1_exhaustion_scan.py
tests/test_vec_v1_exhaustion_scan.py
```

## Ziel

Der Bot soll ausschliesslich ETHUSDC Spot LONG-only handeln. Keine Shorts,
keine Futures, keine Margin, kein Leverage, keine Fake-Trades.

Zielwert bleibt sehr ambitioniert:

```text
100 USDC Einsatzbasis
730 Tage Training/Walkforward
365 Tage Blindtest ohne Lernen
Ziel: mindestens 3.00 USDC/Tag im Blindtest
```

Dieses Ziel darf nicht durch Blindtest-Lernen, Gate-Lockerung, getrennte
Backtestpfade oder Overfitting erzwungen werden.

## Vorherige geschlossene Spuren

Nicht erneut empfehlen, ausser du findest einen klaren technischen Fehler:

- Attempt 053: nicht sauber reproduzierbar.
- ERRO/ECMD/EPX/R2: keine robuste Execution.
- ERH-v1 HTF-Regime-Hold: nach Next-Open-Korrektur kein
  Training-Walkforward-Kandidat.
- BRH/ERV-v1 BTC-Risk-On ETH 72h Hold: frozen Blindtest nur schwach positiv
  und stark konzentriert.
- BRH BTC-Risk-On Frozen Blindtest:
  ca. `+10.62 USDC`, `+0.029 USDC/Tag`, 26 Trades, aber Leave-two-out PF
  ca. `0.85` und Top-2-Konzentration ca. `157.6%`.
- EREM Exposure Management:
  frozen Blindtest bestaetigte bessere Drawdown-Vermeidung als Buy-and-Hold,
  aber keine Profit-Alpha-Strategie:
  EREM ca. `-0.53 USDC` vs. Buy-and-Hold ca. `-37.00 USDC`.

## VEC-v1 aktueller Befund

VEC-v1 wurde als neuer, getrennt gehaltener Microstructure-Alpha-Scan gebaut:

```text
VEC-v1 = Volume Climax & Selling Exhaustion Reversion
```

Daten:

- ETHUSDC 1m Binance Klines.
- Verwendete Kline-Orderflow-Spalten:
  - `quote_volume`
  - `trade_count`
  - `taker_buy_quote_volume`
- Daraus lookahead-sicher geschlossene 15m/1h Bars.

Feature-Idee:

- extreme `quote_volume_ratio_20d`
- hohe Taker-Sell-Dominanz:
  `sell_imbalance = (taker_sell_quote_volume - taker_buy_quote_volume) / quote_volume`
- negative Bar / Flush:
  `bar_return`
- Reclaim/Absorption:
  `close_location = (close - low) / (high - low)`
- Entry erst am naechsten geschlossenen 15m/1h Bar-Open.
- Fixed Hold 4h/8h/12h je Variante.

Varianten:

```text
vec_15m_sell_climax_reclaim_4h
vec_15m_sell_climax_reclaim_8h
vec_1h_sell_climax_reclaim_8h
vec_1h_sell_climax_reclaim_12h
```

Run:

```text
strategy_version = vec_v1_exhaustion_scan_20260702
status = no_vec_training_edge
passing_variant_count = 0 / 4
```

Detail:

```text
vec_15m_sell_climax_reclaim_4h:
  trades = 6
  pnl ~= +2.57 USDC
  usdc_per_day ~= +0.0047
  pf ~= 2.99
  positive_folds = 3
  rejection:
    validation_trades_below_minimum
    positive_folds_below_minimum
    leave_two_out_profit_factor_below_minimum
    top2_pnl_share_above_limit
    worst_fold_pnl_not_positive

vec_15m_sell_climax_reclaim_8h:
  trades = 6
  pnl ~= +6.53 USDC
  usdc_per_day ~= +0.0119
  pf ~= 2.11
  median_trade_pnl_usdc < 0
  positive_folds = 2
  rejection:
    validation_trades_below_minimum
    positive_folds_below_minimum
    median_trade_pnl_not_positive
    leave_two_out_profit_factor_below_minimum
    top2_pnl_share_above_limit
    worst_fold_pnl_not_positive

vec_1h_sell_climax_reclaim_8h:
  trades = 2
  pnl negativ

vec_1h_sell_climax_reclaim_12h:
  trades = 2
  pnl negativ
```

Aktuelle Codex-Interpretation:

- VEC-v1 ist ehrlich gescheitert.
- Die positiven Miniwerte sind zu selten und zu konzentriert.
- Keine frozen VEC-Blindtest-Freigabe.
- Keine UI-/Router-Integration.
- Nicht durch Gate-Lockerung retten.

## Frage an Arena.ai

Bitte bewerte, was der naechste kleine, methodisch saubere Research-Schritt
sein sollte.

Wichtig:

- Keine Wiederholung von ERRO/ECMD/EPX/R2/ERH/BRH/VEC in leicht geloeckerter
  Form.
- Keine 08/15-Strategie aus dem Internet.
- Kein Blindtest-Lernen.
- Keine Gate-Lockerung, nur damit Trades entstehen.
- Keine Router-/UI-Integration, bevor Training/Walkforward robust genug ist.

Besonders gesucht:

1. Ist VEC-v1 technisch/logisch falsch gebaut, oder ist der negative Befund
   plausibel?
2. Falls VEC-v1 falsch gebaut ist: welcher kleine Code-/Logikfehler sollte
   zuerst geprueft werden?
3. Falls VEC-v1 plausibel negativ ist: welche neue ETH-spezifische
   Microstructure-Hypothese ist als naechstes am sinnvollsten?
4. Soll Codex als naechstes echte aggTrade-Minutenfeatures nutzen, z. B.
   `agg_trade_count`, `raw_trade_count`, taker buy/sell imbalance,
   `max_agg_trade_quote`, VWAP-Abweichung?
5. Wie sollte der naechste Scan so klein gehalten werden, dass er nicht wieder
   in eine Overfit-Schleife laeuft?

Bitte antworte mit einer konkreten, umsetzbaren Spezifikation fuer genau einen
naechsten Research-Scan, den Codex danach bauen kann.
