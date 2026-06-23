# Aktueller technischer Stand 2026-06-21

- Letzter analysierter Run: `run_20260621_070352`.
- Ergebnis: `-2.398 USDC`, 12 Trades, Ziel `3.0 USDC/Tag` nicht erreichbar mit aktueller Aktivität.
- Hauptblocker: Cluster Router ist technisch aktiv, aber zu inaktiv / mathematisch nicht zielerreichend; 12 Trades/Jahr würden `91.25 USDC` Netto pro Trade benötigen.
- Patch danach: Target-Math-Diagnose, Trade-MFE/MAE-Diagnose, strengere Statusnamen und persistente Runtime/ETA-Felder in `progress.json`.
- Nächster Schritt: neuer UI-Backtest mit 100 USDC, Profil normal, 730d Training, 365d Blindtest, kein Live, keine echten Orders.

# Auftrag an Clean/Cline: Warum erreicht der letzte Backtest nicht 3 USDC/Tag?

## Ziel dieses Audits

Bitte analysiere den letzten abgeschlossenen Backtest vollständig und ehrlich.

Ziel ist NICHT, sofort blind zu patchen.

Ziel ist zuerst:
- verstehen, warum der Blindtest mit 100 USDC Einsatz nicht ca. 3 USDC/Tag erreicht
- beweisen, an welcher Stelle die Pipeline bricht
- prüfen, ob alle notwendigen Daten vorhanden sind
- prüfen, ob vorhandene Daten wirklich benutzt werden
- prüfen, ob Live-/Microstructure-Daten korrekt gesammelt, freigegeben oder blockiert werden
- prüfen, ob Strategie, Cluster, Router, Setup-Lernen oder Engine das Problem sind
- danach erst gezielt umsetzen

Keine Gate-Lockerung. Keine Fake-Trades. Keine erzwungenen Trades. Kein Schönreden. Keine neue Parallelarchitektur.

---

## 1. Letzten Lauf eindeutig bestimmen

Bitte zuerst den letzten abgeschlossenen Backtest eindeutig bestimmen:

- run_id
- Startkapital
- Risiko-/Aggressionsprofil
- Zeitbudget
- Status
- Run-Klassifikation
- technischer Abschluss ja/nein
- fachlich vollständiger Backtest ja/nein
- result_reliability_class
- readme_compliant_full_search_completed
- target_model_alignment
- target_model_gaps

Kernfrage:
War dieser Lauf überhaupt belastbar genug, um zu sagen: „Der Bot schafft keine 3 USDC/Tag“?
Oder war es nur ein Minimal-/Diagnoselauf?

---

## 2. Zielwert prüfen

Bitte auswerten:

- blindtest_total_profit_usdc
- blindtest_usdc_per_day
- total_trades
- trades_per_day
- win_rate
- profit_factor
- total_fees_usdc
- total_slippage_usdc
- gross_profit_usdc
- net_profit_usdc
- max_drawdown
- beste/schlechteste Tage
- beste/schlechteste Monate

Fragen:
- Wie weit ist der Lauf von 1 USDC/Tag entfernt?
- Wie weit ist der Lauf von 3 USDC/Tag entfernt?
- Ist das Problem zu wenig Aktivität?
- Ist das Problem negative Netto-Edge?
- Ist das Problem Fees/Slippage?
- Ist das Problem falscher Exit?
- Ist das Problem falscher Entry?
- Ist das Problem, dass kein Router-Setup entsteht?

---

## 3. Datenprüfung: Ist alles Notwendige vorhanden?

Bitte alle Datenquellen prüfen:

Pflichtdaten:
- ETHUSDC 1m Klines
- BTCUSDC 1m Klines
- ETHBTC 1m Klines
- Exchange Info
- Fee-Modell
- Slippage-Modell
- Binance-Regeln
- Tick Size
- Step Size
- Min Notional

Zusätzliche Daten:
- ETHUSDC AggTrades
- ETHUSDC Trades
- BookTicker
- Orderbuch-Snapshots
- Microstructure-Features
- Tradeflow-Features
- Taker-Pressure-Features

