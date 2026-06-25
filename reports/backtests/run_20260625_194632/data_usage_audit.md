# Data Usage Audit – run_20260625_194632

Stand: 2026-06-25  
Scope: Part 1 – Diagnose und Daten-Nutzung. Keine Gate-, Strategie- oder Feature-Änderung.

## Kurzfazit

Der Full-Run ist technisch korrekt abgeschlossen. Die 0 Trades sind kein Datenfehler
und kein fehlgeschlagener Backtestlauf. Der `activity_first_router` hat 392 Kandidaten
im Training vollständig geprüft, aber keinen als `trade_allowed` zugelassen. Deshalb
blieb `selected_pool_size = 0`, es entstanden keine Blindtest-Proposals und der
Blindtest führte absichtlich keine Strategie aus.

Der beste positive Training-Kandidat erreichte:

- 277 Trades an 170 aktiven Tagen
- 5,2516 USDC Training-Netto-PnL in 730 Tagen
- 0,007194 USDC/Tag
- 60,6429 USDC Brutto-PnL
- 55,3913 USDC Gebühren
- Fee/Gross-Ratio 0,9134 bei erlaubtem Maximum 0,70
- Profit Factor 1,0197 bei gefordertem Minimum 1,03
- Max Drawdown 26,84 % bei erlaubtem Maximum 25 %

Der zuerst greifende Ablehnungsgrund war `rejected_by_fees`. Auch ohne diesen
ersten Gate-Treffer hätte derselbe Kandidat anschließend Profit-Factor- und
Drawdown-Gate nicht bestanden. Die Training-Edge ist zudem weit vom Ziel
3 USDC/Tag entfernt.

## Router-Diagnose

### Kandidatenraum

- `candidate_count`: 392
- `setup_test_count`: 392
- `trade_allowed_setup_count`: 0
- `selected_pool_size`: 0
- `pool_raw_proposals`: 0
- `pool_executed_trades`: 0
- `pool_skipped_overlaps`: 0
- `candidate_space_status`: `trade_allowed_blocked`
- `selection_reason`: `diagnostic_only_no_trade_allowed_candidate`
- `blindtest_strategy_executed`: false

### Rejection Counts

| Ablehnungsgrund | Anzahl | Interpretation |
|---|---:|---|
| `rejected_by_training_net` | 124 | Training nach Kosten nicht positiv |
| `rejected_by_fees` | 153 | Gebührenquote beseitigt oder dominiert die Edge |
| `rejected_by_activity` | 27 | Allgemeine Kandidaten unter Aktivitätsfloor |
| `rejected_by_overactivity` | 88 | Mehr als 10 Trades/Tag |
| `rejected_by_target_math` | 0 | Target-Math blockierte keinen Kandidaten |
| `rejected_by_profit_factor` | 0 | Kein zuerst gemeldeter PF-Gate-Treffer |
| `rejected_by_drawdown` | 0 | Kein zuerst gemeldeter Drawdown-Gate-Treffer |
| `rejected_by_robustness` | 0 | Kein Robustness-Gate-Treffer |
| `rejected_by_precheck` | 0 | Kein Kandidat wurde vor der Simulation verworfen |
| übrige Gründe | 0 | Kein Context-, Dedup- oder sonstiger Blocker |

Die Gates werden sequenziell ausgewertet. Deshalb erscheint der beste positive
Kandidat nur unter `rejected_by_fees`, obwohl seine Kennzahlen anschließend auch
Profit Factor und Drawdown nicht erfüllen würden.

### Search Pass Summary

| Pass | Generiert/getestet | Positive Training-Netto-Kandidaten | Aktiv genug | Trade allowed |
|---|---:|---:|---:|---:|
| `activity_first` | 90 | 0 | 90 | 0 |
| `edge_expansion` | 120 | 0 | 102 | 0 |
| `eth_regime_discovery` | 150 | 4 | 150 | 0 |
| `fee_rescue` | 32 | 0 | 23 | 0 |

Alle vier positiven Kandidaten kamen aus `eth_regime_discovery`. Der beste davon
war zugleich `best_edge_candidate`, `best_fee_survivor_candidate` und
`best_target_candidate`, wurde aber wegen der Gebührenquote nicht zugelassen.

