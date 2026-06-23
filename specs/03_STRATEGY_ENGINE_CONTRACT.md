\# 03\_STRATEGY\_ENGINE\_CONTRACT.md – Strategie-Engine-Vertrag



\## Zweck



Diese Datei definiert verbindlich, wie der neue Strategie-Kern aufgebaut werden soll.



Der bisherige Cluster-/Opportunity-Router wird nicht weiter geflickt.



Der neue Strategie-Kern heißt:



activity\_first\_router



\## Warum ein neuer Strategie-Kern nötig ist



Der bisherige Router hat mehrfach gezeigt:



\* UI-Smoke läuft technisch.

\* Daten und Split funktionieren.

\* Reports funktionieren.

\* Smoke und Full nutzen denselben Backtest-Apparat.

\* Opportunity-Mining wurde angeschlossen.

\* Best-Candidates wurden sichtbar.



Trotzdem entstanden wiederholt:



\* 0 Trades

\* optimizer\_search\_space\_failed

\* Best-Candidate mit viel zu wenig Aktivität

\* zuletzt ca. 0.0624 USDC/Tag statt Zielrichtung 3 USDC/Tag

\* bester Kandidat nur ca. 1 Trade in 14 Trainingstagen



Damit ist der alte Strategie-Kern als Zielstrategie gescheitert.



\## Neue Grundidee



Der neue Router arbeitet activity-first.



Das bedeutet:



Nicht zuerst seltene profitable Situationen suchen.



Sondern:



1\. Erst aktive Entry-Kandidaten erzeugen.

2\. Zielbereich: ca. 1 bis 10 Trades pro Tag.

3\. Dann nach Kosten, Edge, TP/SL/Hold und Stabilität filtern.

4\. Erst danach darf ein Kandidat trade\_allowed werden.



\## Zielaktivität



Die Strategie-Engine muss Kandidaten in mehreren Aktivitätsbereichen erzeugen und bewerten.



Aktivitätsklassen:



\* very\_low\_activity: < 0.5 Trades/Tag

\* low\_activity: 0.5 bis 1 Trade/Tag

\* usable\_activity: 1 bis 3 Trades/Tag

\* target\_activity: 3 bis 6 Trades/Tag

\* high\_activity: 6 bis 10 Trades/Tag

\* overactive: > 10 Trades/Tag



Zielbereich für die Suche:



\* bevorzugt usable\_activity bis target\_activity

\* high\_activity darf getestet werden

\* overactive nur mit sehr guter Kostenkontrolle



\## Fensterabhängige Skalierung



Aktivitätsanforderungen müssen immer auf die jeweilige Trainingsdauer skaliert werden.



Beispiel 14 Tage Training:



\* 1 Trade/Tag = 14 Training-Trades

\* 3 Trades/Tag = 42 Training-Trades

\* 6 Trades/Tag = 84 Training-Trades

\* 10 Trades/Tag = 140 Training-Trades



Beispiel 730 Tage Training:



\* 1 Trade/Tag = 730 Training-Trades

\* 3 Trades/Tag = 2190 Training-Trades

\* 6 Trades/Tag = 4380 Training-Trades

\* 10 Trades/Tag = 7300 Training-Trades



Jahreswerte dürfen nicht als absolute Mindestwerte für kurze Smoke-Fenster verwendet werden.



\## Handelsrichtung



Nur erlaubt:



\* Spot LONG

\* Entry: USDC -> ETH

\* Exit: ETH -> USDC



Nicht erlaubt:



\* Short

\* Margin

\* Futures

\* Leverage

\* synthetische Gegenposition

\* Hedge-Logik

\* Martingale

\* Nachkaufen ohne eigene Spezifikation



\## Datenquellen



Pflicht:



\* ETHUSDC 1m Candles

\* Binance exchange\_info

\* Gebührenmodell

\* LOT\_SIZE

\* MIN\_NOTIONAL

\* PRICE\_FILTER



Optionaler Kontext:



\* BTCUSDC 1m Candles

\* ETHBTC 1m Candles



Nicht als historische Pflicht verfügbar:



\* bookTicker