Für jede Datenquelle ausgeben:

- vorhanden ja/nein
- Pfad
- Zeitraum
- Zeilen/Datensätze
- Abdeckung in Tagen
- Mindesthistorie erreicht ja/nein
- aktuell ja/nein
- älter als 7 Tage ja/nein
- validiert ja/nein
- included_in_backtest ja/nein
- diagnostic_only ja/nein
- positive_candidate_influence_allowed ja/nein
- Grund falls nicht benutzt

---

## 4. Werden alle vorhandenen Daten wirklich benutzt?

Bitte nicht nur prüfen, ob Daten existieren.

Bitte prüfen, ob sie wirklich im Backtest wirken:

- beeinflussen sie Situation-Cluster?
- beeinflussen sie Entry?
- beeinflussen sie Exit?
- beeinflussen sie Router?
- beeinflussen sie Setup-Lernen?
- beeinflussen sie Kandidatenbewertung?
- beeinflussen sie Rejections?
- beeinflussen sie Similarity?
- beeinflussen sie Fees/Slippage?
- beeinflussen sie No-Trade?

Für jede Datenquelle klar ausgeben:

```text
Datenquelle:
Status:
Im Backtest verwendet:
Wo im Code verwendet:
Welche Features daraus entstehen:
Welche Entscheidung sie beeinflusst:
Wenn nicht verwendet: Warum?
```

---

## 5. Live-/Microstructure-Daten prüfen

Bitte besonders prüfen:

- werden AggTrades live/historisch heruntergeladen?
- werden Trades live/historisch heruntergeladen?
- wird BookTicker gesammelt?
- werden Orderbuch-Snapshots gesammelt?
- läuft der Collector?
- läuft er auch ohne UI?
- werden Daten fortlaufend gespeichert?
- gibt es Mindesthistorie 30 Tage / 90 Tage?
- ab wann werden diese Daten im Training freigegeben?
- ab wann werden diese Daten im Backtest verwendet?
- werden sie aktuell nur diagnostisch verwendet?
- warum?

Wichtig:
Wenn nur 1 Monat Live-Daten vorhanden ist:
- dürfen diese Daten nur im passenden Zeitraum des 2-jährigen Trainings genutzt werden
- sie dürfen nicht rückwirkend für 2 Jahre simuliert werden
- sie dürfen nicht im Blindtest positiv wirken, wenn sie im entsprechenden Zeitraum nicht vorhanden waren
- sie dürfen nicht als Lookahead wirken

Bitte prüfen:
Ist diese Zeitlogik korrekt umgesetzt?

---

## 6. Ablauf prüfen: läuft die komplette Pipeline?

Bitte die komplette Pipeline anhand des letzten Runs prüfen:

```text
UI Start
-> runtime_config
-> Datenprüfung
-> Download/Update
-> Validierung
-> Feature-Build
-> Opportunity-Events
-> Situation-Cluster
-> Setup-Lernen
-> Spezialisten-Freigabe
-> Router-Freeze
-> Blindtest
-> Engine
-> Trades
-> Reports
```

Für jeden Schritt ausgeben:

- erfolgreich ja/nein
- Report vorhanden ja/nein
- relevante Kennzahl
- nächster Blocker

Besonders prüfen:

- opportunity_event_count
- candidate_situation_count
- tested_candidates
- valid_candidates
- final_profitable_specialist_cluster_count
- trade_allowed_setup_count
- router_setup_count
- router_trade_signals
- engine_entry_attempts
- engine_entry_executions
- trades

Kernfrage:
Wo bricht die Kette wirklich?

---

## 7. Cluster-/Setup-Lernen prüfen

Bitte detailliert prüfen:

- Wie viele Opportunity-Events wurden gefunden?
- Wie viele Situation-Cluster entstanden?
- Wie viele Cluster wurden im Training aktiv getestet?
- Wie viele Cluster wurden im Blindtest wiedererkannt?
- Wie viele Cluster bekamen ein Setup?
- Wie viele Setups waren trade_allowed?
- Wie viele waren adoption_allowed?
- Wie viele wurden wegen diagnostic_only/research_only blockiert?
- Wie viele scheiterten an training_net_profit_not_positive?
- Wie viele scheiterten an training_activity_floor_not_met?
- Wie viele scheiterten an friction_to_move?
- Wie viele scheiterten an profit_factor?
- Wie viele scheiterten an Recent-Stability?
- Wie viele scheiterten an Overfit?

