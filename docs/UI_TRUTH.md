# UI_TRUTH

This file contains only confirmed UI truth.

## Current Phase

UI is not part of the first build phase.

The first build phase is the clean backtest core.

## Later UI Goal

The later UI should control and display the bot.
It must not contain trading logic.

## Later Test Trade Goal

A later Test Trade button is planned.

A Test Trade means:
- only after consciously taken-over configuration
- the bot waits for a learned profitable situation
- it executes exactly one complete trade from entry to exit
- it collects as much diagnostic and comparison data as possible
- it documents deviations from backtest expectation, for example later TP/SL trigger, different execution, slippage or timing
- it stops automatically afterwards
- it does not start a second trade

## Forbidden For Now

Do not build:
- Paper trading
- Live trading
- Test trade
- order execution
- UI buttons for trading

until the backtest core, training, router, blindtest and reports are correct.
