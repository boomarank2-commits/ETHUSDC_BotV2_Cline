# Arena.ai Anfrage nach ERH-v1-DIAG

Repository:

```text
https://github.com/boomarank2-commits/ETHUSDC_BotV2_Cline
Branch: spec/activity-first-rebuild-20260623
```

Bitte zuerst lesen:

```text
README.md
AGENTS.md
docs/GPT_CONTINUATION_GUIDE_20260701.md
src/research/erh_v1.py
src/research/erh_v1_diagnostics.py
```

## Projektregeln

- ETHUSDC Binance Spot
- LONG-only
- 100 USDC Einsatzbasis
- keine Futures, keine Shorts, kein Margin, kein Leverage
- keine echten Orders
- kein Lookahead
- kein Blindtest-Lernen
- keine Gate-Lockerung, nur damit Trades oder Zielwerte entstehen
- 730 Tage Training/Walkforward
- 365 Tage Blindtest nur, wenn Training/Walkforward bestanden wurde

## Bisherige sauber gescheiterte Spuren

- Attempt 053: nicht reproduziert
- ERRO-L v1: negativ
- ECMD-L v1: kein robustes Walkforward-Template
- EPX/R2-v2/R2-v3: relative Signale, aber keine robuste Execution /
  `no_path_gate_candidate`
- ERH-v1 HTF-Regime-Pivot: `no_training_walkforward_candidate`

## Neuer Diagnose-Run

Codex hat nach deiner letzten Antwort keinen neuen Strategieversuch gebaut,
sondern ERH-v1-DIAG:

```text
src/research/erh_v1_diagnostics.py
scripts/run_erh_v1_diagnostics.py
tests/test_erh_v1_diagnostics.py
```

Der Diagnose-Run aendert keine Parameter, startet keinen Blindtest und ist
nur Instrumentierung.

## ERH-v1-DIAG Ergebnis

```text
strategy_version = erh_v1_signal_funnel_diagnostic_20260701
status = diagnostic_complete
suspected_root_cause_category = B_genuine_edge_problem
recommended_next_step = Treat ERH-v1 as likely non-trading edge unless a
concrete implementation bug is found.
```

Regime-Sanity:

```text
training_4h_bars = 4380
hard_gate_active_bar_count = 416
hard_gate_episode_count = 178
score3_active_bar_count = 334
score3_episode_count = 146
score4_active_bar_count = 248
score4_episode_count = 119
```

Feature-Audit:

```text
gate_eth_trend true_rate ~= 50.3%, nan_rate ~= 0.18%
gate_ethbtc_trend true_rate ~= 38.6%, nan_rate ~= 0.21%
gate_ethbtc_slope true_rate ~= 41.7%, nan_rate = 0
gate_btc_not_crash true_rate ~= 95.7%, nan_rate ~= 1.12%
gate_orderflow true_rate ~= 40.4%, nan_rate = 0
gate_usdc true_rate ~= 98.1%, nan_rate = 0
gate_basis true_rate ~= 99.98%, nan_rate = 0
```

Interpretation der Feature-Audit:

- Keine offensichtliche massive NaN-/Join-Anomalie.
- USDC/Basis sind fast immer true, aber das ist als Sanity-Filter plausibel
  und blockiert nicht.
- Regime tritt oft genug auf; Frequenzproblem ist nicht die Hauptursache.

Signal-Funnel:

```text
score3 variants:
  active 1h bars: 1336
  trigger bars: 729
  candidate entry bars after no_chase: 707
  trades opened: 135-136

score4 variants:
  active 1h bars: 992
  trigger bars: 551
  candidate entry bars after no_chase: 551
  trades opened: 112
```

Exit-Verteilung:

```text
Die meisten Exits sind regime_end.
Hard stops sind selten.
Trailing exits sind selten.
```

Unconditional-Regime-Return-Test:

```text
Score>=3:
  episodes = 146
  total_pnl_usdc ~= -11.72
  profit_factor ~= 0.8766
  win_rate_per_episode ~= 43.15%
  avg_return_per_episode ~= -0.080%

Score>=4:
  episodes = 119
  total_pnl_usdc ~= -25.44
  profit_factor ~= 0.6981
  win_rate_per_episode ~= 39.50%
  avg_return_per_episode ~= -0.214%

Full-train buy-and-hold net:
  ~= +28.99 USDC
```

## Wichtige Schlussfolgerung

ERH-v1 scheitert nicht, weil zu wenige Regime/Trades existieren. Es scheitert
auch nicht offensichtlich an einem NaN-/Join-Bug. Die definierte Regime-Idee
filtert im Training schlechter als einfaches ETH-Halten und liefert nach
Kosten keinen positiven Edge.

## Frage an Arena.ai

Bitte keine ERH-v1-Gates blind lockern und kein Exit-Tuning vorschlagen, nur
damit PF steigt.

Bitte beantworte:

1. Gibt es im ERH-v1/DIAG-Befund noch einen konkreten Implementierungsfehler,
   den Codex pruefen sollte?
2. Wenn nein: Ist ERH-v1 damit ehrlich als nicht-tragender Edge zu archivieren?
3. Gibt es noch genau einen kleinen, fachlich begruendeten Diagnose-Schritt,
   bevor das Projekt neu bewertet werden sollte?
4. Falls du eine neue Hypothese empfiehlst:
   - sie muss fundamental anders sein als ERRO, ECMD, EPX/R2 und ERH;
   - sie muss mit den vorhandenen Daten begruendet sein;
   - sie muss research-only klein genug fuer Codex sein;
   - sie muss klare Abbruchkriterien haben.

Wenn kein solcher Schritt sinnvoll ist, bitte ehrlich sagen:

```text
Mit ETHUSDC Spot LONG-only, 100 USDC, ohne Leverage, ohne Short und bei
realistischen Kosten ist mit den aktuell vorhandenen historischen Daten kein
robuster Edge nachgewiesen. Empfehlung: Projekt-Reassessment statt weiteres
Signal-Patchen.
```
