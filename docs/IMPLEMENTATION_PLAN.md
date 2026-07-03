# IMPLEMENTATION_PLAN

Diese Datei ist nur der operative Plan. Die Prioritaet kommt aus `README.md`
und `docs/GPT_CONTINUATION_GUIDE_20260701.md`.

## Current Priority

Der alte Pool-Execution-Bug ist nicht mehr der naechste Auftrag. Der
Pool-Overlap-Guard ist aktiv.

Der alte Datenanschluss-Auftrag ist ebenfalls nicht mehr der Engpass:
ETHUSDC-Basisdaten, Kontextklines, Kline-Orderflow, aggTrade-Minutenfeatures
und Derived Timeframes sind grundsaetzlich vorhanden bzw. im Backtestpfad
anschliessbar.

Aktueller Schwerpunkt:

1. Keine alten Research-Spuren weiter erzwingen:
   Attempt 053, ERRO-L v1, ECMD-L v1 und EPX-L/R2-v2/R2-v3 sind nicht
   integrationsfaehig.
2. ERH-v1 nicht weiter retten. Nach Next-Open-Korrektur ist ERH-v1 klar
   negativ und archiviert.
3. ETH Edge Existence Scan ist der aktuelle Arbeitsanker:
   `eth_edge_existence_scan_20260701` fand Trainingsstruktur ueber 24-72h.
   Top-Befund ist BTC-Risk-On (`btc_4h_drawdown_from_20d_high` q4, 72h),
   plus ETHBTC/ETH-Dip-Reversion-Quintile.
4. `ERV/BRH-v1 = BTC-Risk-On ETH 72h Hold + ETHBTC/ETH-Dip-Reversion-Filter`
   wurde research-only gebaut. Training/Walkforward war stark, aber der frozen
   Blindtest nur schwach positiv: ca. `+0.013 USDC/Tag`.
5. BRH-v1-DIAG wurde gebaut. Ergebnis: keine Threshold-Leakage, kein klarer
   72h-Horizon-Decay, aber starke Blindtest-PnL-Konzentration und Fragilitaet.
   Aktuelle BRH-v1-Form bleibt archiviert.
6. BRH Window Selection Edge Check wurde gebaut. Ergebnis:
   `window_selection_edge_found`, 3 passing Varianten. Die alte v1-Auswahl
   `erv_risk_on_orderflow_cooldown_72h` ist weiterhin bester training-only
   Window-Selector gegen die naive BTC-Risk-On-Baseline. Weil genau diese
   Variante bereits frozen blindgetestet wurde und nur schwach positiv war,
   bleibt sie archiviert.
7. BRH Selection Edge Robustness v2Check wurde gebaut. Ergebnis:
   `new_training_only_candidate_found`, genau 1 passing Variante:
   `brh_btc_risk_on_72h`. Die alte v1-Auswahl scheitert an Mindesttrades,
   worst Fold und PF-Overfit-Obergrenze.
8. BRH BTC-Risk-On Frozen Blindtest wurde gebaut. Ergebnis:
   `frozen_research_blindtest_completed`, positiv aber nicht robust:
   ca. `+10.62 USDC`, `+0.029 USDC/Tag`, 26 Trades, PF ca. `1.26`,
   Leave-two-out PF ca. `0.85`, Top-2 Share ca. `157.6%`.
9. Kein UI-Full-Backtest und keine Router-Integration aus BRH/ERV ableiten.
10. BRH/ERV ist geschlossen.
11. EREM Exposure Edge Check wurde gebaut. Ergebnis:
    `erem_training_edge_found`, genau 1 passing Variante:
    `erem_btc_drawdown_q35_or_ema_below0`. Training/Walkforward zeigt
    robuste Drawdown-/Exposure-Verbesserung gegen Buy-and-Hold.
12. EREM Frozen Blindtest wurde gebaut. Ergebnis:
    `erem_frozen_blindtest_completed`, EREM `-0.53 USDC` vs.
    Buy-and-Hold `-37.00 USDC`, MaxDD `58.69` vs. `140.05 USDC`,
    robust verteilte Avoided-Loss-Bloecke.
13. EREM ist kein 3-USDC/Tag-Profit-Alpha, sondern ein bestaetigtes
    ETH-Exposure-/Drawdown-Management-Thema.
