\# 05\_REPORTING\_CONTRACT.md – Reporting-Vertrag



\## Zweck



Diese Datei definiert verbindlich, welche Reports der Bot schreiben muss und welche Informationen in UI, Summary und Diagnose sichtbar sein müssen.



Reports sind wichtig, weil ohne klare Reports nicht erkennbar ist, ob ein Lauf wirklich funktioniert oder nur technisch „completed“ ist.



\## Grundsatz



Jeder Run muss nachvollziehbar sein.



Ein Run gilt nur dann als auswertbar, wenn klar sichtbar ist:



\* welche Daten verwendet wurden

\* welcher Zeitraum verwendet wurde

\* welcher run\_type verwendet wurde

\* welche Strategie/Router-Engine verwendet wurde

\* wie viele Kandidaten erzeugt wurden

\* wie viele Setup-Tests liefen

\* warum Kandidaten verworfen wurden

\* ob Trades ausgeführt wurden

\* warum 0 Trades entstanden sind, falls keine Trades entstehen



\## Report-Arten



Pflichtreports je Run:



\* backtest\_summary.json

\* data\_preparation\_report.json

\* split\_report.json

\* strategy/router report

\* diagnostics report



Der Name des Router-Reports darf je Strategie variieren, muss aber im Summary klar referenziert werden.



\## Run-Metadaten



Jeder Report muss mindestens enthalten:



\* run\_id

\* run\_type

\* status

\* message

\* created\_at

\* duration\_seconds

\* profile

\* stake\_usdc

\* symbol

\* quote\_asset

\* base\_asset



run\_type muss klar sein:



\* smoke\_test

\* full\_backtest

\* paper

\* test\_trade

\* live



Aktuell relevant:



\* smoke\_test

\* full\_backtest



\## Zeitfenster



Reports müssen klar enthalten:



\* training\_start

\* training\_end

\* blindtest\_start

\* blindtest\_end

\* training\_days

\* blindtest\_days



Smoke und Full müssen über dieselben Felder berichtet werden.



\## Datenqualität



Reports müssen enthalten:



\* ETHUSDC candle count

\* ETHUSDC gaps

\* ETHUSDC usable\_for\_backtest

\* ETHUSDC used\_in\_backtest

\* BTCUSDC candle count

\* BTCUSDC gaps

\* BTCUSDC usable\_for\_backtest

\* BTCUSDC used\_in\_backtest

\* ETHBTC candle count

\* ETHBTC gaps

\* ETHBTC usable\_for\_backtest

\* ETHBTC used\_in\_backtest

\* exchange\_info usable

\* fehlende Datenquellen

\* nicht genutzte Datenquellen



Nicht verfügbare Daten müssen ehrlich markiert werden:



\* aggTrades

\* trades

\* bookTicker

\* Orderbook / Depth



\## Ergebnisfelder



Pflichtfelder im Summary:



\* start\_capital

\* final\_capital

\* total\_pnl

\* total\_pnl\_pct

\* trade\_count

\* win\_rate

\* gross\_pnl

\* fees

\* net\_pnl

\* quote\_per\_day

\* max\_drawdown

\* average\_trade\_pnl

\* average\_hold\_minutes



Wenn ein Feld nicht berechnet werden kann, muss es klar als nicht vorhanden markiert werden.



\## Candidate-Space



Jeder Strategie-/Router-Report muss den Candidate-Space sichtbar machen.



Pflichtfelder:



\* candidate\_space\_status

\* opportunity\_windows\_count

\* opportunity\_cluster\_count

\* candidate\_count

\* setup\_test\_count

\* trade\_allowed\_count

\* selected\_candidate\_count

\* rejected\_candidate\_count



candidate\_space\_status Beispiele:



\* candidates\_found

\* trade\_allowed\_found

\* optimizer\_search\_space\_failed

\* target\_activity\_missing

\* target\_edge\_missing

\* no\_trade\_allowed\_setup

\* target\_not\_reached

\* target\_reached



\## Search-Passes



Wenn mehrere Suchpässe existieren, müssen sie einzeln berichtet werden.



Beispiele:



\* primary

\* activity\_expansion

\* target\_activity

\* opportunity\_mining

\* activity\_first



Für jeden Pass:



\* pass\_name

\* candidates\_generated

\* setup\_tests\_run

\* candidates\_positive\_net

\* candidates\_active\_enough

\* candidates\_trade\_allowed

\* rejection\_counts

\* best\_candidate



\## Rejection-Counts



Rejection-Gründe müssen gezählt werden.



Pflichtgründe:



\* rejected\_by\_precheck

\* rejected\_by\_activity

\* rejected\_by\_target\_math

\* rejected\_by\_training\_net

\* rejected\_by\_fees

\* rejected\_by\_profit\_factor

\* rejected\_by\_robustness

\* rejected\_by\_drawdown

\* rejected\_by\_deduplication

\* rejected\_by\_context\_filter

\* rejected\_by\_other



Ein Kandidat darf nicht verschwinden, ohne dass ein Grund gezählt wird.



\## Best-Candidates



Auch wenn kein Kandidat trade\_allowed wird, müssen Best-Candidates gespeichert werden:



\* best\_activity\_candidate

\* best\_edge\_candidate

\* best\_balanced\_candidate

\* best\_fee\_survivor\_candidate

