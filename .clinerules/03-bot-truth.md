# Bot Truth

Project:
ETHUSDC Adaptive Spot LONG-only Bot V2.

Hard truth:
- Symbol: ETHUSDC
- Quote/capital basis: USDC
- Binance Spot only
- LONG only
- No short
- No futures
- No margin
- No leverage

Backtest principle:
- 730 days training / optimization
- then 365 days blindtest
- blindtest must not be used for training, optimization, parameter selection or learning

Target model:
Situation -> Cluster -> Router -> Setup -> Trade

Strategies:
- are search space only
- are not the final target model

Clusters:
- no artificial requirement to create 100 clusters
- no negative clusters as trading clusters
- No-Trade is allowed, but not a final target cluster

Backtest capital:
- start for example with 100 USDC
- backtest must honestly show what would have happened
- no early capital stop only because of calculated loss
- negative calculated results must remain visible

UI/Paper/Live:
- come later
- first the backtest core must be clean