14. Nach Nutzer-Klarstellung (`3 USDC/Tag` ist Wunsch/Zielwert, kein
    Versprechen) wurde EREM als defensives Zwischenziel akzeptiert und minimal
    in den gemeinsamen `activity_first_router` integriert:
    `erem_defensive_router_v1_1_hourly_aligned_20260702`.
    Die minimale EREM-Router-Integration ist damit umgesetzt, aber noch nicht
    durch einen neuen UI-Full-Backtest bewertet.
    Run `run_20260702_201035` war noch kein EREM-Urteil: EREM blockierte
    wegen zu strengem 1h-Execution-vs-Minuten-Split-Guard
    (`erem_execution_context_does_not_cover_split`) und der alte Pool lief.
    Dieser Guard ist jetzt durch Hourly-Alignment mit maximal 2h Randtoleranz
    ersetzt.
15. Neuer UI-Full-Backtest `run_20260703_100717` lief danach korrekt mit
    EREM:
    `erem_exposure_management / erem_btc_drawdown_q35_or_ema_below0`.
    Ergebnis: ca. `-9.51 USDC`, `-0.026 USDC/Tag`, 100 Exposure-Segmente.
    EREM war defensiver als ETH Buy-and-Hold (`-34.88 USDC`, MaxDD ca.
    `130.76 USDC`), aber absolut negativ und nicht uebernahmefaehig.
16. Kleiner Report-Fix danach: EREM-Router-Result verwendet fuer MaxDD den
    mark-to-market Drawdown aus `blindtest_metrics.erem_maxdd_pct`; UI-Label
    `Kein robuster Kandidat` wurde zu `Kein freigegebener Router-Kandidat`
    praezisiert.
15. VEC-v1 Exhaustion Scan wurde gebaut. Ergebnis:
    `no_vec_training_edge`, 0/4 Varianten passing. Die 15m/1h
    Selling-Exhaustion-Idee erzeugte nur 2-6 Validation-Trades je Variante
    und scheiterte an Mindesttrades, Fold-Stabilitaet, Leave-two-out-PF,
    Top-2-Konzentration und Worst-Fold.
16. Kein frozen VEC-Blindtest und keine
    Router-Integration aus VEC-v1 ableiten.
17. AFP-v1 Flow Persistence Scan wurde gebaut. Ergebnis:
    `afp_sanity_failed`, 0/6 Sanity-Folds passing. Die echte aggTrade-
    Kernspur hatte vollstaendige Daten, aber buy-flow persistence lieferte
    nach Kosten in keinem Fold positive Top-Quintile-Forward-PnL.
18. Kein AFP-Variantenlauf, kein frozen AFP-Blindtest und keine
    Router-Integration aus AFP-v1 ableiten.
19. Naechster sinnvoller Lauf: UI-Full-Backtest starten, um nur die neue EREM-
    Router-Integration im echten 730/365-Pfad zu messen.
20. Training/Walkforward muss zuerst Ziel-vor-Stop, Kostenrobustheit,
   Fold-Stabilitaet und genug Trades zeigen.
21. Jede weitere Profit-Alpha-Integration in den gemeinsamen
   `activity_first_router` erst nach Research-only Evidenz.

Keine Datenquelle und keine Strategie wird routerwirksam, nur weil sie
heruntergeladen oder als Idee formuliert wurde.

## Phase 0 - Project Foundation

Status: done

Goal: clean project structure, rules, memory-bank and truth files.

## Phase 1 - Technical Skeleton

Status: done

Goal: Python project skeleton with config, logging, tests and base modules.

## Phase 2 - Data Layer

Status: automatic availability layer implemented; feature adoption remains staged

Implemented availability:

- ETHUSDC, BTCUSDC, ETHBTC, ETHUSDT and USDCUSDT 1m klines
- complete Binance kline order-flow columns
- ETHUSDC exchange_info
- compact official ETHUSDC aggTrade minute features
- append-only live ETHUSDC spread/depth collection

GitHub stores code/tests/docs, not raw downloaded data.

## Phase 3 - Feature Layer

Status: partial

Implemented:

- ETHUSDC 1m base features
- lookahead-safe derived timeframes 5m, 15m, 30m, 1h, 4h, 1d
- HTF training edge diagnostics for winner/loser separation
- research-only ETH Edge Existence Scan ueber vorhandene ETH/BTC/Orderflow/
  Basis-Features und Forward-Horizonte 1h/4h/12h/24h/72h
- research-only BRH/ERV-v1 Walkforward mit 72h fixed hold, foldweise
  kalibrierten Quantilen, Next-Open Entry und one-position-at-a-time
- research-only BRH-v1-DIAG fuer Threshold-Verifikation, Distribution Shift,
  Horizon Decay, Konzentration und Selection-Forensics
