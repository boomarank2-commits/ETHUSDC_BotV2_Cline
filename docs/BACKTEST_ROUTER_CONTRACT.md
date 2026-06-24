# Backtest-Router-Vertrag ETHUSDC

Full und Smoke sind derselbe Backtest-Vertrag. Nur das Zeitfenster ist anders.

Gleich bleiben: ETHUSDC, USDC, Spot LONG-only, gleiche Engine, gleiche Datenbasis, gleiche Kosten, gleiche Filter, gleicher Kandidatenraum und gleiche Bewertungslogik.

V6 ersetzt Single-Winner-Auswahl durch training-only Top-N-Kandidatenpool. Der Blindtest waehlt nichts aus, sondern prueft den im Training gefundenen Pool.

Poolgroesse: max(2, min(25, ceil(training_days / 14))).

ETH-Regime-Kandidaten werden nicht mehr starr wegen unter 1 Trade pro Tag blockiert. Sie nutzen skalierte Mindestaktivitaet nach Trainingslaenge. Normale Kandidaten behalten die 1-Trade-pro-Tag-Regel.

Ziel: Der 365-Tage-Blindtest soll nicht eine starre 08/15-Strategie pruefen, sondern einen lokal im Training gefundenen Strategiepool je Marktphase. Ziel bleibt 3 USDC pro Tag im 365-Tage-Blindtest, reproduzierbar und ohne Short/Margin/Futures/Leverage.
