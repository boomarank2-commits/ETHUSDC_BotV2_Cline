\# 01\_BACKTEST\_CONTRACT.md – Backtest-Vertrag



\## Zweck



Diese Datei definiert verbindlich, wie Backtests im Projekt funktionieren müssen.



Der Backtest ist die zentrale Wahrheit für Strategie-Entwicklung, Optimierung und spätere Paper-/Live-Vorbereitung.



\## Ein gemeinsamer Backtest-Apparat



Es gibt nur einen Backtest-Apparat.



Smoke-Test und Full-Backtest sind keine getrennten Systeme.



Beide verwenden denselben Codepfad:



UI → Controller → Run Request → Preparation Pipeline → Train/Blind Split → Strategy/Router/Optimizer → Simulation → Reports



Der einzige Unterschied zwischen Smoke und Full ist der Zeitraum und die Report-Markierung `run\_type`.



\## Full-Backtest



Der Full-Backtest ist der echte 365-Tage-Blindtest.



Standard:



\* 730 Tage Training / Optimierung

\* 365 Tage Blindtest

\* ETHUSDC 1m Binance Spot Candles

\* Stake: wählbar, Standard 100 USDC

\* Profil: wählbar, Standard normal



Der Full-Backtest darf erst gestartet werden, wenn Smoke-Tests zeigen, dass der gemeinsame Backtest-Apparat technisch korrekt läuft.



\## Smoke-Test



Smoke-Test ist ein verkürzter Lauf desselben Backtest-Apparats.



Smoke-Test ist kein Leistungsnachweis und keine Live-Freigabe.



Smoke-Zeiträume:



\* 1 Tag Blindtest = 2 Tage Training

\* 7 Tage Blindtest = 14 Tage Training

\* 14 Tage Blindtest = 28 Tage Training

\* 30 Tage Blindtest = 60 Tage Training



Smoke-Test dient zur schnellen technischen Prüfung nach Patches.



\## UI ist Wahrheit



Ein Backtest gilt nur dann als relevant, wenn er aus der UI oder über denselben UI-Controller/Pipeline-Pfad gestartet werden kann.



Inline-Tests, Unit-Tests oder synthetische Tests dürfen helfen, aber sie ersetzen nicht den UI-nahen Lauf.



Wenn Inline-Test und UI-Smoke unterschiedliche Ergebnisse zeigen, gilt der UI-Smoke als Wahrheit.



\## Keine separaten Pfade



Nicht erlaubt:



\* separate Smoke-Engine

\* separater Smoke-Router

\* separate Smoke-Strategie

\* separater Smoke-Simulator

\* separater Smoke-Report mit anderer Logik

\* versteckter V1-Fallback

\* alter Default-Pfad, der bei Smoke oder Full anders handelt



Wenn Smoke gepatcht wird, muss der gemeinsame Backtest-Apparat gepatcht werden.



Wenn Full gepatcht wird, muss Smoke automatisch denselben Patch nutzen.



\## Training und Blindtest



Training und Blindtest müssen strikt getrennt sein.



Training darf verwenden:



\* historische Candles im Training-Zeitraum

\* Kontextdaten im Training-Zeitraum

\* Fees/Slippage/Exchange-Info

\* MFE/MAE nur zur Trainingsbewertung, nicht als Live-/Blindtest-Feature



Blindtest darf nicht verwenden:



\* zukünftige Daten

\* Labels aus der Zukunft

\* nachträgliche Optimierung

\* Blindtest-Ergebnis zur Kandidatenauswahl

\* manuelles Nachjustieren während des Laufs



\## Kein Lookahead



Es darf kein Lookahead entstehen.



Entry-Features dürfen nur Daten nutzen, die zum Entscheidungszeitpunkt bekannt gewesen wären.



Nicht erlaubt:



\* zukünftiges High/Low als Entry-Feature

\* zukünftige MFE/MAE als Entry-Feature

\* Blindtest-Lernen

\* Blindtest-Reoptimierung

