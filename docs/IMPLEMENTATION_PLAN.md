# IMPLEMENTATION_PLAN

This file contains the current high-level build plan.

## Current Priority

Fix the shared backtest contract before further result tuning.

The next implementation target is the pool execution bug:
- training may create a selected candidate pool
- blindtest must not add all pool candidates as independent accounts
- candidate signals become proposals
- overlapping proposals are resolved by the router
- one shared account / capital context is simulated
- reports expose raw proposals, executed actions and skipped overlaps

This patch is for the full 730/365 contract. Smoke runs only verify the same mechanism quickly.

## Phase 0 - Project Foundation

Status: done

Goal:
Create clean project structure, rules, memory-bank and minimal truth files.

## Phase 1 - Technical Skeleton

Status: done

Goal:
Create Python project skeleton with config loading, logging, tests and placeholder modules.

## Phase 2 - Data Layer

Status: done enough for current backtest core

Goal:
Load or download ETHUSDC historical data.
Validate time ranges and data quality.

## Phase 3 - Feature Layer

Goal:
Build time-safe features from historical data.

## Phase 4 - Training Layer

Goal:
Find recurring situations in 730 training days.

## Phase 5 - Router Layer

Goal:
Freeze learned situation -> setup/no_trade mapping.

Must include:
- selected candidate pool
- shared account execution
- overlap guard
- no blindtest learning

## Phase 6 - Blindtest Layer

Goal:
Run 365 day blindtest without learning.

The 365 day blindtest is the actual decision basis.

## Phase 7 - Reports

Goal:
Write clear reports explaining trades, no_trade decisions and result quality.

Reports must expose pool execution internals.

## Phase 8 - UI / Paper / Test Trade / Live

Goal:
Only after backtest core is proven.

## Temporary Smoke Runs

1 / 7 / 14 / 30 day runs are temporary technical checks only.

They must never get separate logic. They are shortened versions of the same contract.
