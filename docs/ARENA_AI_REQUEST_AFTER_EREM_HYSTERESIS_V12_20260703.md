# Arena.ai Anfrage - nach EREM-Hysteresis v1.2 Full-Backtest

Bitte analysiere das Repository:

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
```

## Ziel

Der Bot ist ausschliesslich fuer ETHUSDC Spot Long-only gedacht.

Der Wunsch/Zielwert ist:

```text
100 USDC Einsatz
730 Tage Training / ca. 365 Tage Blindtest
moeglichst Richtung 3 USDC/Tag oder mehr
```

Wichtig: `3 USDC/Tag` ist ein Wunsch/Zielwert, kein Versprechen. Es darf
nichts gefaelscht, ueberoptimiert oder blind im Blindtest gelernt werden.

## Aktueller ehrlicher Stand

Der bisherige Profit-Alpha-Pfad ist nicht gut genug:

- alte Activity-/Impulse-/R2-/BRH-/ERV-/VEC-/AFP-Spuren nicht weiter retten;
- keine Gates lockern;
- keine 08/15-Strategie;
- kein Blindtest-Lernen.

EREM wurde als defensives ETH-Regime-Exposure-Management gebaut:

```text
Idee:
ETH halten, aber bei BTC-Risk-Off flach sein.
```

Basis-EREM v1.1:

```text
Run: run_20260703_100717
Kandidat: erem_btc_drawdown_q35_or_ema_below0
Ergebnis: ca. -9.51 USDC
Gewinn/Tag: ca. -0.026 USDC/Tag
Bewertung: defensiver als Buy-and-Hold, aber absolut negativ.
```

Forensik:

```text
erem_postmortem_cycle_scan_20260703
Full-Cycle EREM: ca. +134.94 USDC
Full-Cycle Buy-and-Hold: ca. -13.72 USDC
Blindtest zero-cost EREM: ca. +12.77 USDC
Blindtest real EREM: ca. -9.51 USDC
Befund: EREM hat Cycle-/Exposure-Wert, aber Switch-Kosten/Churn sind ein
wichtiger Engpass.
```

Daraufhin wurde ein training-only Hysteresis-/Mindesthaltezeit-Scan gebaut:

```text
Datei: src/research/erem_hysteresis_minhold_scan.py
Script: scripts/run_erem_hysteresis_minhold_scan.py
Test: tests/test_erem_hysteresis_minhold_scan.py
Version: erem_hysteresis_minhold_scan_20260703
Status: erem_hysteresis_training_candidate_found
Passing Varianten: 1 / 16
Kandidat: erem_minhold_exp48_flat12
Regel: mindestens 48h exposed bleiben, mindestens 12h flat bleiben
```

Eingefrorener Research-Blindtest:

```text
Datei: src/research/erem_hysteresis_frozen_blindtest.py
Script: scripts/run_erem_hysteresis_frozen_blindtest.py
Test: tests/test_erem_hysteresis_frozen_blindtest.py
Version: erem_hysteresis_frozen_blindtest_20260703
Basis-EREM Blindtest: ca. -9.51 USDC, 200 Switches
Hysteresis-EREM Blindtest: ca. +4.64 USDC, 100 Switches
robust_frozen_edge = true
router_integration_allowed_now = true
```

Danach wurde genau dieser eine feste Overlay minimal in den gemeinsamen
Routerpfad integriert:

```text
Datei: src/router/__init__.py
Version: erem_defensive_router_v1_2_hysteresis_minhold_20260703
Familie: erem_exposure_management
Basis-Variante: erem_btc_drawdown_q35_or_ema_below0
Router-Kandidat: erem_minhold_exp48_flat12
Kein Blindtest-Lernen.
Thresholds nur aus Training.
Smoke/Full/UI bleiben ein gemeinsamer Backtestpfad.
```

Echter UI-Backend-Full-Backtest nach Integration:

```text
Run: run_20260703_122054
Typ: full_backtest
Kandidat: erem_minhold_exp48_flat12
Ergebnis: ca. +4.64 USDC
Gewinn/Tag: ca. +0.0127 USDC/Tag
Trades: 50
Final Capital: ca. 104.64 USDC
Zielstatus: target_not_reached
```

Bewertung:

```text
Der Patch hat den echten UI-Full-Backtest von negativ (-9.51 USDC) auf positiv
(+4.64 USDC) gedreht.
Das ist ein echter Fortschritt.
Es ist aber weiterhin weit weg von 3 USDC/Tag und nicht uebernahmefaehig.
```

## Datenlage

Der Bot nutzt lokal:

- ETHUSDC 1m Klines mit vollstaendigen Binance-Kline-Feldern:
  Open, High, Low, Close, Volume, Quote Volume, Trade Count,
  Taker-Buy Base/Quote usw.
- BTCUSDC 1m Kontextmarkt.
- ETHBTC 1m Kontextmarkt.
- ETHUSDT 1m Kontextmarkt.
- USDCUSDT 1m Kontextmarkt.
- ETHUSDC aggTrade-Minutenfeatures.
- Abgeleitete geschlossene ETHUSDC Timeframes: 5m, 15m, 30m, 1h, 4h, 1d.
- Binance `exchange_info` fuer Spot-Filter.
- Live BookTicker/Depth wird gesammelt, ist aber noch nicht backtestfaehig,
  weil keine ausreichend lange saubere historische Sammlung vorhanden ist.

## Bitte analysieren

Bitte nicht versuchen, EREM weiter auf denselben Blindtest zu optimieren.
Der Blindtest ist jetzt durch v1.1 und v1.2 bereits stark verbraucht.

Gesucht ist ein konkreter naechster kleiner Research-Schritt fuer echte
Profit-Alpha, nicht nur defensives Exposure-Management.

Bitte beantworte:

1. Ist EREM-Hysteresis v1.2 als defensive Baseline sinnvoll stehen zu lassen?
2. Welche neue, klar getrennte ETHUSDC-Profit-Alpha-Hypothese ist aus den
   vorhandenen Daten am sinnvollsten?
3. Welche Daten sollte diese Hypothese konkret nutzen?
4. Wie soll Codex sie training-only/walkforward testen?
5. Welche harten Kill-Switches verhindern Overfitting?
6. Welche Mindestanforderungen muessen erfuellt sein, bevor ein frozen
   Blindtest erlaubt ist?
7. Welche Mindestanforderungen muessen erfuellt sein, bevor Router/UI-Full
   erlaubt ist?

Regeln:

- Kein Blindtest-Lernen.
- Keine Gate-Lockerung fuer 3 USDC/Tag.
- Kein Short/Futures/Margin/Leverage.
- Kein Live/Paper/echte Orders.
- Keine separate Smoke-Engine.
- Kein Nachbauen einer 08/15-Internetstrategie.
- Erst Research-only, dann frozen Blindtest, dann maximal minimaler
  Router-Patch.

Bitte liefere am Ende eine konkrete Codex-Umsetzungsanweisung als Text.
