# UI_TRUTH

Bei Widerspruch gilt `docs/CURRENT_TRUTH_MAP.md`.

## Aktuelle Phase

Die UI ist fuer Backtest-Steuerung Teil der aktuellen Wahrheit.

Smoke und Full muessen ueber denselben UI-/Controller-Pfad gestartet werden. Der UI-Start fuehrt zuerst den zentralen Daten-Ensure aus und startet danach die gemeinsame Backtest-Pipeline.

## Erlaubt

- Einsatz anzeigen und setzen
- Profil anzeigen und setzen
- Smoke 1/7/14/30 starten
- Full-Backtest starten
- Datenstatus anzeigen
- Laufstatus und Fortschritt anzeigen
- Ergebnisreports anzeigen
- spaeter einen Uebernahme-Kandidaten bewusst anzeigen

Die UI darf keine eigene zweite Backtestlogik besitzen.

## Gesperrt

Bis Backtest, Training, Router, Blindtest, Reports und bewusste Uebernahme korrekt sind, bleiben gesperrt:

- Paper-Modus
- Testtrade
- echte Marktorder
- automatische Strategieuebernahme

## Spaeterer Testtrade

Ein spaeterer Testtrade bedeutet: genau eine passende gelernte Situation abwarten, genau einen kompletten Trade von Entry bis Exit testen, Diagnose sammeln und danach stoppen.

## Monatsworkflow

Nach bewusst uebernommener Konfiguration soll die UI spaeter den Monatszyklus unterstuetzen:

1. Daten aktualisieren.
2. 3 Jahre Fenster bilden.
3. 2 Jahre Training/Optimierung.
4. 1 Jahr Blindtest.
5. Kandidat mit Kennzahlen anzeigen.
6. Nutzer entscheidet bewusst, ob der Kandidat uebernommen wird.
