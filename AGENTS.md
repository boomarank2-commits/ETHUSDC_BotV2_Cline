\# AGENTS.md – Arbeitsregeln für AI-Coding-Agents



\## Projekt

ETHUSDC\_BotV2\_Cline



\## Ziel

Dieses Projekt baut einen lokalen ETHUSDC Spot LONG-only Trading-Bot mit UI, Smoke-Test, Full-Backtest, Paper-Trading und später bewusst freigegebenem Live-Betrieb.



\## Harte Regeln

\- Symbol: ETHUSDC.

\- Quote-Währung: USDC.

\- Nur Spot LONG.

\- Kein Short.

\- Kein Margin.

\- Kein Futures.

\- Kein Leverage.

\- Keine echten Orders ohne ausdrückliche Live-Freigabe.

\- Kein Blindtest-Lernen.

\- Kein Lookahead.

\- Kein V1-Fallback als versteckte Handelslogik.

\- Keine Fake-Trades.

\- Keine separaten Backtest-Engines.



\## UI ist Wahrheit

Alles, was später relevant ist, muss aus der UI heraus funktionieren.

CLI-/Inline-Tests dürfen nur technische Hilfen sein, aber niemals als Beweis ersetzen, dass der UI-Pfad funktioniert.



\## Ein gemeinsamer Backtest-Apparat

Smoke-Test und Full-Backtest sind derselbe Backtest-Apparat.

Der einzige Unterschied ist der Zeitraum.



Full:

\- 730 Tage Training

\- 365 Tage Blindtest



Smoke:

\- 1 Tag Blindtest = 2 Tage Training

\- 7 Tage Blindtest = 14 Tage Training

\- 14 Tage Blindtest = 28 Tage Training

\- 30 Tage Blindtest = 60 Tage Training



\## Aktueller Stand vor Neuaufbau

Die Infrastruktur funktioniert grundsätzlich:

\- UI startet Runs.

\- Smoke-Test läuft.

\- Datenqualität wird geprüft.

\- Training/Blindtest-Split funktioniert.

\- Reports werden geschrieben.

\- Smoke und Full nutzen denselben Codepfad.



Gescheitert ist der aktuelle Strategie-/Router-Kern:

\- Cluster-/Opportunity-Router findet keine ausreichend aktiven positiven Kandidaten.

\- Mehrere UI-Smoke-Tests endeten mit 0 Trades.

\- Best training lag zuletzt nur bei ca. 0.0624 USDC/Tag.

\- Bester Kandidat war viel zu selten aktiv.



\## Neue Richtung

Der alte Cluster-Router wird nicht weiter geflickt.

Stattdessen soll ein neuer activity\_first\_router spezifiziert und später gebaut werden.



Grundidee:

1\. Erst aktive Entry-Situationen erzeugen.

2\. Zielbereich: ca. 1–10 Trades/Tag.

3\. Dann nach Fees, TP/SL/Hold, Edge und Stabilität filtern.

4\. Danach erst trade\_allowed setzen.

5\. Smoke-Test zeigt schnell, ob der gemeinsame Backtest-Apparat in die richtige Richtung läuft.



\## Arbeitsweise

Vor Codeänderungen immer zuerst specs/ lesen.

Keine großen Daten-/Report-Ordner blind laden.

Keine langen Diagnoseberichte ohne Patch.

Jede Änderung muss Tests haben.

Nach jeder Änderung:

\- compileall

\- pytest

\- kurzer Ergebnisbericht



\## Wichtige Dateien

\- specs/00\_MASTER\_GOAL.md

\- specs/01\_BACKTEST\_CONTRACT.md

\- specs/02\_SMOKE\_TEST\_CONTRACT.md

\- specs/03\_STRATEGY\_ENGINE\_CONTRACT.md

\- specs/04\_UI\_CONTRACT.md

\- specs/05\_REPORTING\_CONTRACT.md

\- specs/06\_ACCEPTANCE\_TESTS.md