- research-only BRH Window Selection Edge Check gegen einfache BTC-Risk-On-
  Baseline innerhalb derselben Training/Walkforward-Folds
- research-only BRH Selection Edge Robustness v2Check mit Random-/Buy-Hold-
  Baseline, Konzentrationsstrafe, Leave-one/two-out PF, PF-Overfit-Obergrenze
  und No-Repeat-Regel fuer bereits blindgetestete Varianten
- research-only frozen Blindtest fuer genau `brh_btc_risk_on_72h`; Ergebnis
  positiv, aber nicht robust genug fuer Router/UI
- research-only EREM Exposure Edge Check und Frozen Blindtest fuer
  `erem_btc_drawdown_q35_or_ema_below0`; Ergebnis robust gegen Buy-and-Hold,
  aber nicht als 3-USDC/Tag-Profit-Alpha
- minimale EREM-Integration im gemeinsamen Routerpfad
  `erem_defensive_router_v1_1_hourly_aligned_20260702`; nur defensives ETH-Exposure-
  Management, keine Profit-Alpha-Behauptung
- research-only VEC-v1 Exhaustion Scan auf geschlossenen 15m/1h Bars mit
  ETHUSDC Kline-Orderflow; Ergebnis `no_vec_training_edge`, nicht
  integrationsfaehig
- research-only AFP-v1 Flow Persistence Scan auf echten ETHUSDC aggTrade-
  Minutenfeatures; Ergebnis `afp_sanity_failed`, kein Variantenlauf und nicht
  integrationsfaehig

Next:

- BRH/ERV nicht weiter anfassen.
- VEC-v1 und AFP-v1 nicht retten und nicht integrieren.
- Keinen weiteren Full-Backtest derselben EREM-Logik starten; der echte
  Full-Befund liegt vor und ist nicht uebernahmefaehig.
- Naechster Schritt: externe/Arena-Analyse oder neuer research-only
  Profit-Alpha-Scan. EREM nur als defensiven Vergleich behalten, nicht ueber
  Gates tunen.
- Erwartung ehrlich halten: Ziel/Wunsch bleibt `3 USDC/Tag`, aber EREM soll
  zuerst Risiko/Drawdown gegen ETH Buy-and-Hold verbessern, nicht Profit
  versprechen.
- Nach dem Full-Run den neuen Reportordner analysieren:
  `activity_first_router_report.json`,
  `router_artifact.erem_defensive_router_integration`,
  Summary-Zahlen und Trade-Ledger.
- Spread/depth only after at least 30 real days of validated local collection.

## Phase 4 - Training Layer

Status: active development

Goal: find recurring Ethereum situations in 730 training days.

Required:

- optimize only on training data
- choose candidate/pool only from training evidence
- no blindtest learning
- no direct 7/14/30 tuning
- no artificial trade forcing

## Phase 5 - Router Layer

Status: active development

Goal: freeze learned situation -> setup/no_trade mapping before blindtest.

Current router core:

- activity_first_router
- multi-candidate pool
- shared account execution
- one_position_at_a_time overlap guard
- HTF diagnostics, not yet HTF gate/score decisions

## Phase 6 - Blindtest Layer

Status: active development

Goal: run 365 day blindtest without learning.

The 365 day blindtest is the actual decision basis.

## Phase 7 - Reports

Status: active development

Reports must expose:

- selected_pool_size
- pool_raw_proposals
- pool_executed_trades
- pool_skipped_overlaps
- pool_overlap_guard_used
- data available vs data used
- HTF training edge diagnostics
- best/worst day
- best/worst month
- positive/negative/neutral days
- target ratio to 3 USDC/day

## Phase 8 - UI / Paper / Test Trade / Live

Status: UI backtest control active; trading control locked

Current:

- UI/Controller starts Smoke and Full through the same path.
- Backtest start performs central data ensure first.

Locked until full validation:

- Paper trading
- Test trade
- Live trading
- real order execution

## Temporary Smoke Runs

1 / 7 / 14 / 30 day runs are temporary technical checks only.

They must never get separate logic. They are shortened versions of the same contract.

## Monthly Workflow Target

After an accepted 365-day blindtest:

1. User reviews and consciously accepts or rejects the candidate.
2. The accepted configuration is used for the coming month.
3. Next month, local data is updated.
4. The 3-year window is rebuilt.
5. The first 2 years are training/optimization.
6. The last 1 year is blindtest.
7. A new candidate is accepted only after conscious user approval.
