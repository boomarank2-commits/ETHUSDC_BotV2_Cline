# FINAL_ONE_YEAR_BLINDTEST_TRUTH

This file is the first file every agent must read.

## Final target

The project target is one adaptive ETHUSDC Spot LONG-only system validated by one full backtest contract.

The final proof is:

- 730 days training / optimization
- then 365 days blindtest
- ETHUSDC
- USDC quote basis
- Binance Spot assumptions
- no short
- no margin
- no futures
- no leverage
- no blindtest learning
- no lookahead

## Smoke runs are temporary

1 day, 7 day, 14 day and 30 day runs are only shortened technical checks of the same full backtest contract.

They are not separate systems, not separate engines, not separate routers, not separate strategies and not final decision criteria.

When the 365 day blindtest workflow is proven and accepted, these smoke windows should no longer matter for the final decision process.

## One shared account rule

The strategy pool may contain many candidates.

But the simulation has one shared account context.

Wrong:

- candidate A uses the full stake
- candidate B also uses the full stake at the same time
- candidate C also uses the full stake at the same time
- all results are added as if each candidate had its own capital

Correct:

- training builds a candidate / situation / regime pool
- blindtest freezes that pool
- blindtest treats candidate signals as proposals
- overlapping proposals compete
- only one position is allowed for the same shared capital/time context unless a later explicit capital-allocation rule exists
- if no learned situation is good enough, no_trade is valid

## Adaptive meaning

Adaptive does not mean inventing untested rules during blindtest.

Adaptive means:

- training learns market situations and matching setups
- blindtest recognizes current situation from already-known features
- router chooses one of the trained actions: setup A, setup B, setup C, or no_trade
- blindtest never changes parameters after seeing blindtest results

## What must be patched now

Any current pool execution that sums all candidate results together is wrong.

The next implementation must make pool execution one shared simulation:

- collect proposals from selected training candidates
- sort by time
- resolve overlapping proposals by training score / router decision
- execute only the chosen proposal for that shared time context
- report raw proposals, executed trades and skipped overlaps

## Required report fields

Reports must make this visible:

- contract_version
- router_version
- selection_policy
- selected_pool_size
- selected candidates
- pool_raw_proposals
- pool_executed_trades
- pool_skipped_overlaps
- pool_overlap_guard_used
- training_days
- blindtest_days
- run_type

## Final acceptance

The bot is not finished because unit tests are green.

The bot is finished only when:

- the full 730/365 contract is implemented
- the 365 day blindtest is acceptable
- reports prove how the result was achieved
- the user consciously accepts the result for the next phase
- later behavior follows the same frozen logic
