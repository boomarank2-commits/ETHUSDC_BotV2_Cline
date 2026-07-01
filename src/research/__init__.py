"""Research-only strategy experiments.

Modules in this package are not production router logic. They may read local
raw data and write ignored local reports, but they must not create live orders
or change the shared UI backtest path unless a later, explicit integration step
is approved.
"""