### Best Candidates

| Rolle | Training USDC/Tag | Trades/Tag | Netto-PnL | Ablehnung |
|---|---:|---:|---:|---|
| Best Activity | -10,341556 | 51,1726 | -7.549,34 | `rejected_by_overactivity` |
| Best Edge | +0,007194 | 0,3795 | +5,25 | `rejected_by_fees` |
| Best Balanced | -0,007907 | 0,2027 | -5,77 | `rejected_by_activity` |
| Best Fee Survivor | +0,007194 | 0,3795 | +5,25 | `rejected_by_fees` |
| Best Target | +0,007194 | 0,3795 | +5,25 | `rejected_by_fees` |

## Prüfung der vermuteten Blocker

### Starre 1-Trade-pro-Tag-Regel

Ja, für allgemeine Activity-/Edge-/Fee-Rescue-Kandidaten existiert weiterhin
`trades_per_day >= 1.0` als harte Aktivitätsregel.

Für `eth_regime_discovery` greift jedoch die aktive ETH-Skalierung:

- im 730-Tage-Training maximal 20 erforderliche Trades
- mindestens 10 aktive Tage

Alle 150 ETH-Regime-Kandidaten bestanden diese skalierte Aktivitätsprüfung.
Die vier positiven Training-Kandidaten lagen in diesem ETH-Pass. Die starre
1-Trade/Tag-Regel war deshalb **nicht die Ursache** für 0 Trades in diesem Run.

### Target-Math

`rejected_by_target_math = 0`. Target-Math hat keinen Kandidaten vorzeitig
blockiert. Das 3-USDC/Tag-Ziel beeinflusst Diagnose/Scoring-Distanz, war aber
kein Zulassungs-Gate dieses Runs.

### Positive Kandidaten vor Router/Blindtest verworfen

Kein Precheck-Fehler: Alle 392 Kandidaten wurden simuliert. Vier Kandidaten waren
nach Kosten positiv. Sie wurden im Router bewertet, bestanden jedoch die
Zulassungsgates nicht. Da nur `trade_allowed` Kandidaten in den Pool dürfen, wurde
kein Blindtest für sie ausgeführt. Das entspricht der aktuellen Selection Policy.

### Fees, Profit Factor und Drawdown

Der beste positive Kandidat scheiterte zuerst am Fee/Gross-Gate. Unabhängig davon
waren Profit Factor und Drawdown ebenfalls knapp außerhalb der aktuellen Grenzen.
Es gibt daher keinen Hinweis, dass ein einzelnes offensichtlich falsches Gate
allein eine robuste Strategie versteckt.

### Smoke-, Cluster-, V1- oder Fallback-Einfluss

- `run_type = full_backtest`
- `legacy_cluster_router_used = false`
- kein `cluster_router_report.json` im Run
- Summary und finales Ergebnis bevorzugen den vorhandenen Activity-First-Report
- Smoke nutzt denselben Pfad, beeinflusst aber diesen Full-Run nicht

Strategy V1 wurde weiterhin als vorgeschalteter Vergleich gerechnet. Es fand
einen Trainingskandidaten und führte 27 Blindtest-Trades aus, verlor dort aber
6,3205 USDC beziehungsweise -0,0173 USDC/Tag. Dieses Ergebnis wurde nicht als
Fallback übernommen und beeinflusste weder Activity-First-Auswahl noch finale
Summary. Strategy V0 war ebenfalls klar negativ.

## Derived-Timeframe Training Edge Analysis

Die HTF-Metriken ändern keine Gates, Scores oder Trades. Sie sind ausschließlich
Training-Diagnose.

