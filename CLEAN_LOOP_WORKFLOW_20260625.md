\# CLEAN\_LOOP\_WORKFLOW\_20260625.md



\## Zweck



Diese Datei definiert den Arbeitsmodus ab dem 25.06.2026.



Clean/Cline soll nicht eigenständig großflächig suchen, umbauen oder experimentieren.



Clean ist in diesem Projekt primär Umsetzer.



Die Analyse, Fehlerlokalisierung und Aufgabenzerlegung erfolgt schrittweise über die gemeinsame Loop:



Andreas + ChatGPT + Clean + GitHub.



\## Rollen



\### Andreas



\* startet Clean lokal

\* gibt Aufträge an Clean weiter

\* führt Commands aus

\* entscheidet bewusst über größere Schritte

\* kopiert Ergebnisse zurück in ChatGPT



\### ChatGPT



\* analysiert Spezifikation, Reports, GitHub/Dateien und Clean-Ausgaben

\* lokalisiert Fehler

\* zerlegt Aufgaben in kleine Schritte

\* formuliert konkrete Clean-Aufträge

\* prüft Clean-Ergebnisse

\* entscheidet mit Andreas über den nächsten Loop-Schritt



\### Clean



\* liest Spezifikation

\* setzt kleine, klar begrenzte Aufgaben um

\* verändert nur notwendige Dateien

\* führt Tests aus

\* berichtet knapp und vollständig

\* stoppt nach dem definierten Auftrag



\### GitHub



\* ist die Verlaufskontrolle

\* enthält Branches, Commits, Spezifikationen und Starter-Dateien

\* jeder sinnvolle Fortschritt wird committed und gepusht



\## Arbeitsweise



Es wird in Loops gearbeitet.



Jeder Loop besteht aus:



1\. Ziel definieren

2\. betroffene Dateien bestimmen

3\. Clean-Auftrag formulieren

4\. Clean setzt nur diesen Auftrag um

5\. Tests ausführen

6\. Ergebnis berichten

7\. ChatGPT prüft Ergebnis

8\. nächster kleiner Loop



\## Verboten



Clean darf nicht:



\* den alten Cluster-/Opportunity-Router weiter flicken

\* große Architekturänderungen ohne Rückfrage machen

\* Smoke und Full trennen

\* separate Smoke-Engine bauen

\* V1-Fallback wieder aktivieren

\* echte Orders einbauen

\* Short/Margin/Futures/Leverage einbauen

\* Blindtest-Lernen einbauen

\* Lookahead einbauen

\* Fake-Trades erzeugen

\* „fertig“ melden, nur weil Unit-Tests grün sind



\## Pflicht vor jedem Clean-Loop



Clean muss lesen:



\* AGENTS.md

\* specs/00\_MASTER\_GOAL.md

\* specs/01\_BACKTEST\_CONTRACT.md

\* specs/02\_SMOKE\_TEST\_CONTRACT.md

\* specs/03\_STRATEGY\_ENGINE\_CONTRACT.md

\* specs/04\_UI\_CONTRACT.md

\* specs/05\_REPORTING\_CONTRACT.md

\* specs/06\_ACCEPTANCE\_TESTS.md

\* CLEAN\_START\_20260625\_ACTIVITY\_FIRST.md

\* CLEAN\_LOOP\_WORKFLOW\_20260625.md



\## Loop 1 am 25.06.2026



Ziel:



Clean soll nicht sofort groß umbauen.



Clean soll zuerst:



1\. Spezifikationen lesen

2\. Repo-Struktur prüfen

3\. alte Router-/Strategie-Dateien identifizieren

4\. gemeinsame Backtest-/UI-Pipeline identifizieren

5\. sinnvolle neue Dateien für activity\_first\_router vorschlagen

6\. Tests vorschlagen

7\. noch keine große Umsetzung starten



Ergebnis von Loop 1:



Clean antwortet mit:



\* gelesene Dateien

\* aktueller Branch

\* working tree status

\* relevante bestehende Dateien

\* welche Dateien legacy sind

\* welche neuen Dateien empfohlen werden

\* minimaler Umsetzungsplan

\* Risiken

\* nächster vorgeschlagener kleiner Schritt



\## Loop 2



Erst nach Prüfung durch ChatGPT und Andreas darf Clean Loop 2 starten.



Loop 2 soll höchstens enthalten:



\* Grundstruktur activity\_first\_router

\* technische Entry-Kandidaten-Erzeugung

\* Tests für Entry-Familien

\* keine Full-Backtest-Ausführung

\* keine Live-Funktion

\* keine Strategieübernahme



\## Testpflicht



Nach Codeänderungen:



python -m compileall src tests

python -m pytest -q



Zusätzlich nur bei ausdrücklicher Freigabe:



UI-naher Smoke-Test



\## Berichtspflicht nach jedem Loop



Clean muss berichten:



1\. Welche Spezifikationsdateien gelesen?

2\. Welche Dateien geändert?

3\. Warum geändert?

4\. Welche Tests ausgeführt?

5\. Tests grün ja/nein?

6\. Wurde UI-naher Smoke ausgeführt ja/nein?

7\. Falls Smoke:



&#x20;  \* Run-ID

&#x20;  \* Trade Count

&#x20;  \* Candidate-Space Status

&#x20;  \* Best training USDC/Tag

&#x20;  \* Zielquote

8\. Nächster sinnvoller Schritt



\## Wichtigste Regel



Clean arbeitet nicht mehr als Suchmaschine.



Clean arbeitet als kontrollierter Umsetzer innerhalb einer klaren Loop.



