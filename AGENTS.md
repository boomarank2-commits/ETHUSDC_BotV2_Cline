# AGENTS.md – Arbeitsregeln für AI-Coding-Agents

## Projekt

ETHUSDC_BotV2_Cline

## Vor allem zuerst lesen

Jeder Agent liest zuerst:

1. docs/FINAL_ONE_YEAR_BLINDTEST_TRUTH.md
2. README.md
3. docs/MASTER_TRUTH.md
4. docs/BACKTEST_TRUTH.md
5. docs/ROUTER_TRUTH.md
6. specs/00_MASTER_GOAL.md
7. specs/01_BACKTEST_CONTRACT.md
8. specs/02_SMOKE_TEST_CONTRACT.md
9. specs/03_STRATEGY_ENGINE_CONTRACT.md
10. specs/04_UI_CONTRACT.md
11. specs/05_REPORTING_CONTRACT.md
12. specs/06_ACCEPTANCE_TESTS.md

## Harte Regeln

- Symbol: ETHUSDC.
- Quote-Währung: USDC.
- Binance Spot LONG-only.
- Kein Short.
- Kein Margin.
- Kein Futures.
- Kein Leverage.
- Kein Blindtest-Lernen.
- Kein Lookahead.
- Kein V1-Fallback als versteckte Logik.
- Keine Fake-Trades.
- Keine separaten Backtest-Engines.

## UI ist Wahrheit

Alles, was später relevant ist, muss aus der UI heraus funktionieren.

CLI-/Inline-Tests dürfen nur technische Hilfen sein, aber niemals als Beweis ersetzen, dass der UI-Pfad funktioniert.

## Ein gemeinsamer Backtest-Apparat

Smoke-Test und Full-Backtest sind derselbe Backtest-Apparat.

Der einzige Unterschied ist der Zeitraum.

Full:
- 730 Tage Training
- 365 Tage Blindtest

Smoke:
- 1 Tag Blindtest = 2 Tage Training
- 7 Tage Blindtest = 14 Tage Training
- 14 Tage Blindtest = 28 Tage Training
- 30 Tage Blindtest = 60 Tage Training

Smoke ist nur technische Kurzprüfung. Der eigentliche Entscheidungsmaßstab ist der 365-Tage-Blindtest.

## Ein gemeinsames Konto

Ein Kandidatenpool darf mehrere Kandidaten enthalten.

Aber die Simulation darf Kandidaten nicht parallel addieren, als hätte jeder Kandidat sein eigenes Kapital.

Alle Kandidaten liefern Vorschläge. Der Router entscheidet im gemeinsamen Zeit-/Kapital-Kontext.

Ohne ausdrückliche Kapitalaufteilungsregel gilt: überlappende Vorschläge werden auf eine Aktion reduziert.

## Aktueller Stand vor nächstem Patch

Der aktuelle V6-Pool hat den richtigen Gedanken, aber die Ausführung muss korrigiert werden:
- Pool ja.
- Paralleles Addieren aller Kandidaten nein.
- Nächster Patch: pool_overlap_guard / one_position_at_a_time.

## Arbeitsweise

Vor Codeänderungen immer zuerst specs/ und docs/ lesen.

Keine großen Daten-/Report-Ordner blind laden.

Jede Änderung muss Tests haben.

Nach jeder Änderung:
- compileall
- pytest
- kurzer Ergebnisbericht