| TF | Kandidaten-Trade-Zeilen | Winner-Loser Close Return | Winner-Loser Range | Winner-Loser Volume | Für spätere Prüfung markiert |
|---|---:|---:|---:|---:|---|
| 5m | 2.096.594 | +0,00004133 | +0,00029555 | +107,80 | nein |
| 15m | 2.096.587 | -0,00001112 | +0,00051094 | +352,20 | nein |
| 30m | 2.096.585 | +0,00000211 | +0,00076102 | +659,44 | nein |
| 1h | 2.096.498 | +0,00006766 | +0,00101226 | +1.105,64 | ja |
| 4h | 2.096.167 | +0,00000010 | +0,00227681 | +4.454,93 | ja |
| 1d | 2.093.939 | -0,00084831 | +0,00356320 | +18.959,02 | ja |

Die hohen Sample Counts sind Kandidaten-Trade-Zeilen und enthalten gleiche
Marktzeitpunkte mehrfach über verschiedene Kandidaten. Vor einer Gate-/Score-Nutzung
muss Part 2 die Trennung zusätzlich auf eindeutigen Zeitpunkten beziehungsweise
pro Kandidat stabilisieren. Aktuell ist nur ein mögliches Range-/Volume-Signal
auf 1h/4h/1d sichtbar; das ist noch kein übernehmbarer Handelsbeleg.

## Daten-Nutzungsmatrix

| Datenquelle | Lokal vorhanden | Qualität ok | Freshness ok | Im Data Overview sichtbar | Im Backtest verwendet | Im finalen Router entscheidend | Nur Diagnose | Grund, wenn nicht entscheidend verwendet | Nächster sicherer Schritt |
|---|---|---|---|---|---|---|---|---|---|
| ETHUSDC 1m OHLCV | ja, 1.579.690 Candles | ja, 0 Gaps, Lookback erfüllt | ja, ca. 4,0 h alt | ja, `current` | ja | ja | nein | Primäre Entry-, Exit- und Trainingsbasis | unverändert als Baseline behalten |
| Vollständige Kline-Felder: quote volume, trade count, taker-buy | ja, im ETHUSDC-CSV | teilweise: Spalten vorhanden; kein separater Feld-Gap-/Null-Report | ja, gleiche CSV wie ETHUSDC | ja, `current` | nein | nein | nein | Activity Router liest OHLCV/Base-Volume, nicht diese Zusatzfelder | training-only Winner/Loser-Trennung für Taker-Imbalance und Trade-Intensität |
| ETHUSDC 5m/15m/30m/1h/4h/1d | ja, lookahead-sicher aus 1m abgeleitet | ja, nur vollständig geschlossene Buckets; Counts vorhanden | ja, aus aktuellem ETHUSDC | **nein, keine eigene Data-Overview-Zeile**; im Data Preparation/Router sichtbar | ja, diagnostisch | nein | ja | `changes_trade_gates_or_scores = false` | zuerst 1h/4h/1d Analyse auf eindeutige Zeitpunkte/pro Kandidat stabilisieren |
| BTCUSDC 1m | ja, 1.579.680 | ja, 0 Gaps | ja, ca. 3,5 h alt | ja, `current` | ja, im Strategy-V1-Vergleich | nein | nein | Activity-First-Router erhält keinen BTCUSDC-Kontext | später training-only Kontextwirkung getrennt testen |
| ETHBTC 1m | ja, 1.579.680 | ja, 0 Gaps | ja, ca. 2,8 h alt | ja, `current` | ja, im Strategy-V1-Vergleich | nein | nein | Activity-First-Router erhält keinen ETHBTC-Kontext | später relative ETH-Stärke training-only testen |
| ETHUSDT 1m | ja, 1.579.680 | ja, 0 Gaps | ja, ca. 2,1 h alt | ja, `current` | nein | nein | nein | Nur vorbereitet, keine Feature-Ausrichtung | nach HTF/Orderflow als einzelnes Kontext-Experiment |
| USDCUSDT 1m | ja, 1.579.680 | ja, 0 Gaps | ja, ca. 1,3 h alt | ja, `current` | nein | nein | nein | Nur vorbereitet, keine Feature-Ausrichtung | später Stablecoin-Abweichung training-only prüfen |
| ETHUSDC exchange_info / Filter | ja | ja, ein gültiger Symbol-Datensatz | ja, ca. 128,8 h und damit unter 7 Tagen | ja, `current` | ja | ja, operativ | nein | Rundung von Preis/Menge und Binance-Minimumregeln | beibehalten; Usage-Text im Overview präzisieren |
| ETHUSDC aggTrade-Minutenfeatures | ja, 89 Partitionen bis 2026-06-23 | teilweise: Status vollständig; keine separate Minuten-Gap-Statistik im Run | ja, offizielle 2-Tage-Archivverzögerung eingehalten | ja, `current` | nein | nein | nein | Router lädt/aligned die Partitionen noch nicht | nach Kline-Orderflow eine lookahead-sichere training-only Ausrichtung bauen |
| Spread / BookTicker / Top-20 Depth | ja, Sammlung gestartet; beim Run 5 Samples | nein, unter 30 Tagen und noch nicht gap-validiert | ja, Samples frisch | ja, `collecting` | nein | nein | nein | `usable_for_backtest = false`; keine historische Abdeckung | weiter sammeln; erst ab 30 echten Tagen Qualität/Gaps auditieren |

