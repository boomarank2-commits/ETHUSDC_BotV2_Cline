# AGENTS.md – Arbeitsregeln für AI-Coding-Agents

## Projekt

ETHUSDC_BotV2_Cline.

Lokaler Ethereum-Bot auf Binance Spot. Hauptpaar ist ETHUSDC. Quote- und Kapitalbasis ist USDC. Der Bot ist LONG-only.

## Zuerst lesen

Jeder Agent liest zuerst:

1. `docs/CURRENT_TRUTH_MAP.md`
2. `docs/FINAL_ONE_YEAR_BLINDTEST_TRUTH.md`
3. `specs/07_FINAL_ONE_YEAR_BLINDTEST_CONTRACT.md`
4. `README.md`
5. `AGENTS.md`
6. `docs/DATA_TRUTH.md`
7. `docs/BACKTEST_TRUTH.md`
8. `docs/ROUTER_TRUTH.md`
9. `specs/00_MASTER_GOAL.md`
10. `specs/01_BACKTEST_CONTRACT.md`
11. `specs/02_SMOKE_TEST_CONTRACT.md`
12. `specs/03_STRATEGY_ENGINE_CONTRACT.md`
13. `specs/04_UI_CONTRACT.md`
14. `specs/05_REPORTING_CONTRACT.md`
15. `specs/06_ACCEPTANCE_TESTS.md`
16. `memory-bank/activeContext.md`
17. `memory-bank/NEXT_WORK_STATE.md`
18. `memory-bank/progress.md`

Bei Widerspruch gilt `docs/CURRENT_TRUTH_MAP.md`.

## Harte Regeln

- ETHUSDC.
- USDC.
- Binance Spot.
- LONG-only.
- Kein Short.
- Kein Margin.
- Kein Futures.
- Kein Leverage.
- Kein Blindtest-Lernen.
- Kein Lookahead.
- Kein V1-Fallback.
- Keine Fake-Trades.
- Keine getrennten Backtest-Engines.
- Kein paralleles Addieren von Kandidaten als getrennte Konten.
- Keine Rohdaten in GitHub committen.

## Zielbild

Das Ziel ist ein Ethereum-spezifischer Bot, der mit lokalen historischen und laufend gesammelten Daten arbeitet.

Finale Pruefung:

- 730 Tage Training / Optimierung
- 365 Tage Blindtest
- ein gemeinsamer Kapital-/Zeitkontext
- ein gemeinsamer Router
- Ergebnisberichte mit bester/schlechtester Tag, bester/schlechtester Monat, Drawdown, Trades und positiven/negativen Tagen

Richtung Zielwert: 3 USDC pro Tag oder mehr im 365-Tage-Blindtest. Das ist ein Zielwert, keine Garantie.

Eine Konfiguration darf erst nach gutem Blindtest und bewusster Nutzerentscheidung uebernommen werden. Danach laeuft sie fuer den kommenden Monat. Beim naechsten Monatslauf werden die Daten aktualisiert und erneut 3 Jahre betrachtet: 2 Jahre Training, 1 Jahr Blindtest.

## UI und Backtestpfad

Smoke und Full muessen aus demselben UI-/Controller-Pfad laufen.

Smoke ist nur technische Kurzpruefung. Entscheidungsgrundlage ist der 365-Tage-Blindtest.

Trading-Funktionen wie Paper, Testtrade und Live bleiben gesperrt, bis Backtest, Training, Router, Blindtest, Reports und bewusste Uebernahme korrekt sind.

## Aktueller Stand

Aktiv:

- Pool-Overlap-Guard / one_position_at_a_time.
- Derived Timeframes 5m bis 1d sind lookahead-sicher erzeugt und diagnostisch
  sichtbar. Positive ETH-Training-Kandidaten dürfen zusätzlich einen kleinen
  training-only gelernten, vor Blindtest eingefrorenen HTF-Range-Filterkandidaten
  testen; alle bestehenden Zulassungsgates bleiben aktiv.
- HTF Training Edge Diagnostics schreiben Gewinner-/Verlierer-Trennung in den Router-Report.
- Zentraler Daten-Ensure laeuft vor Smoke und Full.
- ETHUSDC, BTCUSDC, ETHBTC, ETHUSDT, USDCUSDT, Kline-Orderflow-Felder, exchange_info und ETHUSDC aggTrade-Minutenfeatures werden vorbereitet.
- Live Spread/Depth wird lokal gesammelt und ist erst nach mindestens 30 echten Tagen validierter Abdeckung als Backtestquelle bewertbar.

Noch nicht als Handelsentscheidung aktiv:

- ETHUSDT/USDCUSDT-Kontext
- aggTrade-/Orderflow-Features
- Spread/Depth/Orderbuch
- weitere HTF-Metriken oder HTF-Score-Ausweitung außerhalb des kleinen
  eingefrorenen Range-Filterkandidaten

Neue Daten duerfen erst in Gates/Scores, wenn Training-only Analyse zeigt, dass sie Gewinner von Verlierern trennen.

## Arbeitsweise

Vor Codeaenderungen zuerst `docs/CURRENT_TRUTH_MAP.md` lesen.

Keine grossen Daten-/Report-Ordner blind laden oder committen.

Nach jeder Codeaenderung:

- `python -m compileall src tests`
- `python -m pytest -q`
- kurzer Ergebnisbericht
