# Arena.ai Anfrage nach echtem EREM UI-Full-Backtest - 2026-07-03

Bitte analysiere dieses GitHub-Repository:

https://github.com/boomarank2-commits/ETHUSDC_BotV2_Cline

Branch:

```text
spec/activity-first-rebuild-20260623
```

Bitte zuerst lesen:

- `README.md`
- `AGENTS.md`
- `docs/GPT_CONTINUATION_GUIDE_20260701.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `src/router/__init__.py`
- `src/research/erem_exposure_edge_check.py`
- `src/research/erem_frozen_blindtest.py`

## Projektziel

ETHUSDC Spot LONG-only auf Binance.

Der Bot soll aus den letzten ca. 3 Jahren Daten arbeiten:

- ca. 730 Tage Training / Auswahl / Kalibrierung
- danach ca. 365 Tage Blindtest ohne Lernen
- 100 USDC Einsatzbasis
- Ziel/Wunsch: Richtung `3 USDC/Tag`, aber kein Versprechen

Wichtig:

- kein Blindtest-Lernen
- keine Fake-Trades
- keine Gate-Lockerung nur für schöne Zahlen
- kein Short, Margin, Futures oder Leverage
- keine getrennte Backtest-Engine
- UI Full und Smoke müssen derselbe technische Pfad bleiben
- kein Live/Paper, keine echten Orders

## Aktuelle lokale Rohdaten

Der Bot lädt/aktualisiert vor Backtests lokal u.a.:

- `data/candles/ETHUSDC_1m.csv`
- `data/candles/BTCUSDC_1m.csv`
- `data/candles/ETHBTC_1m.csv`
- `data/candles/ETHUSDT_1m.csv`
- `data/candles/USDCUSDT_1m.csv`
- ETHUSDC vollständige 1m-Kline-Felder:
  - open/high/low/close
  - volume
  - quote volume
  - trade count
  - taker buy base volume
  - taker buy quote volume
- ETHUSDC aggTrade-Minutenfeatures:
  - `agg_trade_count`
  - `raw_trade_count`
  - `taker_buy_quote_volume`
  - `taker_sell_quote_volume`
  - `vwap`
  - `max_agg_trade_quote`
- abgeleitete ETHUSDC Timeframes:
  - 5m
  - 15m
  - 30m
  - 1h
  - 4h
  - 1d
- Binance `exchange_info`
- Spread/Depth/BookTicker werden gesammelt, aber nicht als historisches
  Backtestfeature verwendet, solange keine belastbare 30-Tage-Sammlung
  vorliegt.

## Aktueller Stand

Viele alte Spuren sind geschlossen oder negativ:

- Attempt 053 nicht sauber reproduziert
- ERRO/ECMD/EPX/R2 nicht übernahmefähig
- ERH-v1 nach Next-Open-Fix negativ
- BRH/ERV-v1 nur schwach positiv und fragil
- BRH BTC-Risk-On Frozen Blindtest positiv, aber nicht robust genug
- VEC-v1 Exhaustion Scan: `no_vec_training_edge`
- AFP-v1 Flow Persistence Scan: `afp_sanity_failed`

Dann wurde EREM gebaut:

```text
EREM = ETH Regime Exposure Management
```

Idee:

- nicht jeder Entry soll Profit-Alpha sein
- stattdessen ETH-Exposure reduzieren, wenn BTC-Risk-Off erkannt wird
- Ziel: Drawdown/Exposure gegen ETH Buy-and-Hold verbessern

EREM wurde zuerst research-only getestet und danach minimal in den echten
`activity_first_router` integriert.

Router-Version:

```text
erem_defensive_router_v1_1_hourly_aligned_20260702
```

Kandidat:

```text
erem_btc_drawdown_q35_or_ema_below0
```

## Wichtiger technischer Fix

Der erste UI-Full-Run nach Integration war `run_20260702_201035`.
Dieser Run war kein echter EREM-Test, weil EREM blockierte:

```text
erem_execution_context_does_not_cover_split
```

Ursache:

- UI-Split war minuten-genau (`20:04` bis `20:03`)
- EREM arbeitet auf geschlossenen 1h-Execution-Bars
- die Abdeckungskontrolle war zu streng

Fix:

- EREM aligniert Training/Blindtest jetzt auf vorhandene geschlossene 1h-Bars
  innerhalb des UI-Splits
- maximal 2 Stunden Randtoleranz
- echte veraltete Daten blockieren weiterhin

## Echter EREM UI-Full-Backtest

Danach wurde ein neuer UI-Full-Backtest gestartet:

```text
Run-ID: run_20260703_100717
Typ: full_backtest
Status: completed
Training: 2023-07-03T20:04:00Z bis 2025-07-02T20:03:00Z
Blindtest: 2025-07-02T20:04:00Z bis 2026-07-02T20:03:00Z
Blindtest-Dauer: 365 Tage
```

UI-Ergebnis:

```text
BACKTEST-ENTSCHEIDUNG:
NICHT ÜBERNEHMEN: Kein positiver Blindtest-Vorteil sichtbar.

