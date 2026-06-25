# ROUTER_TRUTH

This file contains only confirmed router truth.

## Target Chain

Situation -> Cluster -> Router -> Setup -> Trade

Extended current interpretation:

Situation -> Cluster / Regime -> Router -> Setup or no_trade -> Trade

## Situations

A situation is a recurring market moment that can be recognized before entry.

The future result may be used in training as a label.
The future result must not be used as a live/blindtest feature.

## Clusters / Regimes

Clusters or regimes must represent recurring situations.

There is no artificial requirement to create exactly 100 clusters.
100 is only an upper idea, not a target that must be forced.

## Trading Clusters

A final trading cluster must represent a learned profitable or usable LONG opportunity from training.

Forbidden:
- negative clusters as trading clusters
- fake clusters
- clusters created only to satisfy a number
- blindtest-derived clusters

## Router Pool

The router may freeze a pool of selected training candidates.

The pool is not permission to sum all candidate results as if every candidate had a separate account.

Correct blindtest execution:
- candidates produce proposals
- router chooses one action for the same shared time / capital context
- overlapping proposals are skipped or resolved
- no_trade is valid when nothing fits

Required report fields:
- selected_pool_size
- pool_raw_proposals
- pool_executed_trades
- pool_skipped_overlaps
- pool_overlap_guard_used
- selection_policy

## No-Trade

No-Trade is allowed.

No-Trade means:
- no learned setup fits
- cost/risk/edge is not good enough
- current situation is unclear

No-Trade is not a final target cluster.
No-Trade must not hide missing model ability.
