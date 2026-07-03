# Arena.ai Anfrage - nach BELL-v1 und BEV-L-v1 Training-Fail

Bitte analysiere dieses Repository:

```text
https://github.com/boomarank2-commits/ETHUSDC_BotV2_Cline
Branch: spec/activity-first-rebuild-20260623
```

Bitte zuerst lesen:

```text
README.md
AGENTS.md
docs/GPT_CONTINUATION_GUIDE_20260701.md
docs/IMPLEMENTATION_PLAN.md
```

## Aktueller Stand

EREM-Hysteresis v1.2 ist die aktuelle defensive Baseline:

```text
Run: run_20260703_122054
Kandidat: erem_minhold_exp48_flat12
Ergebnis: ca. +4.64 USDC
Gewinn/Tag: ca. +0.0127 USDC/Tag
Bewertung: positiv gegen vorheriges Basis-EREM, aber weit weg von 3 USDC/Tag.
```

EREM wird nicht weiter auf denselben Blindtest optimiert.

Danach wurden zwei neue, klar getrennte Profit-Alpha-Research-Spuren gebaut.
Beide nutzen nur Training/Walkforward und beruehren den Blindtest nicht.

## BELL-v1 BTC->ETH Lead-Lag/Catch-up

Dateien:

```text
src/research/bell_v1_leadlag_scan.py
scripts/run_bell_v1_leadlag_scan.py
tests/test_bell_v1_leadlag_scan.py
```

Ziel:

```text
Pruefen, ob ETHUSDC nach BTC-Impulsen in Risk-On-Kontexten verzoegert
nachzieht, wenn ETH/ETHBTC noch nicht gechased sind.
```

Ergebnis:

```text
status = no_bell_training_edge
sanity_status = bell_sanity_failed
passing_scan_count = 0
variant_count = 6
eligible_variant_count = 0
best_sanity_feature = btc_impulse_with_ethbtc_lag
best_sanity_horizon = 48
best_sanity_positive_folds = 4
required_positive_folds = 5
```

Entscheidung:

```text
Kein frozen Blindtest.
Kein Router-Patch.
Kein UI-Full-Backtest.
Nicht per Gate-Lockerung retten.
```

## BEV-L v1 Volatility-Divergence

Dateien:

```text
src/research/bev_l_v1_divergence_scan.py
scripts/run_bev_l_v1_divergence_scan.py
tests/test_bev_l_v1_divergence_scan.py
```

Ziel:

```text
Pruefen, ob BTC-Volatilitaetskompression plus positive ETHBTC-
Volatilitaetsdivergenz einen stabilen ETHUSDC-Forward-Edge erzeugt.
```

Ergebnis:

```text
status = no_bev_l_training_divergence_edge
passing_horizon_count = 0
12h: 0 passing folds
24h: 0 passing folds
48h: 1 passing fold
```

Entscheidung:

```text
Keine Strategie.
Kein frozen Blindtest.
Kein Router-Patch.
Kein UI-Full-Backtest.
Nicht per Gate-Lockerung retten.
```

## Bitte analysieren

Bitte nicht einfach eine elfte umbenannte Momentum-/Reversion-/Lead-Lag-Idee
vorschlagen.

Bitte beantworte:

1. Sind die Kill-Switches fuer BELL-v1 und BEV-L-v1 methodisch sinnvoll, oder
   sind sie technisch falsch umgesetzt?
2. Gibt es in den neuen BELL/BEV-Modulen einen offensichtlichen Codefehler,
   der einen echten Edge faelschlich blockiert?
3. Falls nein: Ist es jetzt sinnvoller, den von einer Antwort vorgeschlagenen
   `eth_regime_conditional_edge_scan` zu bauen, also erst zu messen, ob alte
   Signale nur in Bull-Phasen Edge hatten?
4. Welche konkrete naechste Codex-Aufgabe ist kleiner und sinnvoller als noch
   eine neue Strategie-Idee?

Regeln:

- Kein Blindtest-Lernen.
- Keine Gate-Lockerung fuer 3 USDC/Tag.
- Kein Short/Futures/Margin/Leverage.
- Keine echten Orders.
- Keine separate Smoke-Engine.
- EREM-v1.2 nicht weiter auf denselben Blindtest tunen.
- Erst Research-only, dann frozen Blindtest, erst dann Router/UI-Full.

Bitte am Ende eine konkrete Codex-Umsetzungsanweisung liefern.
