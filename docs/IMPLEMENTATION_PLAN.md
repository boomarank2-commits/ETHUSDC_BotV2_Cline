# IMPLEMENTATION_PLAN

Diese Datei ist nur der operative Plan. Die Prioritaet kommt aus `docs/CURRENT_TRUTH_MAP.md`.

## Current Priority

Der alte Pool-Execution-Bug ist nicht mehr der naechste Auftrag. Der Pool-Overlap-Guard ist bereits aktiv.

Aktueller Schwerpunkt:

1. Vollstaendigen UI-/Controller-nahen Datenaufbau durchlaufen lassen.
2. Sicherstellen, dass Smoke und Full denselben Daten-, Feature-, Router- und Simulationspfad nutzen.
3. Reports auswerten: Datenstatus, Data Overview, HTF Training Edge Diagnostics.
4. Training-only pruefen, welche Datenquellen Gewinner und Verlierer trennen.
5. Erst danach einzelne belegte Metriken als Score-/Gate-Kandidat in den Router einbauen.

Keine Datenquelle wird nur deshalb routerwirksam, weil sie heruntergeladen wurde.

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

Next:

- Add feature adapters one source at a time only after the current full report proves availability and quality.
- Candidate sources: kline order-flow fields, aggTrade minute features, ETHUSDT/USDCUSDT context, BTCUSDC/ETHBTC context.
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
