# CLEAN_LOOP_WORKFLOW_20260625.md

## Zweck

Diese Datei definiert den Arbeitsmodus ab dem 25.06.2026.

Clean/Cline soll nicht eigenständig großflächig suchen, umbauen oder experimentieren.

Clean ist in diesem Projekt primär Umsetzer.

Die Analyse, Fehlerlokalisierung und Aufgabenzerlegung erfolgt schrittweise über die gemeinsame Loop:

Andreas + ChatGPT + Clean + GitHub.

## Rollen

### Andreas

- startet Clean lokal
- gibt Aufträge an Clean weiter
- führt Commands aus
- entscheidet bewusst über größere Schritte
- kopiert Ergebnisse zurück in ChatGPT

### ChatGPT

- analysiert Spezifikation, Reports, GitHub/Dateien und Clean-Ausgaben
- lokalisiert Fehler
- zerlegt Aufgaben in kleine Schritte
- formuliert konkrete Clean-Aufträge
- prüft Clean-Ergebnisse
- entscheidet mit Andreas über den nächsten Loop-Schritt

### Clean

- liest Spezifikation
- setzt kleine, klar begrenzte Aufgaben um
- verändert nur notwendige Dateien
- führt Tests aus
- berichtet knapp und vollständig
- stoppt nach dem definierten Auftrag

### GitHub

- ist die Verlaufskontrolle
- enthält Branches, Commits, Spezifikationen und Starter-Dateien
- jeder sinnvolle Fortschritt wird committed und gepusht

## Wichtigste aktuelle Wahrheit

Der 365-Tage-Blindtest nach 730 Tagen Training ist das Ziel.

1 / 7 / 14 / 30 Tage sind nur technische Kurzversionen desselben Backtests.

Jeder Patch muss den gemeinsamen Backtest-Apparat verbessern, nicht einen einzelnen Smoke-Zeitraum.

## Aktueller Loop-Fokus

Der erkannte Hauptfehler ist Pool-Ausfuehrung ohne gemeinsamen Kapital-/Zeitkontext.

Naechster Patch:

- Kandidatenpool beibehalten
- Kandidaten liefern Vorschlaege
- ueberlappende Vorschlaege auf eine Aktion reduzieren
- Reportfelder fuer Vorschlaege / ausgefuehrte Aktionen / uebersprungene Overlaps schreiben

## Verboten

Clean darf nicht:

- Smoke und Full trennen
- separate Smoke-Engine bauen
- nur 7 Tage oder nur 30 Tage spezialpatchen
- Kandidaten parallel addieren, als haette jeder eigenes Kapital
- V1-Fallback wieder aktivieren
- echte Ausfuehrung einbauen
- Short/Margin/Futures/Leverage einbauen
- Blindtest-Lernen einbauen
- Lookahead einbauen
- Fake-Trades erzeugen
- fertig melden, nur weil Unit-Tests grün sind

## Pflicht vor jedem Clean-Loop

Clean muss lesen:

- docs/FINAL_ONE_YEAR_BLINDTEST_TRUTH.md
- specs/07_FINAL_ONE_YEAR_BLINDTEST_CONTRACT.md
- AGENTS.md
- specs/00_MASTER_GOAL.md
- specs/01_BACKTEST_CONTRACT.md
- specs/02_SMOKE_TEST_CONTRACT.md
- specs/03_STRATEGY_ENGINE_CONTRACT.md
- specs/04_UI_CONTRACT.md
- specs/05_REPORTING_CONTRACT.md
- specs/06_ACCEPTANCE_TESTS.md
- CLEAN_START_20260625_ACTIVITY_FIRST.md
- CLEAN_LOOP_WORKFLOW_20260625.md