Zusatz: Raw Trades sind bewusst nicht lokal dupliziert. Der Run meldet sie als
`rejected_redundant_raw_source`, weil aggTrades plus Kline-Trade-Count die
gewählte kompakte Ausgangsbasis bilden.

## Gefundene Bugs / Report-Unschärfen

### 1. Candidate-Space-Text ist ungenau

`candidate_space_reason` lautet:

> positive candidates exist but failed robustness/activity filters

Im Run gab es jedoch `rejected_by_robustness = 0`; der beste positive Kandidat
scheiterte zuerst an Gebühren. Korrekt wäre eine Formulierung wie
`positive candidates exist but failed activity/cost/risk gates`.

Das ist ein kleiner Diagnose-/Reportfehler, kein Ausführungsfehler. In Part 1
wurde er nur dokumentiert.

### 2. `best_fee_survivor_candidate` ist missverständlich benannt

Die Auswahl dafür bedeutet im Code lediglich `training_net_pnl > 0`. Der
ausgewiesene Kandidat hat das eigentliche Fee/Gross-Gate nicht bestanden.
`best_net_positive_candidate` wäre semantisch genauer.

### 3. Data-Overview-„used“ ist nicht gleich finaler Router

BTCUSDC und ETHBTC stehen als `used_in_backtest = true`, weil Strategy V1 im
gemeinsamen Pipeline-Lauf als Vergleich ausgeführt wird. Der finale
Activity-First-Router verwendet beide nicht. Die Zahl „4 used“ darf daher nicht
als „4 Datenquellen beeinflussten die finale Routerentscheidung“ gelesen werden.

### 4. Router-Patch-Layer ist wartungsanfällig

Die sichtbare Basisdatei enthält weiterhin die allgemeine 1-Trade/Tag-Regel.
Zur Laufzeit ersetzt `src/router/__init__.py` die Funktionen durch die
ETH-skalierte Implementierung. Der aktive Full-Run nutzte nachweislich die
Patch-Layer-Funktion. Das ist kein Fehler dieses Runs, erschwert aber Audits und
sollte später konsolidiert werden.

## Gesamtbewertung und Part 2

Es liegt kein Datenqualitäts-, Lookahead-, Smoke-/Full-Pfad- oder Fallback-Bug vor,
der die 0 Trades erklärt. Die 0 Trades entstanden, weil die einzig positiven
Training-Kandidaten zu wenig robuste Netto-Edge nach Kosten und Risiko hatten.

Part 2 ist sinnvoll und sicher möglich, wenn genau eine Datenquelle schrittweise
und ausschließlich training-only untersucht wird. Empfohlene Reihenfolge:

1. HTF-Diagnose 1h/4h/1d gegen doppelte Kandidaten-Zeitpunkte absichern.
2. Danach vollständige Kline-Orderflow-Felder.
3. Danach aggTrade-Minutenfeatures.
4. Danach Kontextmärkte einzeln.
5. Spread/Depth erst nach mindestens 30 echten Tagen.

Part 2 darf zunächst nur Diagnose/Separation ergänzen. Keine Gate-Lockerung,
keine Blindtest-Auswahl und keine gleichzeitige Integration aller Quellen.