Kernfrage:
Warum entsteht aus den Clustern kein profitabler Spezialist?

---

## 8. Strategien prüfen

Bitte jede Strategiefamilie einzeln auswerten:

- trend_follow
- trend_pullback
- momentum_breakout
- volatility_breakout
- mean_reversion
- range_reversion
- micro_scalp
- panic_bounce
- session_momentum
- opportunity_cluster_entry
- no_trade_guard

Für jede Strategie:

- Rohsignale
- getestete Kandidaten
- gültige Kandidaten
- beste Trainingsleistung
- beste Blindtestleistung
- Trades/Tag aktiv
- aktive Tage
- win_rate
- profit_factor
- gross_profit
- fees
- slippage
- net_profit
- häufigste Ablehnungsgründe
- ob sie zu breit handelt
- ob sie zu selten handelt
- ob Entry schlecht ist
- ob Exit schlecht ist
- ob Fees/Slippage alles zerstören
- ob sie überhaupt ins Zielmodell passt

Frage:
Muss eine Strategie repariert, ersetzt oder nur als Suchraum behalten werden?

---

## 9. Entry-/Exit-/TP-/SL-/Hold-Analyse

Entry prüfen:
- sind Entries zu früh?
- sind Entries zu spät?
- sind Entries zu breit?
- werden Opportunity-Momente sauber isoliert?
- gibt es zu viele Entries pro Cluster?
- gibt es zu wenige Entries pro Cluster?
- sind Entry-Filter zu streng?
- sind Entry-Filter zu locker?

Exit prüfen:
- TP zu klein?
- TP zu groß?
- SL zu eng?
- SL zu weit?
- Hold-Time falsch?
- Trailing zu früh?
- Trailing zu spät?
- Phase-Shift-Exit sinnvoll?
- Time-Exit zerstört Gewinner?
- Gewinner werden zu früh geschlossen?
- Verlierer laufen zu lange?

Bitte auswerten:
- MFE/MAE
- exit_diagnostics
- loss_analysis
- post_exit_analysis
- quick_loss_clusters
- friction_survivors

Frage:
Was muss an Entry/Exit geändert werden, damit ein Cluster profitabel wird?

---

## 10. Kosten-/Friction-Analyse

Bitte prüfen:

- durchschnittlicher erwarteter Move pro Trade
- durchschnittliche Fees pro Trade
- durchschnittliche Slippage pro Trade
- friction_to_move_ratio
- gross_profit vor Kosten
- net_profit nach Kosten
- welche Strategien brutto positiv aber netto negativ sind
- welche Cluster an Kosten scheitern
- ob Trades zu klein sind
- ob TP zu klein ist
- ob zu viele Micro-Moves gehandelt werden

Frage:
Kann 3 USDC/Tag mit 100 USDC Einsatz technisch erreicht werden, wenn die durchschnittliche Bewegung pro Trade so bleibt?

Wenn nein:
Welche Mindestbewegung pro Trade ist nötig?

---

## 11. Erzwungene Trades prüfen

Bitte explizit prüfen:

- Gibt es erzwungene Trades?
- Gibt es Fallback von Phase auf Strategie?
- Gibt es Trades ohne finalen situation_id-Spezialisten?
- Gibt es Trades durch diagnostic_only-Kandidaten?
- Gibt es Trades durch research_only-Kandidaten?
- Gibt es Fallback auf den besten Verlierer?
- Gibt es Overtrading wegen Aktivitätsziel?

Wichtig:
Schlechter Tag ist schlechter Tag.
Wenn kein Cluster passt, muss no_trade gelten.
Der Bot darf nicht handeln, nur um Trades/Tag zu erfüllen.

---

## 12. Ziel 3 USDC/Tag technisch prüfen

