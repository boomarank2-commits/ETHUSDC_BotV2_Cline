\# 04\_UI\_CONTRACT.md – UI-Vertrag



\## Zweck



Diese Datei definiert verbindlich, wie die Benutzeroberfläche im Projekt funktionieren muss.



Die UI ist die Wahrheit für alle relevanten Bot-Abläufe.



Wenn etwas nur per internem Test oder CLI funktioniert, aber nicht aus der UI, gilt es nicht als fertig.



\## Grundsatz



Alle wichtigen Abläufe müssen aus der UI startbar, sichtbar und nachvollziehbar sein.



Dazu gehören:



\* Daten laden / aktualisieren

\* Smoke-Test starten

\* Full-Backtest starten

\* Ergebnisse anzeigen

\* Reports öffnen / verlinken

\* Paper-Trading später starten

\* Live-Freigabe später bewusst bestätigen



\## UI ist Wahrheit



Ein Lauf gilt nur als relevant, wenn er aus der UI oder über denselben UI-Controller/Pipeline-Pfad gestartet wurde.



Nicht ausreichend:



\* synthetischer Inline-Test

\* isolierter Router-Test

\* isolierter CLI-Test

\* manuell zusammengestellter Test ohne UI-Controller

\* Testdaten, die nicht dem echten Projektpfad entsprechen



Wenn UI und interner Test widersprechen, gilt zuerst die UI.



\## Gemeinsamer Startpfad



Smoke-Test und Full-Backtest müssen denselben UI-/Controller-Pfad nutzen.



Pfad:



UI Button

→ UI Controller

→ Run Request

→ Preparation Pipeline

→ Data Preparation

→ Train/Blind Split

→ Strategy/Router/Optimizer

→ Simulation

→ Report

→ UI Anzeige



Smoke darf keinen separaten Sonderpfad haben.



\## Smoke-Test in der UI



Die UI muss Smoke-Test als verkürzten Backtest anbieten.



Pflicht:



\* Button: Smoke-Test starten

\* Auswahl Smoke-Dauer:



&#x20; \* 1 Tag

&#x20; \* 7 Tage

&#x20; \* 14 Tage

&#x20; \* 30 Tage

\* Eingabe Einsatz in USDC

\* Auswahl Profil, z. B. normal

\* klare Anzeige: run\_type = smoke\_test



Smoke-Zuordnung:



\* 1 Tag Blindtest = 2 Tage Training

\* 7 Tage Blindtest = 14 Tage Training

\* 14 Tage Blindtest = 28 Tage Training

\* 30 Tage Blindtest = 60 Tage Training



\## Full-Backtest in der UI



Die UI muss Full-Backtest als echten 365-Tage-Blindtest anbieten.



Standard:



\* 730 Tage Training

\* 365 Tage Blindtest

\* Einsatz wählbar

\* Profil wählbar

\* run\_type = full\_backtest



Full-Backtest darf nicht gestartet werden, wenn die technischen Voraussetzungen nicht erfüllt sind.



\## Keine zwei Wahrheiten



Nicht erlaubt:



\* Smoke-Button startet andere Engine

\* Full-Button startet andere Engine

\* UI zeigt anderen Report als tatsächlich erzeugt

\* UI nutzt alte Reports bevorzugt

\* UI zeigt Best training 0.0000, obwohl Report Best-Candidates enthält

\* UI versteckt Candidate-Space-Fehler

\* UI zeigt completed, obwohl der Optimizer-Suchraum gescheitert ist



\## Ergebnisanzeige



Die UI muss nach einem Lauf klar anzeigen:



\* Run-ID

\* Run-Type

\* Status

\* Progress

\* Laufzeit

\* Report-Pfad

\* Report-Ordner

\* Training Start

\* Training Ende

\* Blindtest Start

\* Blindtest Ende

\* Startkapital

\* Endkapital

\* Total PnL

\* Total PnL %

\* Trade Count

\* Candidate-Space Status

\* No robust positive candidate

\* Best training USDC/Tag

\* Zielnähe Status

\* Zielquote zu 3 USDC/Tag



\## Datenqualität in der UI



Die UI muss Datenqualität sichtbar machen:



\* ETHUSDC 1m Candles

\* BTCUSDC 1m Candles

\* ETHBTC 1m Candles

\* exchange\_info

