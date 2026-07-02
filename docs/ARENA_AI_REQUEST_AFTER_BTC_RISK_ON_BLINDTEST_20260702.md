# Arena.ai Anfrage - nach BRH BTC-Risk-On Frozen Blindtest

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
src/research/brh_selection_edge_robustness_v2check.py
src/research/brh_btc_risk_on_frozen_blindtest.py
```

## Ziel

ETHUSDC Spot LONG-only auf Binance:

- 100 USDC Einsatzbasis
- 730 Tage Training/Walkforward
- danach maximal ein 365-Tage frozen Blindtest je sauber freigegebener
  Research-Hypothese
- kein Short, kein Futures/Margin/Leverage
- kein Blindtest-Lernen
- kein Lookahead
- keine echten Orders
- langfristiges Ziel: Richtung `3 USDC/Tag`, aber nur durch robuste Evidenz

## Bisheriger Stand

Viele Spuren sind archiviert:

- Attempt 053: nicht reproduziert
- ERRO-L v1: negativ
- ECMD-L v1: keine robuste Execution
- EPX-L/R2-v2/R2-v3: Path-/Execution-Gates scheiterten
- ERH-v1: nach Next-Open-Korrektur negativ
- BRH/ERV-v1 Orderflow-Auswahl:
  - Training stark
  - frozen Blindtest nur schwach positiv:
    ca. `+4.65 USDC`, `+0.013 USDC/Tag`
  - Top-2-Konzentration im Blindtest ca. `572%`
  - daher archiviert

## Neuer Gatekeeper

Codex baute danach:

```text
strategy_version = brh_selection_edge_robustness_v2check_20260702
```

Der Check ist rein training-only und ergaenzt:

- Random/unconditional ETH-72h-Baseline
- ETH Buy-and-Hold-Baseline fuer denselben Validation-Zeitraum
- Top-1/Top-2-Konzentrationsgrenzen
- Leave-one/two-out PF
- Mindest-Trades
- PF-Obergrenze gegen Overfit
- No-Repeat-Regel fuer bereits blindgetestete v1-Varianten

Ergebnis:

```text
status = new_training_only_candidate_found
passing_variant_count = 1
passing_variant = brh_btc_risk_on_72h
already_blindtested_in_v1 = false
```

Training/Walkforward fuer `brh_btc_risk_on_72h`:

```text
trades = 68
validation_pnl ~= +138.06 USDC
validation_usdc_per_day ~= +0.251
profit_factor ~= 2.36
leave_one_out_pf ~= 2.07
leave_two_out_pf ~= 1.89
top1_share ~= 20.9%
top2_share ~= 34.5%
random_baseline_trimmed_edge ~= +1.49 USDC/Fenster
strategy_minus_buy_hold_usdc_per_day ~= +0.240
```

Die alte v1-Orderflow-Variante scheiterte am neuen Gatekeeper:

```text
45 < 48 Trades
worst Fold nicht positiv
PF ueber Overfit-Obergrenze
```

## Neuer Frozen Research-Blindtest

Codex baute danach genau einen frozen Research-Blindtest-Runner:

```text
strategy_version = brh_btc_risk_on_72h_frozen_blindtest_20260702
candidate = brh_btc_risk_on_72h
```

Regeln:

- genau diese Variante
- keine neue Variantensuche
- keine Parameteraenderung
- kein UI-/Router-Backtest
- kein Blindtest-Lernen
- Runner bricht ab, wenn der Gatekeeper nicht exakt diesen Kandidaten
  freigegeben hat

Frozen Blindtest Ergebnis:

```text
pnl_usdc ~= +10.62
usdc_per_day ~= +0.0291
trades = 26
profit_factor ~= 1.256
median_trade_net_pnl ~= +0.493 USDC
max_drawdown ~= 18.63 USDC
leave_one_out_pf ~= 1.006
leave_two_out_pf ~= 0.852
top1_share ~= 97.7%
top2_share ~= 157.6%
```

Blindtest Buy-and-Hold-Baseline:

```text
ETH buy-and-hold pnl ~= -35.84 USDC
ETH buy-and-hold ~= -0.098 USDC/Tag
strategy_minus_buy_hold ~= +0.127 USDC/Tag
```

Codex-Entscheidung:

```text
positive_blindtest_edge = true
robust_blindtest_edge = false
router_integration_allowed_now = false
ui_full_backtest_allowed_now = false
```

Interpretation:

- `brh_btc_risk_on_72h` ist besser als die alte BRH-v1-Auswahl.
- Es war im Blindtest besser als passives ETH-Halten.
- Aber das Ergebnis ist weit entfernt vom Ziel `3 USDC/Tag`.
- Der Gewinn ist zu stark konzentriert.
- Nach Entfernung der zwei besten Trades faellt PF unter 1.
- Deshalb keine Router-Integration und kein UI-Full-Backtest.
- Der Blindtest darf nicht nachoptimiert werden.

## Bitte analysieren

Ich brauche eine ehrliche Entscheidung:

1. Ist Codex' Entscheidung korrekt, trotz positivem Blindtest nicht zu
   integrieren?
2. Soll die BRH/ERV-Linie jetzt geschlossen werden?
3. Oder gibt es noch genau einen sauberen, vorab definierbaren Research-Schritt,
   der nicht auf diesem Blindtest lernt?
4. Wenn ja: welcher?
5. Wenn nein: welches neue Research-Thema ist sinnvoller?

Wichtig:

- Kein Nachoptimieren auf `brh_btc_risk_on_72h`.
- Kein zweiter Blindtest derselben Variante.
- Keine UI-/Router-Integration ohne robustes Research-Ergebnis.
- Keine Gate-Lockerung nur fuer Trades oder Zielnaehe.
- Keine 08/15-Strategie.
- Kein Short/Futures/Margin/Leverage.
- Keine erfundene Orderbook-Historie.

## Gewuenschte Antwortform

Bitte konkret antworten:

```text
Codex-Entscheidung korrekt? ja/nein
BRH/ERV schliessen? ja/nein
Wenn nein:
  - exakt ein neuer Research-Schritt
  - warum er nicht auf dem gesehenen Blindtest lernt
  - Datenquellen
  - Training-only Kriterien
  - wann ein neuer Blindtest ueberhaupt erlaubt waere
Wenn ja:
  - welches neue Research-Thema
  - kleinste messbare Hypothese
  - warum es nicht nur BRH/ERV unter anderem Namen ist
```
