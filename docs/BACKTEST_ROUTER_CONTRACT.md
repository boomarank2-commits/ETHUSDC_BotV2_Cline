# Backtest-Router-Vertrag ETHUSDC

Full und Smoke sind derselbe Backtest-Vertrag. Nur das Zeitfenster ist anders.

Gleich bleiben: ETHUSDC, USDC, Spot LONG-only, gleiche Engine, gleiche Datenbasis, gleiche Kosten, gleiche Filter, gleicher Kandidatenraum und gleiche Bewertungslogik.

Der 365-Tage-Blindtest ist die eigentliche Entscheidungsgrundlage. 1/7/14/30 Tage sind nur technische Kurzpruefungen desselben Mechanismus.

V6 ersetzt Single-Winner-Auswahl durch training-only Top-N-Kandidatenpool. Der Blindtest waehlt nichts aus, sondern prueft den im Training gefundenen Pool.

Poolgroesse: max(2, min(25, ceil(training_days / 14))).

Wichtig: Der Kandidatenpool darf nicht wie mehrere getrennte Konten simuliert werden.

Falsch ist: alle Kandidaten erzeugen separat Ergebnisse und diese Ergebnisse werden addiert.

Richtig ist: alle Kandidaten erzeugen Vorschlaege, der gemeinsame Router entscheidet pro Zeit-/Kapital-Kontext eine Aktion oder no_trade.

Bei ueberlappenden Vorschlaegen darf nur ein Vorschlag ausgefuehrt werden, solange keine ausdrueckliche Kapitalaufteilungsregel existiert.

Reports muessen zeigen: selected_pool_size, pool_raw_proposals, pool_executed_trades, pool_skipped_overlaps, pool_overlap_guard_used und selection_policy.

ETH-Regime-Kandidaten werden nicht mehr starr wegen unter 1 Trade pro Tag blockiert. Sie nutzen skalierte Mindestaktivitaet nach Trainingslaenge. Normale Kandidaten behalten die 1-Trade-pro-Tag-Regel.

Ziel: Der 365-Tage-Blindtest soll nicht eine starre 08/15-Strategie pruefen, sondern einen lokal im Training gefundenen Strategiepool je Marktphase. Ziel bleibt 3 USDC pro Tag im 365-Tage-Blindtest, reproduzierbar und ohne Short/Margin/Futures/Leverage.
