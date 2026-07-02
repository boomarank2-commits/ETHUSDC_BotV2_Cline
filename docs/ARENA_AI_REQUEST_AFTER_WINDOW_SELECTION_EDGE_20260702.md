# Arena.ai Anfrage - nach BRH Window Selection Edge Check

Stand: 2026-07-02

Repository:

```text
https://github.com/boomarank2-commits/ETHUSDC_BotV2_Cline
Branch: spec/activity-first-rebuild-20260623
```

Bitte zuerst lesen, falls Repository-Zugriff moeglich ist:

```text
README.md
AGENTS.md
docs/GPT_CONTINUATION_GUIDE_20260701.md
docs/IMPLEMENTATION_PLAN.md
src/research/brh_v1.py
src/research/brh_v1_diagnostics.py
src/research/brh_window_selection_edge.py
```

## Ziel

ETHUSDC Spot LONG-only auf Binance:

- 100 USDC Einsatzbasis
- 730 Tage Training/Walkforward
- danach maximal ein 365-Tage frozen Blindtest pro sauber freigegebener
  Research-Hypothese
- kein Short, kein Futures/Margin/Leverage
- kein Blindtest-Lernen
- kein Lookahead
- keine echten Orders
- langfristiges Ziel: Richtung `3 USDC/Tag`, aber nur durch robuste Evidenz

## Bisheriger Verlauf kurz

Archiviert/nicht weiter retten:

- Attempt 053: nicht reproduziert
- ERRO-L v1: negativ
- ECMD-L v1: keine robuste Execution
- EPX-L/R2-v2/R2-v3: Path-/Execution-Gates scheiterten
- ERH-v1: nach Next-Open-Korrektur klar negativ

Danach:

1. `eth_edge_existence_scan_20260701`
   - fand Trainingsstruktur ueber 24-72h
   - besonders BTC Risk-On und ETH/ETHBTC-Dip-Reversion
2. `brh_v1_btc_risk_on_eth_reversion_hold_20260701`
   - BTC-Risk-On ETH 72h Hold
   - optionale ETHBTC/ETH/Orderflow-Reversion
   - Signale nur auf geschlossenen 4h-Availability-Rows
   - Entry naechster 1h-Open
   - Exit nach 72h am 1h-Open
   - one-position-at-a-time
   - Quantile je Fold nur aus Training
   - genau ein frozen Blindtest, wenn Walkforward eligible

BRH-v1 Ergebnis:

```text
status = blindtest_completed
eligible_variant_count = 5 / 7
blindtest_candidate_count_evaluated = 1
selected_variant = erv_risk_on_orderflow_cooldown_72h
```

Training/Walkforward selected variant:

```text
total_pnl ~= +135.41 USDC
usdc_per_day ~= +0.246
trades = 45
PF ~= 3.95
```

Frozen Blindtest:

```text
total_pnl ~= +4.65 USDC
usdc_per_day ~= +0.013
trades = 22
PF ~= 1.10
median_trade_pnl ~= -0.37 USDC
max_drawdown ~= 26.58 USDC
```

## BRH-v1-DIAG Befund

Codex baute danach eine reine Post-Mortem-Diagnose:

```text
strategy_version = brh_v1_attribution_decay_diagnostics_20260702
```

Wichtig:

- keine Strategieaenderung
- keine neue Variante
- kein zweiter Varianten-Blindtest
- keine UI-/Router-Integration

Ergebnis:

- Threshold-Recalculation zeigte:
  `thresholds_training_only = true`
  Also kein stiller Quantile-Lookahead gefunden.
- Kein klarer Risk-On-Verfuegbarkeits-Kollaps:
  Risk-On-Bars/Tag Blind vs. Training ca. `0.639`.
- Kein klarer 72h-Horizon-Decay:
  kuerzere Horizonte waren im Blindtest nicht besser als 72h.
- Hauptproblem:
  Blindtest-PnL-Konzentration und Fragilitaet.

Training selected variant:

```text
45 Trades
total ~= +135.41 USDC
median trade ~= +1.95 USDC
top-2 trades share ~= 36.9%
leave-two-out PF ~= 2.86
```

Blindtest selected variant:

```text
22 Trades
total ~= +4.65 USDC
median trade ~= -0.37 USDC
top-1 trade share ~= 337%
top-2 trades share ~= 572%
leave-one-out PF ~= 0.76
leave-two-out PF ~= 0.53
```

Interpretation vor dem naechsten Check:

- BRH-v1 war methodisch sauberer als fruehere Spuren.
- Der positive Blindtest war aber zu schwach und zu konzentriert.
- BRH-v1 bleibt archiviert.
- Keine UI-/Router-Integration.
- Keine erneute Auswahl anhand des gesehenen Blindtests.

## Neuer Check: BRH Window Selection Edge

Auf Basis der externen Hinweise wurde nicht sofort BRH-v2 gebaut. Codex hat
zuerst eine engere training-only Frage umgesetzt:

```text
Hat BRH-v1 im Training/Walkforward bessere ETHUSDC-Exposure-Fenster selektiert
als ein einfacher BTC-Risk-On-Baseline-Hold innerhalb derselben Folds?
```