\* Trade-Auswahl nach bekanntem Ergebnis



\## Kosten und Realismus



Backtest muss Kosten berücksichtigen:



\* Binance Spot Gebühren

\* Stake in USDC

\* MIN\_NOTIONAL

\* LOT\_SIZE

\* PRICE\_FILTER

\* optional Slippage, falls im Profil aktiviert



Ein Setup, das nur vor Fees positiv ist und nach Fees negativ wird, ist nicht robust.



\## Zielaktivität



Der Backtest muss prüfen, ob der Strategie-Kern genügend Aktivität erzeugen kann.



Für das Ziel 3 USDC/Tag mit 100 USDC Einsatz sind 0 Trades oder extrem seltene Trades mathematisch unbrauchbar.



Orientierung:



\* 1 Trade/Tag = niedrige Aktivität

\* 3 bis 6 Trades/Tag = Zielbereich

\* 6 bis 10 Trades/Tag = hoher, aber noch prüfbarer Aktivitätsbereich



Der Backtest darf schlechte Trades nicht erzwingen.



Aber der Optimizer muss aktiv Kandidaten mit ausreichender Aktivität suchen.



\## Fensterabhängige Skalierung



Alle Aktivitätsanforderungen müssen auf die tatsächliche Trainingsdauer skaliert werden.



Beispiele:



14 Tage Training:



\* 1 Trade/Tag = 14 Training-Trades

\* 3 Trades/Tag = 42 Training-Trades

\* 6 Trades/Tag = 84 Training-Trades



365 Tage Blindtest:



\* 1 Trade/Tag = 365 Trades

\* 3 Trades/Tag = 1095 Trades

\* 6 Trades/Tag = 2190 Trades



Fehlerhaft wäre:



\* im 14-Tage-Smoke 1095 Training-Trades zu verlangen

\* Jahreswerte als absolute Mindestwerte für kurze Smoke-Fenster zu verwenden



\## Ergebnisstatus



Der Backtest muss klare Status liefern.



Wichtige Status:



\* completed

\* failed

\* data\_not\_usable

\* optimizer\_search\_space\_failed

\* no\_trade\_allowed\_setup

\* blindtest\_completed

\* target\_reached

\* target\_not\_reached

\* target\_out\_of\_reach\_current\_activity



\## 0 Trades



0 Trades im Smoke oder Full sind kein normaler Erfolg.



0 Trades sind erlaubt, wenn vollständig begründet:



\* keine Opportunity-Fenster

\* keine aktiven Kandidaten

\* alle Kandidaten nach Fees negativ

\* Aktivität fehlt

\* Edge fehlt

\* Robustness fehlt

\* Kandidaten wurden korrekt verworfen



Der Report muss diese Gründe sichtbar machen.



0 Trades ohne klare Diagnose ist ein Fehler.



\## Reports



Jeder Backtest muss Reports schreiben.



Pflichtfelder:



\* run\_id

\* run\_type

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

\* data\_quality\_report

\* router\_report

\* diagnostics



\## Kandidaten-Diagnose



Auch wenn kein Kandidat `trade\_allowed` wird, müssen Best-Candidates gespeichert werden:



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

\* TP/SL/Hold

\* Aktivität

\* Edge

\* Rejection-Grund

\* Abstand zum Ziel



\## Akzeptanzkriterium für Backtest-Apparat



Der Backtest-Apparat gilt technisch als lauffähig, wenn:



\* UI-Smoke und UI-naher Controller-Lauf denselben Codepfad nutzen

\* Smoke und Full nur durch Zeitraum/run\_type abweichen

\* Training/Blindtest korrekt getrennt sind

\* Reports vollständig sind

\* 0 Trades nicht ohne Diagnose möglich sind

\* Best-Candidates bei Fehlschlag sichtbar sind

\* keine separaten Backtest-Wahrheiten existieren



\## Nicht Ziel dieser Datei



Diese Datei garantiert keinen Gewinn.



Diese Datei definiert nur, wie der Backtest korrekt funktionieren muss.



