# IMPLEMENTATION_PLAN

This file contains the current high-level build plan.

## Phase 0 - Project Foundation

Status: current

Goal:
Create clean project structure, rules, memory-bank and minimal truth files.

No bot code yet.

## Phase 1 - Technical Skeleton

Goal:
Create Python project skeleton with config loading, logging, tests and placeholder modules.

No trading logic yet.

## Phase 2 - Data Layer

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
Freeze learned situation -> setup mapping.

## Phase 6 - Blindtest Layer

Goal:
Run 365 day blindtest without learning.

## Phase 7 - Reports

Goal:
Write clear reports explaining trades, no_trade decisions and result quality.

## Phase 8 - UI / Paper / Test Trade / Live

Goal:
Only after backtest core is proven.