Dateien:

```text
src/research/brh_window_selection_edge.py
scripts/run_brh_window_selection_edge_check.py
tests/test_brh_window_selection_edge.py
```

Regeln des Checks:

- rein training-only
- verwendet vorhandenen BRH-v1-Report und Validation-Trade-Ledger
- verwendet nur Markt-/Fold-Daten vor dem Blindtest
- kein neuer Blindtest
- keine neue Varianten-Auswahl fuer UI/Router
- keine Strategieparameter aendern
- Baseline: einfacher BTC-Risk-On 72h Hold in denselben Validation-Folds
- Entry/Exit lookahead-sicher:
  Signal auf geschlossener Row, Entry naechster Open, Exit nach `hold_hours`

Lokales Ergebnis:

```text
strategy_version = brh_window_selection_edge_check_20260702
status = window_selection_edge_found
passing_variant_count = 3
selected_v1_variant_id = erv_risk_on_orderflow_cooldown_72h
```

Bester training-only Kandidat nach Window-Selection-Edge:

```text
variant_id = erv_risk_on_orderflow_cooldown_72h
selected_window_mean_pnl_usdc ~= +2.521
baseline_all_risk_on_mean_pnl_usdc ~= +1.084
baseline_non_overlap_risk_on_mean_pnl_usdc ~= +2.030
window_selection_edge_after_cost_usdc ~= +1.438
non_overlap_selection_edge_after_cost_usdc ~= +0.491
folds_with_positive_selection_edge = 6
worst_fold_selection_edge_after_cost_usdc ~= +0.147
```

Weitere passing Varianten:

```text
erv_risk_on_ethbtc_dip_72h:
  edge_vs_all_risk_on ~= +1.393 USDC
  positive_edge_folds = 5
  worst_fold_edge ~= -0.264 USDC

erv_risk_on_any_eth_dip_72h:
  edge_vs_all_risk_on ~= +1.425 USDC
  positive_edge_folds = 5
  worst_fold_edge ~= -0.264 USDC
```

Codex-Interpretation:

- BRH/ERV ist nicht komplett leer.
- Die Auswahl der Exposure-Fenster hat im Training messbaren Mehrwert gegen
  naive BTC-Risk-On-Exposure.
- Aber der beste Kandidat ist wieder exakt die alte v1-Auswahl
  `erv_risk_on_orderflow_cooldown_72h`.
- Diese alte v1-Auswahl wurde bereits frozen blindgetestet und war nur schwach
  positiv.
- Deshalb darf aus diesem Check kein neuer UI-Full-Backtest und kein zweiter
  Blindtest auf der alten Variante entstehen.

## Bitte analysieren

Ich brauche eine konkrete fachliche Entscheidung fuer Codex:

1. Ist die Codex-Interpretation korrekt?
2. Reicht der Window-Selection-Edge-Befund, um eine BRH/ERV-v2 als
   research-only Schritt zu rechtfertigen?
3. Oder zeigt die Tatsache, dass erneut die alte v1-Auswahl gewinnt, dass die
   BRH-Linie trotz Training-Edge geschlossen werden sollte?
4. Falls v2 erlaubt ist: Welche exakt eine kleine Aenderung soll Codex bauen?

Wichtig:

- Kein zweiter Blindtest auf `erv_risk_on_orderflow_cooldown_72h`.
- Keine Auswahl anhand des bereits gesehenen Blindtests.
- Keine Gate-Lockerung nur fuer mehr Trades.
- Keine 08/15-Strategie.
- Kein Short/Futures/Margin/Leverage.
- Keine erfundene Orderbook-Historie.
- Keine UI-/Router-Integration ohne neuen research-only Run.

## Gewuenschte Antwortform

Bitte am Ende sehr konkret liefern:

```text
Naechster Schritt:
  BRH-Linie schliessen ODER BRH/ERV-v2 research-only erlauben?

Wenn BRH/ERV-v2 erlaubt:
  - Name des v2-Schritts
  - exakt eine fachliche Aenderung
  - welche Datenquellen
  - welche Varianten duerfen getestet werden
  - darf die alte v1-Auswahl teilnehmen?
  - wenn ja: wie verhindern wir einen zweiten Blindtest-Erfolg auf derselben
    alten Variante?
  - wenn nein: welche Varianten sind fairerweise erlaubt?
  - Training-only Auswahlregel
  - Walkforward-Kriterien
  - Konzentrations-/Robustheitskriterien
  - Mindestanzahl Trades/Fold
  - Leave-one/two-out Kriterien
  - wann ein spaeterer frozen Blindtest erlaubt waere

Wenn BRH-Linie schliessen:
  - warum trotz Window-Selection-Edge schliessen
  - welches neue Research-Thema stattdessen
  - welche kleinste messbare Hypothese
```

Bitte keine fertige "Profitstrategie" behaupten. Ich brauche eine robuste,
saubere Spezifikation, die Codex danach ohne Blindtest-Lernen implementieren
kann.
