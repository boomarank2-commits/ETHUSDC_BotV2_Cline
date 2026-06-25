# BACKTEST_TRUTH

This file contains only confirmed backtest truth.

## Window

The final backtest uses:

- 730 days training / optimization
- then 365 days blindtest

The blindtest is unknown future data from the perspective of training.

Short runs with 1 / 7 / 14 / 30 blindtest days are temporary smoke checks only. They are shortened versions of the same backtest contract.

## Training

Training may:
- find situations
- build clusters / regimes
- test strategies as search space
- optimize local setups
- create a frozen router / candidate pool

Training must not use blindtest data.

## Blindtest

Blindtest may:
- use only the frozen router from training
- execute learned setups
- choose no_trade when no learned setup fits
- report what happened

Blindtest must not:
- learn
- optimize
- change parameters
- create new setups
- use future information

## Shared Pool Execution

A pool may contain multiple selected candidates.

The blindtest still simulates one shared account context.

It is wrong to run each candidate independently and add all candidate results together.

Correct behavior:
- collect candidate proposals from the frozen pool
- sort proposals by time
- resolve overlapping proposals by router / training score
- execute only the selected proposal for that shared time context
- report skipped overlaps

Required visibility:
- selected_pool_size
- pool_raw_proposals
- pool_executed_trades
- pool_skipped_overlaps
- pool_overlap_guard_used
- selection_policy

## Blindtest Purpose

The 365 day blindtest must not only show total profit or loss.

It should later provide an expectation frame for Paper and Live.

The blindtest should later make at least these views analyzable:
- result per month
- best months
- worst months
- positive months
- negative months
- neutral months
- best and worst periods
- normal expected monthly range
- warning signal when Paper or Live after takeover runs clearly outside the blindtest frame

If Paper or Live runs clearly worse than the blindtest frame, this is an analysis trigger.
If Paper or Live runs clearly better than the blindtest frame, this is also an analysis trigger because backtest and live behavior may not be identical.

## Capital Simulation

If the backtest starts with 100 USDC, the result must honestly show what would have happened to that 100 USDC.

There is no early stop only because calculated equity becomes negative.

Negative calculated results must remain visible.

Example:
- Start: 100 USDC
- Result: -1000 USDC

This is allowed as a backtest result because it shows that the strategy would have failed badly.

Do not add hidden protection logic to make results look safer.

## Valid Result

A valid backtest must report:
- training window
- blindtest window
- learned clusters / regimes
- approved setups / selected pool
- router decisions
- trades
- no_trade reasons
- fees / slippage assumptions
- final result
- why the result is or is not usable
