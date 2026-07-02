# Arena.ai Anfrage nach AFP-v1 Flow Persistence Scan

Bitte analysiere den aktuellen Forschungsstand fuer einen ETHUSDC Spot
LONG-only Bot.

Repository:

```text
https://github.com/boomarank2-commits/ETHUSDC_BotV2_Cline
Branch: spec/activity-first-rebuild-20260623
```

Falls du keinen Live-Zugriff hast, arbeite bitte aus diesem Text.

## Ziel

ETHUSDC Spot LONG-only, 100 USDC Einsatzbasis, 730 Tage Training /
Walkforward, danach 365 Tage Blindtest ohne Lernen. Ziel bleibt mindestens
`3.00 USDC/Tag`, aber nicht durch Blindtest-Lernen, Fake-Trades,
Gate-Lockerung oder getrennte Backtestpfade.

Keine Shorts, keine Futures, keine Margin, kein Leverage.

## Geschlossene Spuren

Nicht wiederholen oder leicht gelockert neu verpacken:

- ERRO / ECMD / EPX / R2: keine robuste Execution.
- ERH-v1: nach Next-Open-Korrektur kein Training-Walkforward-Kandidat.
- BRH/ERV-v1 und BRH BTC-Risk-On: frozen Blindtests nur schwach positiv und
  stark konzentriert.
- EREM: robustes Exposure-/Drawdown-Management, aber kein Profit-Alpha.
- VEC-v1: Volume-Climax/Selling-Exhaustion-Reclaim auf Kline-Orderflow,
  `no_vec_training_edge`, nur 2-6 Trades je Variante.

## Aktuellster Schritt: AFP-v1

Nach VEC-v1 wurde auf deinen/euren Vorschlag hin echte aggTrade-
Minutengranularitaet getestet:

```text
AFP-v1 = Aggregate Flow Persistence Long
strategy_version = afp_l_v1_flow_persistence_scan_20260702
```

Dateien:

```text
src/research/afp_v1_flow_persistence_scan.py
scripts/run_afp_v1_flow_persistence_scan.py
tests/test_afp_v1_flow_persistence_scan.py
```

Verwendete Daten:

- ETHUSDC 1m Klines fuer OHLC/Execution.
- ETHUSDC aggTrade-Minutenfeatures:
  - `agg_trade_count`
  - `raw_trade_count`
  - `taker_buy_quote_volume`
  - `taker_sell_quote_volume`
  - `vwap`
  - `max_agg_trade_quote`

Technische Datenklarstellung:

```text
total_minutes = 1,576,800
available_minutes = 1,576,800
completeness_ratio = 1.0
missing_minutes = 0
zero_trade_minutes_without_agg_rows = 47,022
```

Die 47.022 Minuten ohne aggTrade-Zeile waren Kline-Minuten mit
`trade_count == 0`. Sie wurden als echte Null-Trade-/Null-Flow-Minuten
behandelt, nicht interpoliert.

AFP-v1 Logik:

1. Daten-Audit.
2. Training-only Sanity-Kill-Switch:
   - Teile Walkforward-Validation-Minuten nach `persistence_ofi_5m` in
     Quintile.
   - Berechne 15m Forward-PnL nach Spot-Roundtrip-Kosten.
   - Sanity muss in mindestens 5/6 Folds bestehen:
     Top-Quintil positiv, Top > Bottom, monotone Quintil-Struktur.
3. Varianten werden nur simuliert, wenn Sanity besteht.

Ergebnis:

```text
status = afp_sanity_failed
passing_folds = 0 / 6
required_passing_folds = 5
variant_count = 0
passing_variant_count = 0
frozen_blindtest_conditionally_allowed = false
ui_full_backtest_allowed_now = false
```

Fold-Details:

```text
Fold 1 quintile means ca. -0.218, -0.218, -0.216, -0.215, -0.216 USDC
Fold 2 quintile means ca. -0.218, -0.219, -0.216, -0.222, -0.223 USDC
Fold 3 quintile means ca. -0.219, -0.222, -0.217, -0.216, -0.232 USDC
Fold 4 quintile means ca. -0.215, -0.214, -0.218, -0.227, -0.227 USDC
Fold 5 quintile means ca. -0.230, -0.219, -0.221, -0.219, -0.225 USDC
Fold 6 quintile means ca. -0.210, -0.223, -0.221, -0.221, -0.221 USDC
```

Interpretation von Codex:

- Die echte aggTrade-Kernspur wurde erstmals getestet.
- Buy-Flow-Persistenz auf Minutenebene ueberwindet die ca. 0.22% Roundtrip-
  Kosten nicht.
- Der Befund ist staerker als VEC, weil nicht einmal der Pre-Backtest-
  Sanity-Kill-Switch besteht.
- Keine Varianten-Simulation.
- Kein frozen Blindtest.
- Kein UI-/Router-Patch.
- Nicht durch Gate-Lockerung retten.

## Frage an Arena.ai

Bitte bewerte ehrlich:

1. Ist der AFP-v1-Sanity-Kill-Switch methodisch korrekt?
2. Gibt es einen technischen Denkfehler im Sanity-Test, der das Ergebnis
   faelschlich negativ machen koennte?
3. Falls AFP-v1 plausibel negativ ist: Gibt es noch genau einen klar neuen,
   kleinen Research-Schritt, der nicht nur eine Wiederholung alter Spuren ist?
4. Oder ist jetzt die ehrliche Schlussfolgerung, dass mit ETHUSDC Spot
   LONG-only, 100 USDC, ohne Leverage, bei ca. 0.22% Roundtrip-Kosten kein
   robustes `3 USDC/Tag` Profit-Alpha aus diesen Daten ableitbar ist?
5. Sollte Codex stattdessen EREM als robustes Exposure-/Drawdown-Management
   veredeln und integrieren?

Bitte keine allgemeine Trading-Erklaerung. Bitte gib eine konkrete
Handlungsentscheidung:

```text
A) AFP-Sanity korrigieren, weil ...
B) genau einen neuen Research-Scan bauen, Spezifikation ...
C) Alpha-Suche stoppen und EREM/Exposure-Management veredeln, weil ...
```
