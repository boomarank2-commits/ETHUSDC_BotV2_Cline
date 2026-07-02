# Arena.ai Anfrage - nach BRH-v1-DIAG

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
src/research/brh_v1.py
src/research/brh_v1_diagnostics.py
```

## Ziel

ETHUSDC Spot LONG-only auf Binance:

- 100 USDC Einsatzbasis
- 730 Tage Training/Walkforward
- danach genau ein 365-Tage frozen Blindtest
- kein Short, kein Futures/Margin/Leverage
- kein Blindtest-Lernen
- kein Lookahead
- keine echten Orders
- Ziel langfristig Richtung `3 USDC/Tag`, aber nur durch robuste Evidenz

## Bisheriger Verlauf

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

Training/Walkforward:

- 5 Varianten eligible
- alle eligible Varianten hatten 6/6 positive Folds
- selektierte Variante:
  - ca. `+135.41 USDC`
  - ca. `+0.246 USDC/Tag`
  - 45 Trades
  - PF ca. `3.95`

Frozen Blindtest:

- `+4.647 USDC`
- `+0.0127 USDC/Tag`
- 22 Trades
- PF ca. `1.10`
- Median Trade PnL ca. `-0.373 USDC`
- Max Drawdown ca. `26.58 USDC`

## Neue Diagnose: BRH-v1-DIAG

Codex hat danach eine reine Post-Mortem-Diagnose gebaut:

```text
strategy_version = brh_v1_attribution_decay_diagnostics_20260702
src/research/brh_v1_diagnostics.py
scripts/run_brh_v1_diagnostics.py
tests/test_brh_v1_diagnostics.py
```

Sie macht:

- keine Strategieaenderung
- keine neue Variante
- keinen zweiten Varianten-Blindtest
- keine UI-/Router-Integration
- nur Auswertung des vorhandenen BRH-v1-Reports und Trade-Ledgers

## BRH-v1-DIAG Ergebnis

Threshold-Verifikation:

```text
thresholds_training_only = true
```

Die Blindtest-Quantile passen exakt zur Recalculation aus Training-only-Daten.
Kein stiller Quantile-Lookahead gefunden.

Distribution Shift:

```text
risk_on_bars_per_day_ratio_blind_over_train ≈ 0.639
```

Risk-On war im Blindtest weniger verfuegbar, aber kein harter <50%-Kollaps.

Horizon Decay:

Blindtest Mean PnL je Trade:

```text
6h  ≈ -0.597 USDC
12h ≈ -0.580 USDC
24h ≈ -0.830 USDC
36h ≈ -0.597 USDC
48h ≈ -1.021 USDC
60h ≈ +0.129 USDC
72h ≈ +0.211 USDC
```

Also: kuerzere Horizonte waren im Blindtest nicht besser. Kein klarer Beleg,
dass nur der starre 72h-Hold das Problem ist.

Same-window ETH Attribution:

```text
signal_minus_same_window_eth ≈ 0
```

Das ist erwartbar, weil BRH fixed Spot-Long im ausgewaehlten Fenster ist.
Ein Edge kann nur aus besserer Auswahl der ETH-Exposure-Fenster kommen, nicht
aus Alpha innerhalb des Fensters.

Konzentration / Fragilitaet:

Training selected variant:

```text
45 Trades
total ≈ +135.41 USDC
median trade ≈ +1.95 USDC
top-2 trades share ≈ 36.9%
leave-two-out PF ≈ 2.86
```

Blindtest selected variant:

```text
22 Trades
total ≈ +4.65 USDC
median trade ≈ -0.37 USDC
top-1 trade share ≈ 337%
top-2 trades share ≈ 572%
leave-one-out PF ≈ 0.76
leave-two-out PF ≈ 0.53
```

Selection Forensics:

```text
selection_rule_in_v1 = highest_training_profit_factor_then_pnl
max_pairwise_entry_jaccard ≈ 0.75
mean_pairwise_entry_jaccard ≈ 0.146
fold winners wechselten zwischen Varianten
```

Codex-Interpretation:

- BRH-v1 war methodisch sauber.
- Der leicht positive Blindtest ist aber nicht robust.
- Hauptproblem ist nicht klar Horizon-Decay, sondern Blindtest-PnL-
  Konzentration / geringe Stichprobe / Selection-Fragilitaet.
- Aktuelle BRH-v1-Form bleibt archiviert und nicht integrationsfaehig.
- Keine BRH-v2 ohne neue, rein training-only begruendete Spezifikation.

## Bitte analysieren

Gesucht ist nicht direkt eine neue Strategie, sondern die naechste saubere
Entscheidung:

1. Ist die Codex-Interpretation korrekt?
2. Reicht der BRH-v1-DIAG-Befund, um BRH-v1 voll zu archivieren?
3. Ist eine BRH/ERV-v2 fachlich noch gerechtfertigt?
4. Falls ja: Welche EINE kleine, training-only begruendete Aenderung waere
   sauber?
5. Soll v2 eher:
   - Selection-Rule robustifizieren,
   - Konzentration bestrafen,
   - Beta-only-Komponente entfernen,
   - oder eine komplett neue Reversion-Hypothese werden?

Wichtig:

- Kein zweiter Blindtest auf alten Varianten.
- Keine Auswahl anhand des bereits gesehenen Blindtests.
- Keine Gate-Lockerung nur fuer mehr Trades.
- Keine 08/15-Strategie.
- Kein Short/Futures/Margin/Leverage.
- Keine erfundene Orderbook-Historie.
- Keine UI-/Router-Integration ohne neuen Research-Run.

Bitte am Ende eine konkrete Codex-Spezifikation liefern:

```text
Name des naechsten Schritts
Ob BRH-v1 archiviert bleibt
Ob v2 erlaubt ist
Wenn v2 erlaubt:
  - exakt eine Aenderung
  - Datenquellen
  - Training-only Auswahlregel
  - Walkforward-Kriterien
  - Konzentrations-/Robustheitskriterien
  - wann ein frozen Blindtest erlaubt waere
Wenn v2 nicht erlaubt:
  - welches Research-Thema stattdessen oder Projekt-Reassessment
```