Bitte realistisch berechnen:

Mit 100 USDC Einsatz:

- Wie viele Trades/Tag wären nötig?
- Welcher Nettogewinn pro Trade wäre nötig?
- Welche Bruttobewegung pro Trade wäre nötig?
- Welche Gebühren/Slippage müssen überwunden werden?
- Welche Winrate wäre nötig?
- Welcher Profit-Factor wäre nötig?
- Welche Cluster-Aktivität wäre nötig?
- Wie viele aktive Handelstage wären nötig?

Beispielrechnung im Report ausgeben:

```text
Ziel: 3 USDC/Tag
bei X Trades/Tag
benötigter Netto-Gewinn pro Trade = ...
benötigter Brutto-Move pro Trade = ...
Kosten pro Trade = ...
erforderliche Trefferquote = ...
```

Frage:
Ist 3 USDC/Tag mit aktuellen Daten/Strategien technisch plausibel?
Oder erst mit reifen Microstructure-/BookTicker-/Orderbuchdaten?

---

## 13. Muss der Bot neu gebaut werden?

Bitte ehrlich prüfen:

- Ist die Architektur grundsätzlich richtig?
- Ist die README-Zielkette im Code wiederzufinden?
- Ist der Code zu stark Phase->Strategie statt Situation->Cluster->Router?
- Gibt es zu viele Parallelstrukturen?
- Gibt es tote Reports?
- Gibt es Fake-Features?
- Gibt es Datenpfade, die nur dokumentiert sind, aber nicht wirken?
- Gibt es eine Stelle, die man gezielt reparieren kann?
- Oder ist ein gezielter Neuaufbau der Backtest-Pipeline sinnvoller?

Bitte am Ende klar sagen:

```text
Neu bauen nötig: ja/nein/teilweise
Begründung:
Minimaler nächster Fix:
Größerer sinnvoller Umbau:
Risiko, wenn weiter gepatcht wird:
```

---

## 14. Konkreter Maßnahmenplan

Nach der Analyse bitte eine konkrete Liste erstellen:

### Sofortmaßnahmen
- kleine gezielte Fixes
- ohne neue Architektur
- mit Tests

### Mittelfristige Umbauten
- falls Setup-Lernen verbessert werden muss
- falls Router/Cluster-Logik erweitert werden muss
- falls Datenpipeline erweitert werden muss

### Spätere Maßnahmen
- wenn 30/60/90 Tage Live-Daten vorhanden sind
- BookTicker/Orderbuch/Microstructure stärker einbinden
- Paper/Live-Vergleich

Für jede Maßnahme:

- Datei/Funktion
- Zweck
- erwarteter Effekt
- Risiko
- Test
- Report, der Erfolg beweist

---

## 15. Erst nach Analyse umsetzen

Bitte erst nach der Analyse umsetzen.

Wenn die Analyse eindeutig zeigt, dass ein kleiner Patch reicht:
- Patch machen
- Tests ausführen
- kleinen Smoke-Test
- normalen UI-Backtest vorbereiten/starten

Wenn die Analyse zeigt, dass es größer ist:
- keine halbe Lösung bauen
- Datei `NEXT_IMPLEMENTATION_PLAN.md` erstellen
- dort alle notwendigen Schritte dokumentieren
- danach mit dem Nutzer abstimmen

---

## Pflichtausgabe am Ende

Bitte am Ende exakt diese Zusammenfassung schreiben:

```text
1. Letzter Run:
2. Warum 3 USDC/Tag nicht erreicht:
3. Wichtigster Blocker:
4. Daten vollständig:
5. Daten wirklich benutzt:
6. Live-/Microstructure-Daten Status:
7. Cluster/Setup-Lernen Status:
8. Strategie-Hauptproblem:
9. Entry-/Exit-Hauptproblem:
10. Kosten-/Friction-Hauptproblem:
11. Erzwungene Trades vorhanden:
12. Neu bauen nötig:
13. Minimaler nächster Fix:
14. Größerer Umbau falls nötig:
15. Nächster Backtest-Befehl:
```