\* Orderbook

\* Depth

\* Spread

\* aggTrades

\* trades



Diese Daten dürfen erst genutzt werden, wenn sie historisch oder live sauber gesammelt und im Backtest realistisch verfügbar sind.



\## Entry-Kandidaten



Der activity\_first\_router muss mehrere einfache Entry-Familien erzeugen.



Mindestfamilien:



1\. Momentum Entry

2\. Pullback Entry

3\. Range Breakout Entry

4\. Volatility Expansion Entry

5\. Mean Reversion Entry

6\. Trend Continuation Entry



Jede Entry-Familie muss mehrere Parameter-Varianten haben.



Beispiele:



\* Lookback-Fenster

\* Momentum-Schwelle

\* Pullback-Tiefe

\* Range-Länge

\* Volatilitäts-Schwelle

\* Volumen-/Candle-Filter

\* Trendfilter an/aus

\* BTC-Kontext an/aus

\* ETHBTC-Kontext an/aus



\## Exit-Kandidaten



Jeder Entry-Kandidat muss mit mehreren Exit-Varianten getestet werden.



Pflichtvarianten:



\* Take Profit

\* Stop Loss

\* Max Hold

\* optional Trailing Stop

\* optional Time Exit

\* optional Break-Even-Regel



TP/SL/Hold dürfen nicht starr sein.



Sie müssen als Suchraum getestet werden.



Beispiele:



\* TP klein / mittel / groß

\* SL klein / mittel / groß

\* Hold kurz / mittel / lang

\* Trail aus / klein / mittel



\## Gebühren und Kosten



Jeder Kandidat muss nach Gebühren bewertet werden.



Pflicht:



\* Brutto-PnL

\* Gebühren

\* Netto-PnL

\* Netto pro Trade

\* Netto pro Tag

\* Fee-to-Move-Ratio



Ein Kandidat, der nur vor Gebühren positiv ist, darf nicht trade\_allowed werden.



\## Kandidatenbewertung



Kandidaten werden nicht nur nach Gewinn bewertet.



Bewertung muss enthalten:



\* Trades pro Tag

\* aktive Tage

\* Netto-PnL

\* Netto pro Tag

\* Netto pro Trade

\* Winrate

\* Profit-Factor

\* Max Drawdown

\* Fees

\* durchschnittliche Haltedauer

\* Stabilität über Trainingssegmente

\* Abstand zum Ziel 3 USDC/Tag



\## Keine Frühvernichtung durch Precheck



Precheck darf schlechte Kandidaten aussortieren.



Aber Precheck darf nicht verhindern, dass der Suchraum sichtbar bewertet wird.



Wenn Precheck einen Kandidaten stoppt, muss gespeichert werden:



\* welcher Precheck

\* welche Werte

\* warum gestoppt

\* ob Setup-Test vorher lief

\* ob Kandidat als best\_activity / best\_edge / best\_target relevant war



Positive oder aktive Kandidaten dürfen nicht ohne Diagnose verschwinden.



\## Trade Allowed



Ein Kandidat darf nur trade\_allowed werden, wenn er im Training sinnvoll ist.



Mindestbedingungen:



\* positive Netto-Performance nach Fees

\* ausreichende Aktivität für den jeweiligen Zeitraum

\* keine extreme Instabilität

\* keine offensichtliche Kostenfalle

\* keine Lookahead-Abhängigkeit

\* keine Blindtest-Optimierung



Für Smoke-Test gilt:



Smoke darf zeigen, dass Kandidaten existieren und getestet werden.



Smoke darf aber keine Live-Freigabe erzeugen.



\## Best-Candidates



Auch wenn kein Kandidat trade\_allowed wird, müssen Best-Candidates gespeichert werden:



\* best\_activity\_candidate

\* best\_edge\_candidate

\* best\_balanced\_candidate

\* best\_fee\_survivor\_candidate

\* best\_target\_candidate



Diese Kandidaten sind Diagnose, nicht automatisch handelbar.



Für jeden Best-Candidate muss sichtbar sein:



\* Entry-Familie

\* Parameter

\* TP/SL/Hold