\* Gaps

\* Candle Count

\* Mindestwert

\* letzter Timestamp

\* Datenalter

\* usable\_for\_backtest

\* used\_in\_backtest



Nicht verfügbare Daten müssen klar angezeigt werden:



\* aggTrades

\* trades

\* bookTicker

\* Orderbook / Depth



Wenn diese Daten nicht historisch verfügbar sind, dürfen sie nicht stillschweigend als genutzt dargestellt werden.



\## Candidate-Diagnose in der UI



Wenn ein Lauf fehlschlägt oder 0 Trades hat, muss die UI ausreichend Diagnose anzeigen oder auf Reportfelder verweisen.



Pflicht sichtbar oder im Report klar auffindbar:



\* opportunity\_windows\_count

\* opportunity\_cluster\_count

\* candidate\_count

\* setup\_test\_count

\* trade\_allowed\_count

\* rejection\_counts

\* best\_activity\_candidate

\* best\_edge\_candidate

\* best\_balanced\_candidate

\* best\_fee\_survivor\_candidate

\* best\_target\_candidate



\## 0 Trades in der UI



0 Trades dürfen nicht wie ein normaler Erfolg aussehen.



Wenn Trade Count = 0, muss die UI anzeigen:



\* Candidate-Space Status

\* Hauptblocker

\* ob Kandidaten erzeugt wurden

\* ob Setup-Tests liefen

\* ob Best-Candidates existieren

\* warum kein Kandidat trade\_allowed wurde



0 Trades ohne Diagnose ist ein Fehler.



\## Status-Logik



Die UI darf nicht nur `completed` anzeigen, wenn der Strategieraum gescheitert ist.



Beispiel:



Ein Lauf kann technisch completed sein, aber strategisch gescheitert.



Daher braucht die UI getrennte Sicht auf:



\* technischer Run-Status

\* Candidate-Space Status

\* Zielnähe Status



Beispiel:



\* Status: completed

\* Candidate-Space Status: optimizer\_search\_space\_failed

\* Zielnähe Status: target\_out\_of\_reach\_current\_activity



\## Progress



Die UI muss bei längeren Läufen Fortschritt anzeigen.



Pflicht:



\* Progress %

\* Progress Stage

\* Laufzeit

\* geschätzte Restzeit, falls verfügbar

\* keine lange stille Phase ohne Hinweis



Lange Läufe ohne sichtbares Lebenszeichen sind nicht akzeptabel.



\## Sicherheit



Die UI darf keine echten Orders auslösen, solange Live nicht ausdrücklich freigegeben ist.



Smoke und Full sind immer Simulation.



Nicht erlaubt:



\* echte Orders im Smoke

\* echte Orders im Full-Backtest

\* versteckte Live-Aktivierung

\* API-Key-Nutzung ohne klare Anzeige

\* Live-Freigabe durch Smoke

\* Live-Freigabe durch Full ohne manuelle Bestätigung



\## Paper-Trading später



Paper-Trading darf erst nach brauchbarem Full-Backtest relevant werden.



Paper-Trading muss sichtbar als Paper gekennzeichnet sein.



Paper darf keine echten Orders auslösen.



\## Live später



Live ist nicht Teil des aktuellen Neuaufbaus.



Live darf später nur aktiviert werden, wenn:



\* Full-Backtest brauchbar ist

\* Paper-Trading plausibel ist

\* Nutzer bewusst bestätigt

\* UI klar Live anzeigt

\* Kapitalgrenzen gesetzt sind

\* keine Short/Margin/Futures/Leverage-Logik existiert



\## UI-Akzeptanzkriterien



Die UI gilt als brauchbar, wenn:



\* Smoke-Test aus UI startbar ist

\* Full-Backtest aus UI startbar ist

\* beide denselben Backtest-Apparat nutzen

\* Ergebnisse vollständig angezeigt werden

\* Report-Pfade stimmen

\* Datenqualität sichtbar ist

\* Candidate-Space Status sichtbar ist

\* 0 Trades nicht ohne Diagnose bleiben

\* keine separaten Smoke-/Full-Wahrheiten entstehen



\## Wichtigste Regel



Wenn der Nutzer aus der UI startet, muss genau der echte gemeinsame Bot-/Backtest-Apparat laufen.



Keine internen Tests ersetzen diese Wahrheit.