\* best\_target\_candidate



Diese Kandidaten sind Diagnose.



Sie sind nicht automatisch handelbar.



\## Pflichtfelder je Best-Candidate



Jeder Best-Candidate muss enthalten:



\* candidate\_id

\* strategy\_family

\* search\_pass

\* activity\_class

\* trades\_per\_day

\* active\_days

\* training\_trade\_count

\* training\_net\_pnl

\* training\_gross\_pnl

\* training\_fees

\* training\_quote\_per\_day

\* training\_win\_rate

\* training\_profit\_factor

\* max\_drawdown

\* average\_hold\_minutes

\* tp

\* sl

\* max\_hold

\* trailing\_stop, falls genutzt

\* context\_filters

\* rejection\_reason

\* distance\_to\_target



\## 0 Trades



0 Trades dürfen nicht nur als completed dargestellt werden.



Bei trade\_count = 0 müssen Reports beantworten:



\* wurden Kandidaten erzeugt?

\* wurden Setup-Tests ausgeführt?

\* gab es positive Kandidaten?

\* gab es aktive Kandidaten?

\* warum wurde niemand trade\_allowed?

\* lag es an Aktivität?

\* lag es an Edge?

\* lag es an Fees?

\* lag es an Robustness?

\* lag es an Target-Relevanz?

\* lag es an Precheck?

\* lag es an Daten?

\* lag es an UI-/Pfadproblemen?



0 Trades ohne Diagnose ist ein Reporting-Fehler.



\## Best training USDC/Tag



Wenn intern ein Best-Candidate existiert, darf Summary nicht fälschlich 0.0000 anzeigen.



`best\_training\_usdc\_per\_day` muss den besten relevanten Trainingswert zeigen, auch wenn der Kandidat nicht trade\_allowed wurde.



Zusätzlich muss klar sein, warum er nicht trade\_allowed wurde.



\## Zielquote



Reports müssen den Abstand zum Ziel 3 USDC/Tag zeigen.



Pflicht:



\* target\_daily\_usdc = 3.0

\* best\_training\_usdc\_per\_day

\* blindtest\_usdc\_per\_day

\* target\_ratio\_to\_3\_usdc\_day



Beispiel:



\* best\_training\_usdc\_per\_day = 0.0624

\* target\_ratio = 0.0208



Das bedeutet: ca. 2,08 % des Zielwerts.



\## Technischer Status vs. strategischer Status



Reports müssen unterscheiden:



Technischer Status:



\* completed

\* failed



Strategischer Status:



\* target\_reached

\* target\_not\_reached

\* optimizer\_search\_space\_failed

\* target\_activity\_missing

\* target\_edge\_missing



Ein Run kann technisch completed sein und strategisch trotzdem gescheitert.



\## UI-Reporting



Die UI muss die wichtigsten Reportfelder anzeigen oder klar auf den Report verweisen.



Pflicht in UI:



\* Run-ID

\* Run-Type

\* Status

\* Progress

\* Laufzeit

\* Report-Pfad

\* Training/Blindtest-Zeitraum

\* Trade Count

\* Total PnL

\* Candidate-Space Status

\* Best training USDC/Tag

\* Zielnähe Status

\* Zielquote

\* No robust positive candidate



\## Report-Pfade



Jeder Run muss einen eigenen Report-Ordner haben:



reports/backtests/<run\_id>/



Reports dürfen nicht versehentlich alte Runs überschreiben.



UI muss den korrekten aktuellen Report anzeigen.



\## Keine alten Reports bevorzugen



Nicht erlaubt:



\* UI zeigt alten Report

\* Summary liest alten Router-Report

\* neuer Run verweist auf alten Report

\* Report-Felder stammen aus einem anderen Run

\* Inline-Test-Report wird als UI-Smoke-Ergebnis dargestellt



\## Smoke-Reports



Smoke-Reports müssen dieselben Kernfelder wie Full-Backtest-Reports enthalten.



Zusätzlich:



\* run\_type = smoke\_test

\* smoke\_blindtest\_days

\* smoke\_training\_days



Smoke-Reports dürfen nicht kleiner oder weniger aussagekräftig sein, wenn ein Fehler analysiert werden muss.



\## Full-Reports



Full-Backtest-Reports müssen zusätzlich Jahres-/Monatsauswertung ermöglichen.



Später wichtig:



\* positive Tage

\* negative Tage

\* neutrale Tage

\* bester Tag

\* schlechtester Tag

\* bester Monat

\* schlechtester Monat

\* längste Gewinnserie

\* längste Verlustserie



Diese Felder sind für den ersten activity\_first\_router nicht zwingend Pflicht, sollen aber nicht blockiert werden.



\## Reporting-Akzeptanzkriterium



Reporting gilt als brauchbar, wenn:



\* jeder Lauf eindeutig nachvollziehbar ist

\* UI und Report denselben Run zeigen

\* 0 Trades vollständig erklärbar sind

\* Best-Candidates sichtbar sind

\* Candidate-Space transparent ist

\* Rejection-Gründe gezählt werden

\* technische und strategische Status getrennt sind

\* keine alten Reports genutzt werden



\## Wichtigste Regel



Ein Report darf nicht nur sagen, dass etwas nicht funktioniert.



Er muss zeigen, warum es nicht funktioniert.