\* Trades pro Tag

\* aktive Tage

\* Training-Netto

\* Fees

\* Profit-Factor

\* Rejection-Grund

\* Abstand zum Ziel



\## Zielrichtung im Smoke-Test



Ein 7-Tage-Smoke muss nicht profitabel sein.



Aber er soll zeigen, ob der Strategie-Kern in die richtige Richtung sucht.



Für 7 Tage Blindtest ist grobe Orientierung:



\* 0 Trades: Warnsignal

\* 1 bis 6 Trades: viel zu wenig Aktivität

\* 7 bis 20 Trades: minimale Aktivität

\* 21 bis 42 Trades: Zielrichtung sichtbar

\* 42 bis 70 Trades: hohe Aktivität, Kosten kritisch prüfen

\* über 70 Trades: möglicherweise overactive, Kosten sehr kritisch prüfen



Diese Werte sind keine harten Gewinnregeln, sondern technische Orientierung.



\## Zielrichtung im Full-Backtest



Der Full-Backtest ist maßgeblich für echte Bewertung.



365 Tage Blindtest:



\* 0 Trades: Fehlerzustand oder vollständig zu begründen

\* unter 365 Trades: sehr geringe Aktivität

\* 365 bis 1095 Trades: mögliche Basis

\* 1095 bis 2190 Trades: Zielrichtung

\* 2190 bis 3650 Trades: hohe Aktivität

\* über 3650 Trades: Kosten/Overtrading kritisch



\## Robustness



Robustness muss trainingsbezogen sein.



Für kurze Smoke-Fenster darf Robustness nicht automatisch jeden Kandidaten töten.



Für Full-Backtest darf Robustness strenger sein.



Wichtig:



\* Smoke ist technischer Kurzlauf.

\* Full ist Bewertungsgrundlage.

\* Live-Freigabe kommt erst später.



\## Kein Blindtest-Lernen



Der Router darf im Blindtest nichts lernen.



Nicht erlaubt:



\* Kandidaten nach Blindtest-Ergebnis auswählen

\* Parameter im Blindtest ändern

\* nachträglich Trade-Filter aus Blindtest ableiten

\* Blindtest-Ergebnis in Training zurückschreiben



\## Keine Fake-Trades



Der Router darf keine Trades erzeugen, nur um Aktivität zu zeigen.



Trades müssen aus echten Entry-/Exit-Regeln entstehen.



Nicht erlaubt:



\* zufällige Trades ohne Regel

\* künstliche Gewinner

\* nachträglich ausgewählte Entry-Zeitpunkte

\* manuelles Einfügen von Trades



\## Alte Strategie



Der alte Cluster-/Opportunity-Router darf als Referenz oder Diagnose erhalten bleiben.



Er darf aber nicht heimlich als Zielstrategie weitergeflickt werden.



Wenn er noch existiert, muss klar sein:



\* legacy

\* nicht neuer Zielkern

\* keine versteckte Fallback-Handelslogik



\## Neuer Zielkern



Neuer Zielkern:



activity\_first\_router



Pflicht:



\* eigener Modulbereich oder klar benannte Dateien

\* Tests

\* UI-/Backtest-Anbindung über gemeinsamen Backtest-Apparat

\* vollständige Reports

\* kein separater Smoke-Codepfad



\## Akzeptanzkriterium für Strategie-Engine



Die Strategie-Engine gilt technisch als brauchbar, wenn:



\* sie Kandidaten in mehreren Aktivitätsklassen erzeugt

\* sie 1 bis 10 Trades/Tag als Suchbereich abdecken kann

\* sie Kosten nach Fees bewertet

\* sie Entry/Exit/TP/SL/Hold testet

\* sie Best-Candidates sichtbar macht

\* sie keine Kandidaten ohne Diagnose verschwinden lässt

\* sie im Smoke-Test technisch nachvollziehbar läuft

\* sie im Full-Backtest ehrlich bewertet werden kann



\## Wichtigste Regel



Der Strategie-Kern muss zuerst Aktivität erzeugen können.



Danach wird entschieden, ob diese Aktivität profitabel ist.



