# BACKTEST_TRUTH

This file contains only confirmed backtest truth.

## Window

The backtest uses:

- 730 days training / optimization
- then 365 days blindtest

The blindtest is unknown future data from the perspective of training.

## Training

Training may:
- find situations
- build clusters
- test strategies as search space
- optimize local setups
- create a frozen router

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
- learned clusters
- approved setups
- router decisions
- trades
- no_trade reasons
- fees / slippage assumptions
- final result
- why the result is or is not usable
