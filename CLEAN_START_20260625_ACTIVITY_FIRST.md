Bitte auf Deutsch arbeiten und streng nach Spezifikation vorgehen.



Arbeitsordner:

C:\\TradingBot\\ETHUSDC\_BotV2\_Cline



Wichtig:

Dies ist ein Spec-Driven-Neuaufbau des Strategie-Kerns.

Nicht den alten Cluster-/Opportunity-Router weiter flicken.



Zuerst lesen:



1\. AGENTS.md

2\. specs/00\_MASTER\_GOAL.md

3\. specs/01\_BACKTEST\_CONTRACT.md

4\. specs/02\_SMOKE\_TEST\_CONTRACT.md

5\. specs/03\_STRATEGY\_ENGINE\_CONTRACT.md

6\. specs/04\_UI\_CONTRACT.md

7\. specs/05\_REPORTING\_CONTRACT.md

8\. specs/06\_ACCEPTANCE\_TESTS.md



Danach kurz prüfen:



\* git status

\* aktueller Branch

\* ob working tree clean ist



Erwarteter Branch:

spec/activity-first-rebuild-20260623



Harte Projektwahrheit:



\* ETHUSDC

\* USDC

\* Binance Spot

\* LONG-only

\* kein Short

\* kein Margin

\* kein Futures

\* kein Leverage

\* keine echten Orders

\* kein Blindtest-Lernen

\* kein Lookahead

\* kein V1-Fallback

\* keine Fake-Trades

\* UI ist Wahrheit

\* Smoke und Full sind derselbe Backtest-Apparat

\* Smoke unterscheidet sich nur durch Zeitraum/run\_type



Aktueller technischer Stand:



Die Infrastruktur bleibt erhalten:



\* UI

\* Datenloader

\* Datenqualität

\* Smoke-Test

\* Full-Backtest-Rahmen

\* Training/Blindtest-Split

\* Reports

\* Tests



Der alte Strategie-Kern gilt als gescheitert:



\* Cluster-/Opportunity-Router findet keine ausreichend aktiven positiven Kandidaten.

\* Mehrere UI-Smoke-Tests endeten mit 0 Trades.

\* Best training lag zuletzt nur bei ca. 0.0624 USDC/Tag.

\* Bester Kandidat war viel zu selten aktiv.

\* Deshalb: nicht weiter flicken.



Neue Aufgabe:



Baue den neuen Strategie-Kern:



activity\_first\_router



Grundidee:



1\. Erst aktive Entry-Kandidaten erzeugen.

2\. Zielbereich: ca. 1 bis 10 Trades pro Tag.

3\. Danach nach Fees, TP/SL/Hold, Edge, Drawdown und Stabilität filtern.

4\. Erst danach darf trade\_allowed gesetzt werden.

5\. Smoke-Test zeigt technisch, ob der gemeinsame Backtest-Apparat in die richtige Richtung läuft.

6\. Full-Backtest bewertet später ernsthaft 365 Tage Blindtest.



Bitte nicht sofort wild programmieren.



Arbeitsauftrag Phase 1:



1\. Lies die Spezifikationen.

2\. Erstelle einen kurzen Umsetzungsplan für activity\_first\_router.

3\. Benenne exakt:



&#x20;  \* welche neuen Dateien sinnvoll sind

&#x20;  \* welche bestehenden Dateien angebunden werden müssen

&#x20;  \* welche Dateien nicht mehr geflickt werden sollen

&#x20;  \* welche Tests zuerst gebaut werden

4\. Danach implementiere nur den ersten kleinen Baustein:



&#x20;  \* Grundstruktur activity\_first\_router

&#x20;  \* Entry-Familien als technische Kandidaten-Erzeugung

&#x20;  \* noch kein Live

&#x20;  \* keine echten Orders

&#x20;  \* keine Full-Backtest-Ausführung



Erwartete neue oder angepasste Bereiche:



\* src/router/activity\_first\_router.py oder passender Modulname

\* tests/test\_activity\_first\_router.py

\* ggf. Integration in gemeinsame Backtest-Pipeline

\* keine separate Smoke-Engine



Pflicht für den ersten Baustein:



\* Momentum Entry

\* Pullback Entry

\* Range Breakout Entry

\* Volatility Expansion Entry

\* Mean Reversion Entry

\* Trend Continuation Entry



Jede Entry-Familie muss testbar Kandidaten erzeugen können.



Noch nicht erforderlich im ersten Baustein:



\* perfekter Profit

\* Full-Backtest

\* Paper-Trading

\* Live

\* Strategieübernahme



Tests:



\* python -m compileall src tests

\* python -m pytest -q



Neue Tests:



\* activity\_first\_router erzeugt mehrere Entry-Familien

\* Kandidaten enthalten Aktivitätsklasse

\* Smoke und Full bleiben gemeinsamer Backtest-Apparat

\* kein V1-Fallback

\* kein Blindtest-Lookahead

\* keine separate Smoke-Engine



Memory aktualisieren:



\* memory-bank/NEXT\_WORK\_STATE.md

\* memory-bank/activeContext.md

\* memory-bank/progress.md



Am Ende bitte nur kurz antworten:



1\. Welche Spezifikationsdateien gelesen?

2\. Was ist der Umsetzungsplan?

3\. Welche Dateien wurden geändert?

4\. Wurde activity\_first\_router Grundstruktur erstellt?

5\. Welche Entry-Familien existieren?

6\. Tests grün?

7\. Nächster sinnvoller Schritt?