Strategie/Familie:
erem_exposure_management

Kandidat:
erem_btc_drawdown_q35_or_ema_below0

Gesamt-PnL:
-9.51 USDC

Gewinn/Tag:
-0.03 USDC / genauer ca. -0.026 USDC/Tag

Trades/Exposure-Segmente:
100

Start/Ende:
100.00 -> 90.49 USDC
```

EREM-interne Vergleichsmetriken:

```text
EREM PnL: ca. -9.51 USDC
ETH Buy-and-Hold PnL: ca. -34.88 USDC
relativer Vorteil: ca. +0.0695 USDC/Tag
EREM MaxDD: ca. 50.68 USDC
Buy-and-Hold MaxDD: ca. 130.76 USDC
Time in market: ca. 32.9%
Switch count: 200
```

Interpretation:

- EREM funktioniert jetzt technisch im echten UI/Full-Pfad.
- EREM ist defensiver als Buy-and-Hold.
- EREM ist absolut negativ.
- EREM ist nicht übernahmefähig.
- EREM darf nicht per Gate-Tuning schönoptimiert werden.

## Frage an Arena.ai

Bitte analysiere, wie Codex als nächsten kleinen Schritt sinnvoll weitergehen
soll.

Gesucht ist kein weiterer EREM-Gate-Tuning-Patch, sondern ein neuer oder
verbesserter research-only Ansatz für echten ETHUSDC Profit-Alpha.

Bitte konkret beantworten:

1. Ist die bisherige Schlussfolgerung korrekt, dass EREM nur defensives
   Exposure-/Drawdown-Management liefert, aber kein übernahmefähiges
   Profit-Alpha?
2. Gibt es im aktuellen Code/Research-Design einen echten methodischen Fehler,
   der EREM oder die anderen Spuren unnötig schlecht macht?
3. Welcher nächste kleine research-only Scan wäre am sinnvollsten mit den
   vorhandenen Daten?
4. Welche Features sollten dabei wirklich benutzt werden?
5. Welche Sanity-Kill-Switches sollen vor jedem Blindtest gelten?
6. Wie sollte Codex vermeiden, wieder dieselben alten Momentum/Reversion-
   Ideen nur mit anderen Namen zu bauen?
7. Gibt es eine realistische Alternative zu `100 USDC` Spot-long-only, die
   trotzdem ohne Short/Margin/Futures/Leverage bleibt?

Bitte keine 08/15-Strategie vorschlagen.
Bitte keine Empfehlung, Gates zu lockern.
Bitte kein Blindtest-Lernen.
Bitte keinen separaten Backtestpfad.

Gewünscht ist eine konkrete, kleine Spezifikation, die Codex danach sauber als
neuen research-only Schritt bauen kann.
