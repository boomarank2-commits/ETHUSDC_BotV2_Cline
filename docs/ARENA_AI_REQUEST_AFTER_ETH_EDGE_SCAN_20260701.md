# Arena.ai Anfrage - nach ETH Edge Existence Scan

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
- Ziel: 365-Tage-Blindtest soll langfristig Richtung >= 3 USDC/Tag kommen

Der Prozess ist:

1. 730 Tage Training/Research/Walkforward
2. genau ein eingefrorener 365-Tage-Blindtest
3. nur wenn der Blindtest gut ist, darf spaeter ueber Uebernahme gesprochen
   werden

## Bisherige negative Spuren

Nicht wiederholen oder ueber TP/SL/Gate-Lockerung retten:

- Attempt 053: alte behauptete Performance nicht reproduziert
- ERRO-L v1: negativ
- ECMD-L v1: Signale ja, aber keine robuste Execution
- EPX-L / R2-v2 / R2-v3: Path-/Execution-Gates scheiterten
- ERH-v1: HTF-Regime-Hold scheiterte

## Wichtiger ERH-v1-Bugfix

Bei ERH wurde ein Ausfuehrungsfehler korrigiert:

- 1h/4h Kerzen sind nach Availability/Close indexiert
- ein Signal auf einer geschlossenen Kerze darf nicht auf dem Open derselben
  bereits geschlossenen Kerze handeln
- Entry ist jetzt: Signal auf Zeile `i` -> pending entry -> Zeile `i+1` Open

Nach dieser Korrektur ist ERH noch schlechter:

- `status = no_training_walkforward_candidate`
- 0/8 Varianten eligible
- 0 Blindtest-Kandidaten
- beste Variante nach PnL:
  - `erh_score4_arm30_give30`
  - 123 Validation-Trades
  - ca. `-98.53 USDC`
  - PF ca. `0.286`
  - positive Folds `0/6`

Unconditional-Regime-Test nach Next-Open:

- Score>=3:
  - 146 Episoden
  - total ca. `-72.80 USDC`
  - PF ca. `0.442`
  - Winrate ca. `30.14%`
  - Avg Return/Episode ca. `-0.499%`
- Score>=4:
  - 119 Episoden
  - total ca. `-77.90 USDC`
  - PF ca. `0.332`
  - Winrate ca. `29.41%`
  - Avg Return/Episode ca. `-0.655%`
- Buy-and-hold im Trainingszeitraum: ca. `+28.99 USDC`

Interpretation: ERH-v1 bitte als archiviert behandeln. Keine Hysterese-/Gate-/
Exit-Rettung empfehlen, ausser du findest einen echten neuen technischen Bug.

## Neuer Scan: ETH Edge Existence Scan

Codex hat danach deinen/euren besseren Vorschlag umgesetzt:

```text
src/research/eth_edge_scan.py
scripts/run_eth_edge_existence_scan.py
tests/test_eth_edge_scan.py
```

Der Scan ist research-only:

- keine Strategie
- keine Trades
- kein UI-Backtest
- kein Blindtest
- nur 730-Tage-Training

Methode:

- vorhandene Features in Quintile teilen
- Forward-Horizonte: 1h, 4h, 12h, 24h, 72h
- Kostenmodell: ca. 0.22% Roundtrip
- Feature-Zeile `i` ist erst nach Close bekannt
- hypothetischer Entry: Zeile `i+1` Open
- Exit: Horizon spaeter
- Kandidat nur, wenn bestes Quintil nach Kosten positiv ist und mindestens
  3 Folds positiv sind

Daten/Features:

- ETHUSDC 1m OHLCV + vollstaendige Binance-Kline-Felder
  - quote volume
  - trade count
  - taker buy base/quote
- BTCUSDC 1m Kontext
- ETHBTC 1m Relative-Strength-Kontext
- ETHUSDT 1m und USDCUSDT 1m fuer Quote/Basis/Peg
- alles auf geschlossene 1h/4h Features resampled
- keine historischen Orderbook-Fakes

Getestete Features u. a.:

- `eth_1h_ret_3`
- `eth_4h_ret_6`
- `ethbtc_4h_ret_6`
- `eth_4h_close_vs_ema20`
- `eth_4h_dist_to_20d_high`
- `eth_of_ofi_4h_3sum`
- `eth_of_4h_buy_share_3avg`
- `eth_of_quote_vol_z_20`
- `btc_4h_close_vs_ema20`
- `btc_4h_drawdown_from_20d_high`
- `btc_4h_rv_20`
- `usdc_dev`
- `basis_usdt_4h`

## Ergebnis des Scans

```text
strategy_version = eth_edge_existence_scan_20260701
status = edge_candidate_found
edge_candidate_count = 24
reversion_candidate_count = 8
momentum_candidate_count = 15
```

Top-Kandidaten im Training:

1. `btc_4h_drawdown_from_20d_high`, Horizon 72h, q4
   - Interpretation: BTC naeher am 20-Tage-Hoch / Risk-On
   - Mean nach Kosten: ca. `+1.426 USDC` je 100 USDC
   - positive Folds: `5/6`
   - Winrate: ca. `57.4%`
2. `btc_4h_close_vs_ema20`, Horizon 72h, q4
   - Mean nach Kosten: ca. `+0.762 USDC`
   - positive Folds: `4/6`
3. `ethbtc_4h_ret_6`, Horizon 72h, q0
   - Interpretation: ETHBTC vorher schwach -> Reversion
   - Mean nach Kosten: ca. `+0.722 USDC`
   - positive Folds: `5/6`
4. `eth_4h_dist_to_20d_high`, Horizon 72h, q0
   - Interpretation: ETH weiter weg vom 20-Tage-Hoch -> Dip/Reversion
   - Mean nach Kosten: ca. `+0.604 USDC`
   - positive Folds: `4/5`
5. `eth_of_ofi_4h_3sum`, Horizon 72h, q1
   - Interpretation: schwaches Orderflow-Quintil -> Reversion/kein Chase
   - Mean nach Kosten: ca. `+0.467 USDC`
   - positive Folds: `4/6`

## Bitte analysieren

Bitte nicht einfach eine fertige 08/15-Strategie vorschlagen.

Gesucht ist der naechste kleine, saubere Research-Schritt fuer Codex:

1. Ist der Edge-Scan logisch sauber genug, oder siehst du noch einen konkreten
   methodischen Fehler?
2. Falls sauber: Welche EINZIGE kleine Hypothese soll Codex daraus bauen?
3. Sollte die naechste Hypothese eher sein:
   - BTC-Risk-On ETH 72h Hold,
   - ETHBTC/ETH Dip-Reversion innerhalb BTC-Risk-On,
   - Kombination aus beiden,
   - oder etwas anderes?
4. Welche Walkforward-Regeln verhindern Overfitting?
5. Welche harten Ablehnungskriterien sollen gelten, bevor ein Blindtest erlaubt
   ist?

Wichtig:

- Kein Blindtest-Lernen.
- Keine Gates blind lockern.
- Keine Wiederholung von ERH/ERRO/ECMD/EPX/R2.
- Keine Short/Futures/Margin/Leverage-Idee.
- Keine Orderbook-Historie erfinden.
- Kein 3-USDC-Ergebnis erzwingen.

Bitte formuliere am Ende eine konkrete Spezifikation, die Codex direkt
implementieren kann:

```text
Name der Hypothese
Datenquellen
Entry-Regel
Exit-Regel
Walkforward-Auswahl
Kostenmodell
No-Lookahead-Regeln
Eligibility-Kriterien
Was reportet werden muss
Wann abbrechen/archivieren
```
