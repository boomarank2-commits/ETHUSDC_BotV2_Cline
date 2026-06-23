\# 06\_ACCEPTANCE\_TESTS.md – Akzeptanztests



\## Zweck



Diese Datei definiert verbindlich, welche Tests erfüllt sein müssen, bevor der neue activity\_first\_router als brauchbar gilt.



Akzeptanztests sind die Kontrolllinie gegen erneutes Herumprobieren ohne Fortschritt.



\## Grundsatz



Kein AI-Coding-Agent darf den Bot als „fertig“ melden, nur weil Unit-Tests grün sind.



Ein Ergebnis gilt erst als brauchbar, wenn:



\* die Spezifikation eingehalten wird

\* der UI-nahe Smoke-Test funktioniert

\* Reports vollständig sind

\* der gemeinsame Backtest-Apparat genutzt wird

\* keine alten Fallbacks aktiv sind

\* Kandidaten nachvollziehbar erzeugt und bewertet werden



\## Pflicht vor jeder Codeänderung



Vor jeder Codeänderung muss der Agent lesen:



\* AGENTS.md

\* specs/00\_MASTER\_GOAL.md

\* specs/01\_BACKTEST\_CONTRACT.md

\* specs/02\_SMOKE\_TEST\_CONTRACT.md

\* specs/03\_STRATEGY\_ENGINE\_CONTRACT.md

\* specs/04\_UI\_CONTRACT.md

\* specs/05\_REPORTING\_CONTRACT.md

\* specs/06\_ACCEPTANCE\_TESTS.md



\## Allgemeine technische Tests



Nach jeder Codeänderung:



```bat

python -m compileall src tests

python -m pytest -q

```



Beides muss grün sein.



\## Backtest-Apparat Tests



Es muss Tests geben, die sicherstellen:



\* Smoke und Full nutzen denselben Pipeline-/Controller-Codepfad.

\* Smoke unterscheidet sich nur durch run\_type und Zeitraum.

\* Full verwendet 730 Tage Training + 365 Tage Blindtest.

\* Smoke 1 verwendet 2 Tage Training + 1 Tag Blindtest.

\* Smoke 7 verwendet 14 Tage Training + 7 Tage Blindtest.

\* Smoke 14 verwendet 28 Tage Training + 14 Tage Blindtest.

\* Smoke 30 verwendet 60 Tage Training + 30 Tage Blindtest.

\* Training und Blindtest überlappen nicht.

\* Blindtest liegt nach dem Training.

\* Kein Blindtest-Lernen stattfindet.

\* Kein Lookahead möglich ist.



\## UI-Tests



Es muss Tests geben, die sicherstellen:



\* Smoke-Test ist aus UI/Controller startbar.

\* Full-Backtest ist aus UI/Controller startbar.

\* Smoke-Test erzeugt run\_type = smoke\_test.

\* Full-Backtest erzeugt run\_type = full\_backtest.

\* UI zeigt den richtigen aktuellen Run.

\* UI verweist auf den richtigen Report-Ordner.

\* UI zeigt Candidate-Space Status.

\* UI zeigt Best training USDC/Tag.

\* UI zeigt Zielquote zu 3 USDC/Tag.

\* UI zeigt 0 Trades nicht ohne Diagnose.



\## Reporting-Tests



Es muss Tests geben, die sicherstellen:



\* backtest\_summary.json enthält Pflichtfelder.

\* Router-/Strategy-Report enthält Candidate-Space-Felder.

\* Rejection-Counts werden geschrieben.

\* Best-Candidates werden auch bei 0 trade\_allowed geschrieben.

\* Best training USDC/Tag ist nicht fälschlich 0, wenn ein Best-Candidate existiert.

\* technische und strategische Status getrennt sind.

\* 0 Trades erzeugt eine Diagnose.

\* alter Report wird nicht bevorzugt.

\* Reports enthalten run\_id und run\_type.



\## Daten-Tests



Es muss Tests geben, die sicherstellen:



\* ETHUSDC Candles werden korrekt geladen.

\* BTCUSDC Kontextdaten werden korrekt geladen oder sauber als nicht nutzbar markiert.

\* ETHBTC Kontextdaten werden korrekt geladen oder sauber als nicht nutzbar markiert.

\* Gaps werden erkannt.

\* Candle Count wird geprüft.

\* Datenqualität wird im Report sichtbar.

\* Nicht verfügbare Datenquellen werden ehrlich markiert.

\* Nicht verfügbare Datenquellen werden nicht stillschweigend verwendet.



\## Strategy-Engine Tests



Für den neuen activity\_first\_router muss getestet werden:



\* mehrere Entry-Familien werden erzeugt

\* Momentum Entry existiert

\* Pullback Entry existiert

\* Range Breakout Entry existiert

\* Volatility Expansion Entry existiert

\* Mean Reversion Entry existiert

\* Trend Continuation Entry existiert

\* mehrere TP/SL/Hold-Varianten werden getestet

\* Gebühren werden berücksichtigt

