# IMPLEMENTATION_PLAN

Diese Datei ist nur der operative Plan. Die Prioritaet kommt aus `docs/CURRENT_TRUTH_MAP.md`.

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
5. Naechster Schritt ist BRH-v1-DIAG: Train-vs-Blind decay,
   Regime-Distribution-Shift und Threshold-Stabilitaet analysieren. Kein
   zweiter Blindtest und kein Auswahlwechsel auf Basis des Blindtests.
6. Training/Walkforward muss zuerst Ziel-vor-Stop, Kostenrobustheit,
   Fold-Stabilitaet und genug Trades zeigen.
7. Erst danach darf eine minimale Integration in den gemeinsamen
   `activity_first_router` vorbereitet werden.
8. Danach erst UI-Full-Backtest.

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

Next:

- BRH-v1-DIAG bauen: erklaeren, warum 5/7 Varianten im Walkforward eligible
  waren, der eingefrorene Blindtest aber nur schwach positiv war.
- Keine UI/Router-Integration von BRH-v1, solange die Generalisierung nicht
  deutlich naeher an das Ziel kommt.
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
