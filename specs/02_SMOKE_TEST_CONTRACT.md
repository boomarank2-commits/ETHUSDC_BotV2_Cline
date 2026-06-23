\# 02\_SMOKE\_TEST\_CONTRACT.md – Smoke-Test-Vertrag



\## Zweck



Diese Datei definiert verbindlich, wie Smoke-Tests im Projekt funktionieren müssen.



Ein Smoke-Test ist ein kurzer technischer Prüflauf des echten Backtest-Apparats.



Smoke-Test ist kein eigener Backtest, keine eigene Engine und keine eigene Strategie.



\## Grundsatz



Es gibt nur einen gemeinsamen Backtest-Apparat.



Smoke-Test und Full-Backtest nutzen denselben Codepfad:



UI → Controller → Run Request → Preparation Pipeline → Train/Blind Split → Strategy/Router/Optimizer → Simulation → Reports



Der einzige Unterschied ist:



\* kürzerer Zeitraum

\* `run\_type = smoke\_test`

\* Report-Markierung als Smoke-Test



\## Nicht erlaubt



Nicht erlaubt sind:



\* eigene Smoke-Engine

\* eigener Smoke-Router

\* eigene Smoke-Strategie

\* eigener Smoke-Simulator

\* eigener Smoke-Optimizer

\* andere Gebührenlogik

\* andere Entry-/Exit-Logik

\* anderer Reportaufbau

\* separater Smoke-Fallback

\* versteckter V1-Fallback

\* synthetische Inline-Tests als Erfolgsbeweis



Wenn Smoke und Full unterschiedliche Ergebnisse zeigen, obwohl Zeitraum und Daten vergleichbar sind, ist das ein Fehler.



\## UI ist Wahrheit



Smoke-Tests müssen aus der UI oder über denselben UI-nahen Controller/Pipeline-Pfad startbar sein.



Ein Unit-Test oder Inline-Test darf helfen, aber er beweist nicht, dass der Bot aus Benutzersicht funktioniert.



Wenn ein interner Test sagt “funktioniert”, aber der UI-Smoke 0 Trades oder falsche Reports zeigt, gilt der UI-Smoke als Wahrheit.



\## Smoke-Zeiträume



Standard-Smoke-Zeiträume:



\* 1 Tag Blindtest = 2 Tage Training

\* 7 Tage Blindtest = 14 Tage Training

\* 14 Tage Blindtest = 28 Tage Training

\* 30 Tage Blindtest = 60 Tage Training



Diese Zeiträume sind bewusst kurz, damit nach Patches schnell geprüft werden kann, ob der gemeinsame Backtest-Apparat technisch korrekt läuft.



\## Zweck des Smoke-Tests



Smoke-Test prüft:



\* Wird der gemeinsame Backtest-Apparat korrekt gestartet?

\* Werden die richtigen Daten geladen?

\* Wird der richtige Zeitraum verwendet?

\* Wird Training/Blindtest korrekt getrennt?

\* Wird der aktuelle Strategie-/Router-Code verwendet?

\* Werden Kandidaten erzeugt?

\* Werden Setup-Tests ausgeführt?

\* Werden Trades simuliert, falls trade\_allowed vorhanden ist?

\* Werden Reports vollständig geschrieben?

\* Wird ein Fehler klar angezeigt, wenn kein Kandidat handelbar ist?



\## Was Smoke-Test nicht ist



Smoke-Test ist kein Leistungsnachweis.



Smoke-Test darf nicht verwendet werden für:



\* Live-Freigabe

\* Strategie-Übernahme

\* Gewinnversprechen

\* endgültige Bewertung einer Strategie

\* echtes Trading

\* Paper-Freigabe

\* manuelle Strategie-Optimierung anhand des Blindtests



\## Erwartung an Aktivität



Smoke-Test muss nicht profitabel sein.



Aber Smoke-Test soll zeigen, ob der Strategie-Kern überhaupt Kandidaten im Zielbereich erzeugen kann.



Orientierung für 7 Tage Blindtest:



\* 1 Trade/Tag = 7 Trades

\* 3 Trades/Tag = 21 Trades

\* 6 Trades/Tag = 42 Trades

\* 10 Trades/Tag = 70 Trades



0 Trades sind nicht automatisch verboten, aber 0 Trades ohne klare Diagnose sind ein Fehler.



\## Fensterabhängige Skalierung



Alle Aktivitätsanforderungen müssen auf die tatsächliche Trainingsdauer skaliert werden.



Beispiel 14 Tage Training:



\* 1 Trade/Tag = 14 Training-Trades

\* 3 Trades/Tag = 42 Training-Trades

\* 6 Trades/Tag = 84 Training-Trades



Fehlerhaft wäre:



\* im 14-Tage-Smoke 1095 Training-Trades zu verlangen

\* Jahreswerte direkt als absolute Mindestwerte zu verwenden

\* Smoke wegen Full-Backtest-Jahresgrenzen leer laufen zu lassen



\## Smoke-Ergebnisstatus



Smoke-Test muss klare Status liefern.



Wichtige Status:



\* completed

\* failed

\* data\_not\_usable

\* optimizer\_search\_space\_failed

\* no\_trade\_allowed\_setup

\* smoke\_completed

\* smoke\_failed

\* target\_activity\_missing

\* target\_edge\_missing

\* smoke\_diagnostic\_complete



\## Pflichtfelder im Smoke-Report



Ein Smoke-Report muss mindestens enthalten:



\* run\_id

\* run\_type = smoke\_test

\* status

\* training\_start

\* training\_end

\* blindtest\_start

\* blindtest\_end

\* stake\_usdc

\* profile

\* trade\_count

\* total\_pnl

\* total\_pnl\_pct

\* quote\_per\_day

\* candidate\_space\_status

\* best\_training\_usdc\_per\_day

\* target\_ratio\_to\_3\_usdc\_day

\* no\_robust\_positive\_candidate

\* opportunity\_windows\_count

\* opportunity\_cluster\_count

\* candidate\_count

\* setup\_test\_count

\* trade\_allowed\_count

\* rejection\_counts

\* best\_candidates

\* diagnostics



\## Best-Candidates bei Fehlschlag



Auch wenn `trade\_allowed\_count = 0` ist, müssen Best-Candidates gespeichert werden:



\* best\_activity\_candidate

\* best\_edge\_candidate

\* best\_balanced\_candidate

\* best\_fee\_survivor\_candidate

\* best\_target\_candidate



Für jeden Best-Candidate muss sichtbar sein:



\* Trades pro Tag

\* Training-Netto

\* Fees

\* Profit-Factor

\* TP

\* SL

\* Hold

\* Aktivität

\* Edge

\* Rejection-Grund

\* Abstand zum Ziel



\## 0 Trades im Smoke



0 Trades sind ein Warnsignal.



0 Trades sind nur akzeptabel, wenn der Report klar erklärt:



\* wie viele Kandidaten erzeugt wurden

\* wie viele Setup-Tests liefen

\* warum kein Kandidat trade\_allowed wurde

\* ob Aktivität fehlte

\* ob Edge fehlte

\* ob Fees alles negativ machten

\* ob Robustness alles blockierte

\* ob Target-Relevanz alles blockierte

\* ob Precheck zu früh blockierte



0 Trades mit `Best training USDC/Tag = 0.0000` ohne weitere Diagnose ist ein Fehler.



0 Trades mit positiver Best-Training-Leistung muss erklären, warum dieser Best-Candidate nicht handelbar wurde.



\## Smoke nach Patch



Nach jedem Strategie-/Router-/Backtest-Patch soll zuerst ein Smoke-Test laufen.



Reihenfolge:



1\. Unit-Tests

2\. compileall

3\. pytest

4\. UI-naher Smoke-Test

5\. erst danach Full-Backtest



\## Wann ist ein Full-Backtest sinnvoll?



Ein Full-Backtest ist erst sinnvoll, wenn der Smoke-Test zeigt:



\* gemeinsamer Backtest-Apparat läuft korrekt

\* Reports sind vollständig

\* Kandidaten werden erzeugt

\* Setup-Tests laufen

\* Best-Candidates sind sichtbar

\* 0 Trades sind entweder behoben oder vollständig begründet

\* keine alte/kaputte Router-Logik wird verwendet



\## Wann ist ein Full-Backtest nicht sinnvoll?



Ein Full-Backtest ist nicht sinnvoll, wenn Smoke zeigt:



\* 0 Trades ohne brauchbare Diagnose

\* optimizer\_search\_space\_failed ohne Best-Candidates

\* keine Kandidaten

\* keine Setup-Tests

\* Best-Candidate nur extrem selten aktiv

\* UI zeigt andere Wahrheit als interner Test

\* Smoke und Full nutzen unterschiedliche Pfade



\## Akzeptanzkriterium



Smoke-Test gilt technisch als brauchbar, wenn:



\* er denselben Codepfad wie Full nutzt

\* der Zeitraum korrekt ist

\* Training/Blindtest getrennt sind

\* Reports vollständig sind

\* der aktuelle Strategie-Kern sichtbar arbeitet

\* Kandidaten und Rejections nachvollziehbar sind

\* kein separater Smoke-Sonderpfad existiert



\## Wichtigste Regel



Smoke-Test ist kein Mini-Bot.



Smoke-Test ist der echte Backtest-Apparat mit kleinerem Zeitraum.