\* Netto-PnL nach Fees wird berechnet

\* Trades pro Tag werden berechnet

\* Aktivitätsklassen werden korrekt zugeordnet

\* Best-Candidates werden gespeichert

\* Candidate-Rejections werden gezählt



\## Aktivitäts-Tests



Der neue Router muss zeigen, dass er Kandidaten in verschiedenen Aktivitätsklassen erzeugen kann.



Mindestens testen:



\* very\_low\_activity

\* low\_activity

\* usable\_activity

\* target\_activity

\* high\_activity



Der Test muss nicht beweisen, dass alle profitabel sind.



Er muss beweisen, dass der Suchraum diese Aktivitätsbereiche erzeugen und bewerten kann.



\## Fenster-Skalierung Tests



Tests müssen sicherstellen:



14 Tage Training:



\* 1 Trade/Tag = ca. 14 Training-Trades

\* 3 Trades/Tag = ca. 42 Training-Trades

\* 6 Trades/Tag = ca. 84 Training-Trades



730 Tage Training:



\* 1 Trade/Tag = ca. 730 Training-Trades

\* 3 Trades/Tag = ca. 2190 Training-Trades

\* 6 Trades/Tag = ca. 4380 Training-Trades



Fehlerfall muss verhindert werden:



\* Jahreswerte dürfen nicht als absolute Mindestwerte im Smoke verwendet werden.



\## Smoke-Akzeptanz



Ein 7-Tage-Smoke gilt technisch als brauchbar, wenn:



\* er aus UI/Controller-Pfad läuft

\* run\_type = smoke\_test ist

\* Training 14 Tage ist

\* Blindtest 7 Tage ist

\* aktueller Strategie-Kern verwendet wird

\* Kandidaten erzeugt werden

\* Setup-Tests ausgeführt werden

\* Reports vollständig sind

\* Best-Candidates sichtbar sind

\* 0 Trades, falls vorhanden, vollständig erklärt werden



\## Smoke-Zielrichtung



Ein 7-Tage-Smoke zeigt Zielrichtung, wenn:



\* mehr als 0 Trades entstehen

\* oder mindestens klar ersichtlich ist, warum keine Trades entstehen

\* Kandidaten im Bereich 1 bis 10 Trades/Tag gesucht wurden

\* Best-Candidates Aktivität/Edge/Fees transparent zeigen



Orientierung:



\* 0 Trades: Warnsignal

\* 1 bis 6 Trades: viel zu wenig Aktivität

\* 7 bis 20 Trades: minimale Aktivität

\* 21 bis 42 Trades: Zielrichtung sichtbar

\* 42 bis 70 Trades: hohe Aktivität, Kosten prüfen

\* über 70 Trades: overactive, Kosten kritisch prüfen



\## Full-Backtest-Akzeptanz



Ein Full-Backtest ist erst sinnvoll, wenn Smoke technisch brauchbar ist.



Ein Full-Backtest gilt als auswertbar, wenn:



\* 730 Tage Training genutzt wurden

\* 365 Tage Blindtest genutzt wurden

\* keine Overlap besteht

\* keine Blindtest-Optimierung stattfindet

\* Candidate-Space Status klar ist

\* Reports vollständig sind

\* Trade Count und PnL nachvollziehbar sind

\* Zielquote berechnet wird

\* 0 Trades vollständig begründet wären



\## Kein Live ohne weitere Akzeptanz



Live ist nicht Teil dieser Akzeptanztests.



Live darf später nur mit eigener Spezifikation freigegeben werden.



\## Verbotene Erfolgsmeldungen



Ein Agent darf nicht melden:



\* „fertig“, wenn nur Unit-Tests grün sind

\* „Smoke funktioniert“, wenn nur ein synthetischer Test funktioniert

\* „Backtest funktioniert“, wenn UI 0 Trades ohne Diagnose zeigt

\* „Ziel erreicht“, wenn nur Training positiv war

\* „Router ist gut“, wenn Aktivität mathematisch zu niedrig ist

\* „Full-Backtest sinnvoll“, wenn Smoke noch optimizer\_search\_space\_failed zeigt



\## Mindestbericht nach Agent-Arbeit



Nach Agent-Arbeit muss kurz berichtet werden:



1\. Welche Spezifikationsdateien wurden gelesen?

2\. Welche Dateien wurden geändert?

3\. Welche Tests wurden ausgeführt?

4\. Tests grün ja/nein?

5\. Wurde UI-naher Smoke ausgeführt?

6\. Ergebnis des Smoke:



&#x20;  \* Run-ID

&#x20;  \* Trade Count

&#x20;  \* Candidate-Space Status

&#x20;  \* Best training USDC/Tag

&#x20;  \* Zielquote

7\. Ist Full-Backtest sinnvoll ja/nein?

8\. Was ist der nächste konkrete Schritt?



\## Wichtigste Regel



Ein Patch gilt erst als Fortschritt, wenn er durch Spezifikation, Tests und UI-nahen Smoke nachvollziehbar ist.



