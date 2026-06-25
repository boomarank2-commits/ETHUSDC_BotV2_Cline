# CLEAN_START_20260625_ACTIVITY_FIRST.md

Bitte auf Deutsch arbeiten und streng nach Spezifikation vorgehen.

Arbeitsordner:

C:\TradingBot\ETHUSDC_BotV2_Cline

Erwarteter Branch:

spec/activity-first-rebuild-20260623

## Zuerst lesen

1. docs/FINAL_ONE_YEAR_BLINDTEST_TRUTH.md
2. specs/07_FINAL_ONE_YEAR_BLINDTEST_CONTRACT.md
3. AGENTS.md
4. README.md
5. docs/MASTER_TRUTH.md
6. docs/BACKTEST_TRUTH.md
7. docs/ROUTER_TRUTH.md
8. docs/BACKTEST_ROUTER_CONTRACT.md
9. specs/00_MASTER_GOAL.md
10. specs/01_BACKTEST_CONTRACT.md
11. specs/02_SMOKE_TEST_CONTRACT.md
12. specs/03_STRATEGY_ENGINE_CONTRACT.md
13. specs/04_UI_CONTRACT.md
14. specs/05_REPORTING_CONTRACT.md
15. specs/06_ACCEPTANCE_TESTS.md

## Harte Projektwahrheit

- ETHUSDC
- USDC
- Binance Spot
- LONG-only
- kein Short
- kein Margin
- kein Futures
- kein Leverage
- kein Blindtest-Lernen
- kein Lookahead
- kein V1-Fallback
- keine Fake-Trades
- UI ist Wahrheit
- Smoke und Full sind derselbe Backtest-Apparat
- Smoke unterscheidet sich nur durch Zeitraum / run_type

## Entscheidendes Zielbild

Der eigentliche Zieltest ist der 365-Tage-Blindtest nach 730 Tagen Training.

1 / 7 / 14 / 30 Tage sind nur technische Kurzversionen desselben Vertrags.

Kein Patch darf nur fuer 7 Tage oder 30 Tage gebaut werden. Jeder Patch gilt fuer den einen gemeinsamen Backtest-Apparat.

## Aktuell erkannter Hauptfehler

Der V6-Kandidatenpool darf nicht alle Kandidaten parallel addieren.

Richtig ist:

- Training erzeugt einen Kandidaten-/Regime-Pool.
- Blindtest friert diesen Pool ein.
- Kandidaten erzeugen Vorschlaege.
- Der Router entscheidet im gemeinsamen Zeit-/Kapital-Kontext.
- Ueberlappende Vorschlaege werden auf eine Aktion reduziert.
- no_trade ist erlaubt.

## Naechster technischer Auftrag

Pool-Ausfuehrung korrigieren:

- pool_overlap_guard_used = True
- pool_execution_policy = one_position_at_a_time
- pool_raw_proposals berichten
- pool_executed_trades berichten
- pool_skipped_overlaps berichten

Danach:

python -m compileall src tests
python -m pytest -q

Dann nur 7 / 14 / 30 Tage als technische Smoke-Kontrolle.
Noch kein 365-Tage-Full, bevor die Pool-Ausfuehrung sauber ist.
