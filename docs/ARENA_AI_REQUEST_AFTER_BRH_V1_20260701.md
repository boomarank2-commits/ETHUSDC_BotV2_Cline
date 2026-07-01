# Arena.ai Anfrage - nach BRH/ERV-v1

Stand: 2026-07-01

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
src/research/eth_edge_scan.py
```

Falls kein Repository-Zugriff moeglich ist, reichen die folgenden Details.

## Projektziel

ETHUSDC Spot LONG-only auf Binance.

- 100 USDC Einsatzbasis
- kein Short
- kein Futures/Margin/Leverage
- keine echten Orders
- kein Blindtest-Lernen
- kein Lookahead
- Ziel: langfristig Richtung >= 3 USDC/Tag im 365-Tage-Blindtest

Workflow:

1. 730 Tage Training/Research/Walkforward
2. genau ein eingefrorener 365-Tage-Blindtest
3. nur bei gutem Blindtest duerfte spaeter UI/Router-Integration entstehen

## Bisherige negative/archivierte Spuren

Nicht wiederholen und nicht ueber Gate-/TP-/SL-Lockerung retten:

- Attempt 053: alte Performance nicht reproduziert
- ERRO-L v1: negativ
- ECMD-L v1: keine robuste Execution
- EPX-L / R2-v2 / R2-v3: Path-/Execution-Gates scheiterten
- ERH-v1: nach Next-Open-Korrektur klar negativ

## Vorlauf: ETH Edge Existence Scan

Codex baute einen training-only Edge-Scan:

```text
src/research/eth_edge_scan.py
scripts/run_eth_edge_existence_scan.py
```

Methode:

- vorhandene Features in Quintile
- Horizonte 1h, 4h, 12h, 24h, 72h
- Kostenmodell ca. 0.22% Roundtrip
- Feature-Zeile `i` ist erst nach Close bekannt
- hypothetischer Entry `i+1` Open
- kein Blindtest

Ergebnis:

```text
strategy_version = eth_edge_existence_scan_20260701
status = edge_candidate_found
edge_candidate_count = 24
reversion_candidate_count = 8
momentum_candidate_count = 15
```

Top-Trainingssignale:

1. `btc_4h_drawdown_from_20d_high`, 72h, q4
   - BTC naeher am 20-Tage-Hoch / Risk-On
   - ca. `+1.426 USDC` pro 100 USDC Hypothesenhold
   - `5/6` Folds positiv
2. `btc_4h_close_vs_ema20`, 72h, q4
   - ca. `+0.762 USDC`
   - `4/6` Folds positiv
3. `ethbtc_4h_ret_6`, 72h, q0
   - ETHBTC-Dip/Reversion
   - ca. `+0.722 USDC`
   - `5/6` Folds positiv
4. `eth_4h_dist_to_20d_high`, 72h, q0
   - ETH-Dip/Reversion
   - ca. `+0.604 USDC`
   - `4/5` Folds positiv

## Neuer Research-Runner: BRH/ERV-v1

Codex hat daraus eine echte research-only Hypothese gebaut:

```text
strategy_version = brh_v1_btc_risk_on_eth_reversion_hold_20260701
src/research/brh_v1.py
scripts/run_brh_v1_research.py
tests/test_brh_v1_research.py
```

BRH/ERV-v1 Regeln:

- Signale nur auf neuen geschlossenen 4h-Availability-Rows
- Entry immer am naechsten 1h-Open
- fixed Hold 72h
- Exit am 1h-Open nach 72h
- one-position-at-a-time, keine Ueberlappung
- Quantil-Thresholds werden je Walkforward-Fold nur aus dem jeweiligen
  Trainingsteil kalibriert
- Kostenmodell unveraendert
- Blindtest nur, wenn Training/Walkforward eligibility besteht

Varianten:

1. `brh_btc_risk_on_72h`
2. `brh_dual_btc_risk_on_72h`
3. `erv_risk_on_ethbtc_dip_72h`
4. `erv_risk_on_eth_dip_72h`
5. `erv_risk_on_any_eth_dip_72h`
6. `erv_risk_on_dual_eth_dip_72h`
7. `erv_risk_on_orderflow_cooldown_72h`

## BRH/ERV-v1 Ergebnis

```text
status = blindtest_completed
eligible_variant_count = 5 / 7
blindtest_candidate_count_evaluated = 1
selected_variant = erv_risk_on_orderflow_cooldown_72h
```

Training/Walkforward:

- 5 Varianten eligible
- alle eligible Varianten hatten `6/6` positive Folds
- `brh_dual_btc_risk_on_72h`:
  - ca. `+142.26 USDC`
  - ca. `+0.259 USDC/Tag`
  - 52 Trades
  - PF ca. `3.65`
- `brh_btc_risk_on_72h`:
  - ca. `+138.06 USDC`
  - ca. `+0.251 USDC/Tag`
  - 68 Trades
  - PF ca. `2.36`
- selektiert wurde training-only nach hoechstem PF:
  - `erv_risk_on_orderflow_cooldown_72h`
  - ca. `+135.41 USDC`
  - ca. `+0.246 USDC/Tag`
  - 45 Trades
  - PF ca. `3.95`

Frozen Blindtest der selektierten Variante:

- PnL: `+4.647 USDC`
- USDC/Tag: `+0.0127`
- Trades: `22`
- PF: ca. `1.10`
- Positive/negative Trades: `10 / 12`
- Median Trade PnL: ca. `-0.373 USDC`
- Max Drawdown: ca. `26.58 USDC`
- Ziel `3 USDC/Tag` klar nicht erreicht

## Problem

BRH/ERV-v1 war im Walkforward stark und fold-stabil, aber der frozen Blindtest
war nur schwach positiv. Das ist kein Komplettversagen, aber weit weg vom Ziel.

Bitte nicht empfehlen:

- Variante nach Blindtest wechseln
- andere eligible Varianten nachtraeglich im Blindtest testen
- Thresholds auf den Blindtest anpassen
- Gates lockern, damit mehr Trades entstehen
- neuen Blindtest zur Optimierung verwenden

## Bitte analysieren

Gesucht ist der naechste kleine, saubere Diagnose- oder Research-Schritt.

Fragen:

1. Ist BRH/ERV-v1 methodisch sauber umgesetzt?
2. Ist die Auswahl nach hoechstem Training-PF sinnvoll, oder haette vor
   Blindtest eine robustere Training-only Auswahlregel gelten muessen?
3. Welche Diagnose erklaert am besten den Train-vs-Blind-Decay?
   - Feature-/Threshold-Distribution-Shift?
   - BTC-Risk-On-Regime im Blindtest anders?
   - 72h-Hold-Horizont zerfaellt im Blindtest?
   - Orderflow-Cooldown war Training-PF-Overfit?
   - zu wenige Trades / zu starke Konzentration?
4. Was ist der naechste EINZIGE Schritt fuer Codex?

Wichtig:

- Kein Blindtest-Lernen.
- Kein zweiter Varianten-Blindtest.
- Keine 08/15-Strategie.
- Keine Wiederholung von ERH/ERRO/ECMD/EPX/R2.
- Kein Short/Futures/Margin/Leverage.
- Keine Orderbook-Historie erfinden.
- Kein 3-USDC-Ergebnis erzwingen.

Bitte formuliere am Ende eine konkrete Codex-Spezifikation:

```text
Name des naechsten Schritts
Ziel der Diagnose
Datenquellen
Metriken
Was aus Training vs Blind verglichen wird
Welche Entscheidungsregeln gelten
Wann BRH/ERV-v1 archiviert wird
Wann eine neue Version fachlich erlaubt waere
```
