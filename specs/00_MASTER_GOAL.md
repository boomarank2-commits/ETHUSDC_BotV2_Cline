\# 00\_MASTER\_GOAL.md – Master-Zielbild



\## Projekt



ETHUSDC\_BotV2\_Cline



\## Hauptziel



Dieses Projekt baut einen lokalen ETHUSDC Spot LONG-only Trading-Bot mit UI, Smoke-Test, Full-Backtest, Paper-Trading und später bewusst freigegebenem Live-Betrieb.



Der Bot soll nicht blind handeln, sondern datenbasiert prüfen, ob eine Strategie im Training und im Blindtest realistisch funktioniert.



\## Symbol und Markt



\* Handelspaar: ETHUSDC

\* Quote-Währung: USDC

\* Markt: Binance Spot

\* Handelsrichtung: LONG-only

\* Kein Short

\* Kein Margin

\* Kein Futures

\* Kein Leverage



\## Kapital und Einsatz



Standardziel:



\* 100 USDC Einsatz pro Trade

\* Ziel langfristig: Richtung 3 USDC pro Tag im 365-Tage-Blindtest



Wichtig:



3 USDC pro Tag sind ein Zielwert, keine Garantie.



Der Bot muss aber technisch so suchen, dass das Ziel mathematisch überhaupt erreichbar ist.



\## Zielrechnung



365 Tage Blindtest:



\* 3 USDC/Tag = 1095 USDC/Jahr



Daraus folgt:



\* 0 Trades sind kein brauchbarer Zustand.

\* 12 Trades/Jahr sind kein brauchbarer Zustand.

\* 1 Trade pro 14 Tage ist kein brauchbarer Zustand.

\* Der Strategie-Kern muss Kandidaten im Bereich mehrerer Trades pro Tag suchen können.



Orientierung:



\* 1 Trade/Tag = 365 Trades/Jahr

\* 3 Trades/Tag = 1095 Trades/Jahr

\* 6 Trades/Tag = 2190 Trades/Jahr

\* 10 Trades/Tag = 3650 Trades/Jahr



Der Bot soll nicht schlechte Trades erzwingen, aber der Optimizer muss aktiv nach genügend Aktivität suchen.



\## Was bisher funktioniert



Die bestehende Infrastruktur bleibt erhalten:



\* UI startet Runs.

\* Smoke-Test funktioniert.

\* Full-Backtest-Rahmen existiert.

\* Datenqualität wird geprüft.

\* ETHUSDC-, BTCUSDC- und ETHBTC-Daten werden geladen.

\* Training/Blindtest-Split funktioniert.

\* Reports werden geschrieben.

\* Smoke und Full verwenden denselben Backtest-Apparat.

\* Tests laufen grundsätzlich grün.



\## Was bisher gescheitert ist



Der bisherige Cluster-/Opportunity-Router ist als Strategie-Kern gescheitert.



Beobachtungen:



\* Mehrere UI-Smoke-Tests endeten mit 0 Trades.

\* Candidate-Space war wiederholt optimizer\_search\_space\_failed.

\* Best training lag zuletzt nur bei ca. 0.0624 USDC/Tag.

\* Der beste Kandidat war viel zu selten aktiv.

\* Der Suchraum fand keine ausreichend aktiven positiven Kandidaten.



Daraus folgt:



Der alte Cluster-Router soll nicht weiter geflickt werden.



\## Neue Richtung



Der Strategie-Kern wird neu gedacht:



activity\_first\_router



Grundidee:



1\. Erst aktive Entry-Situationen erzeugen.

2\. Zielbereich: ca. 1 bis 10 Trades pro Tag.

3\. Dann nach Fees, TP/SL/Hold, Edge und Stabilität filtern.

4\. Erst danach wird trade\_allowed gesetzt.

5\. Smoke-Test dient zur schnellen technischen Prüfung.

6\. Full-Backtest dient zur ernsthaften 365-Tage-Blindtest-Bewertung.



\## Harte Projektregeln



\* UI ist die Wahrheit.

\* Smoke-Test und Full-Backtest sind derselbe Backtest-Apparat.

\* Smoke unterscheidet sich nur durch Zeitraum und run\_type.

\* Kein separater Smoke-Backtest.

\* Kein separater Smoke-Router.

\* Kein V1-Fallback als versteckte Handelslogik.

\* Kein Blindtest-Lernen.

\* Kein Lookahead.

\* Keine Fake-Trades.

\* Keine echten Orders ohne ausdrückliche Live-Freigabe.

\* Kein Live-Betrieb ohne manuelle Freigabe.

\* Keine schlechten Trades erzwingen.



\## Smoke-Test-Zweck



Smoke-Test ist kein Leistungsnachweis.



Smoke-Test zeigt nur:



\* Wird der gemeinsame Backtest-Apparat korrekt ausgeführt?

\* Werden Kandidaten erzeugt?

\* Gibt es Aktivität?

\* Werden Reports korrekt geschrieben?

\* Wird nicht wieder ein alter 0-Trade-Pfad verwendet?



\## Full-Backtest-Zweck



Full-Backtest ist der echte 365-Tage-Blindtest.



Er entscheidet, ob ein Strategie-Kandidat überhaupt weiter betrachtet werden darf.



\## Paper-Trading-Zweck



Paper-Trading darf erst relevant werden, wenn ein Full-Backtest brauchbare Ergebnisse liefert.



Ziel im Paper-Trading:



\* Prüfen, ob Live-Simulation und Backtest-Logik zusammenpassen.

\* Keine echten Orders.

\* Gleiche Engine wie Backtest, soweit möglich.



\## Live-Zweck



Live darf erst nach ausdrücklicher manueller Freigabe aktiviert werden.



Live ist nicht Teil des aktuellen Neuaufbaus.



\## Nächster technischer Fokus



Nicht weiter den alten Cluster-Router flicken.



Stattdessen:



\* Spezifikation vollständig machen.

\* Akzeptanztests definieren.

\* activity\_first\_router planen.

\* Erst danach Code ändern lassen.





