# ETHUSDC Bot V2 - einzige Arbeitswahrheit

Stand: 2026-07-01.

Dieses Projekt ist ausschließlich fuer einen Zweck da:

> ETHUSDC Spot LONG-only auf Binance mit USDC-Kapital so trainieren, dass aus
> 730 Tagen Training eine eingefrorene Strategie / ein eingefrorener
> Kandidatenpool entsteht und danach ein 365-Tage-Blindtest ohne Lernen zeigt,
> ob diese Logik wirklich tragfaehig ist.

Zielwert bleibt: mindestens `3.00 USDC/Tag` im 365-Tage-Blindtest bei
`100 USDC` Einsatzbasis. Dieses Ziel darf nicht durch Blindtest-Lernen,
Fake-Trades, Gate-Lockerung oder getrennte Backtestpfade erzwungen werden.

## Wichtigste Dateien

- GPT/Codex-Fortsetzung: `docs/GPT_CONTINUATION_GUIDE_20260701.md`
- Kernregeln: `AGENTS.md`
- Backtest-Vertrag: `specs/07_FINAL_ONE_YEAR_BLINDTEST_CONTRACT.md`
- Basistruth-Dateien: `docs/MASTER_TRUTH.md`, `docs/BACKTEST_TRUTH.md`,
  `docs/DATA_TRUTH.md`, `docs/ROUTER_TRUTH.md`, `docs/UI_TRUTH.md`

Wenn eine Datei widerspricht, gilt diese Reihenfolge:

1. `README.md`
2. `AGENTS.md`
3. `docs/GPT_CONTINUATION_GUIDE_20260701.md`
4. `specs/`
5. alte Hintergrundnotizen

## Aktueller technischer Stand

- UI, Smoke und Full laufen ueber denselben Backtestpfad.
- Es gibt nur eine Wahrheit: `activity_first_router`.
- Smoke 1/7/14/30 sind nur kuerzere technische Pruefungen desselben Pfads.
- Full ist der 730-Tage-Training / 365-Tage-Blindtest.
- Pool-Overlap-Guard ist aktiv: Kandidaten werden nicht als getrennte Konten
  zusammengerechnet.
- Daten-Ensure laeuft vor UI-Backtests zentral an und laedt/aktualisiert
  fehlende Marktdaten.
- Paper, Live, Testtrade und echte Orders bleiben gesperrt.

## Aktueller Ergebnisstand

Kein Kandidat ist uebernahmefaehig.

Die zuletzt untersuchten Research-Spuren sind bewusst nicht integriert:

- Attempt 053: nicht reproduziert.
- ERRO-L v1: negativ, nicht integrieren.
- ECMD-L v1: kein robuster Walkforward-Kandidat, nicht integrieren.
- EPX-L / R2-v2 / R2-v3: Tradeability/Path-Lift vorhanden, aber keine
  robuste Execution; `R2-v3` endete mit `no_path_gate_candidate`.
- ERH-v1: Research-only HTF-Regime-Pivot wurde umgesetzt, danach wurde ein
  Next-Open-Ausfuehrungsfehler korrigiert. Signale auf geschlossenen 1h/4h
  Kerzen duerfen jetzt nur noch am naechsten 1h-Open handeln. Ergebnis nach
  erneutem Run: `no_training_walkforward_candidate`, 0/8 Varianten eligible,
  0 Blindtest-Kandidaten. ERH-v1 ist archiviert.
- ETH Edge Existence Scan: neuer training-only Scan wurde umgesetzt und lokal
  ausgefuehrt. Ergebnis: `edge_candidate_found`. Es gibt Trainingsstruktur
  ueber 24-72h, besonders BTC-Risk-On und einige Reversion-/Dip-Quintile.
  Das ist noch keine Strategie und noch kein UI-Backtest-Signal.
- BRH/ERV-v1: aus dem Edge-Scan wurde eine echte research-only
  Walkforward-Hypothese gebaut:
  BTC-Risk-On ETH 72h Hold plus optionale ETHBTC/ETH/Orderflow-Reversion.
  Ergebnis: Training/Walkforward fand 5/7 eligible Varianten und erlaubte
  genau einen frozen Blindtest. Der Blindtest war leicht positiv, aber weit
  vom Ziel entfernt: `+4.65 USDC` gesamt, `+0.013 USDC/Tag`, 22 Trades.
  BRH/ERV-v1 ist deshalb nicht uebernahmefaehig und nicht UI-ready.

Konsequenz:

- keinen neuen UI-Full-Backtest nur fuer diese toten Spuren starten;
- R2-v2/R2-v3 nicht weiter ueber TP/SL/Hold/Gates erzwingen;
- ERH-v1 nicht weiter ueber Gate-/Exit-/Hold-Tuning retten. Nach
  Next-Open-Korrektur ist der Befund klar negativ.
- naechster sinnvoller Schritt ist nicht UI-Full-Backtest, sondern BRH/ERV-v1
  diagnostizieren: Warum waren Walkforward-Folds stark, aber der frozen
  Blindtest nur schwach positiv? Keine weitere Blindtest-Optimierung.

Aktueller Edge-Scan-Befund:

- Dateien:
  - `src/research/eth_edge_scan.py`
  - `scripts/run_eth_edge_existence_scan.py`
  - `tests/test_eth_edge_scan.py`
- `strategy_version = eth_edge_existence_scan_20260701`
- `status = edge_candidate_found`
- `edge_candidate_count = 24`
- `reversion_candidate_count = 8`
- `momentum_candidate_count = 15`
- wichtigster Trainingskandidat:
  - Feature: `btc_4h_drawdown_from_20d_high`
  - Horizont: `72h`
  - bestes Quintil: `q4` = BTC naeher am 20-Tage-Hoch / Risk-On
  - Mean nach Kosten: ca. `+1.426 USDC` je 100-USDC-Hypothesenhold
  - positive Folds: `5/6`
  - Winrate: ca. `57.4%`
- wichtige Reversion-Kandidaten:
  - `ethbtc_4h_ret_6`, 72h, q0: ca. `+0.722 USDC`, `5/6` Folds
  - `eth_4h_dist_to_20d_high`, 72h, q0: ca. `+0.604 USDC`, `4/5` Folds
  - Orderflow-Schwachequintile, 72h, q1: ca. `+0.467 USDC`, `4/6` Folds

Interpretation: Die bisherigen Momentum-/Leadership-Bestaetigungsstrategien
waren wahrscheinlich zu spaet. Die Daten zeigen eher: ETH ist long-only
interessanter, wenn der BTC-Kontext stabil/risk-on ist und ETH/ETHBTC nicht
bereits aggressiv gechased wird. Das ist nur Trainingsevidenz, kein Freifahrtschein.

Aktueller BRH/ERV-v1-Befund:

- Dateien:
  - `src/research/brh_v1.py`
  - `scripts/run_brh_v1_research.py`
  - `tests/test_brh_v1_research.py`
- `strategy_version = brh_v1_btc_risk_on_eth_reversion_hold_20260701`
- `status = blindtest_completed`
- Training/Walkforward:
  - 7 feste Varianten
  - 5 Varianten eligible
  - alle eligible Varianten hatten 6/6 positive Folds
  - beste Training-PnL-Variante: `brh_dual_btc_risk_on_72h`
    mit ca. `+142.26 USDC`
  - selektiert wurde nach Training-PF:
    `erv_risk_on_orderflow_cooldown_72h`
    mit ca. `+135.41 USDC`, PF ca. `3.95`
- Frozen Blindtest der selektierten Variante:
  - `+4.65 USDC` gesamt
  - `+0.013 USDC/Tag`
  - 22 Trades
  - Profit Factor ca. `1.10`
  - Median Trade PnL ca. `-0.37 USDC`
  - Max Drawdown ca. `26.58 USDC`

Interpretation: BRH/ERV-v1 beweist, dass der Edge-Scan nicht komplett leer war.
Aber die Trainingsstaerke generalisiert zu schwach. Das darf nicht durch
Auswahlwechsel nach Blindtest, Gate-Lockerung oder zweiten Blindtest
"repariert" werden.

## Datenwahrheit

Lokale Rohdaten liegen unter `data/` und werden nicht nach GitHub committed.
Sie sind per `.gitignore` ausgeschlossen.

Aktuell lokal vorhanden:

- `data/candles/ETHUSDC_1m.csv`
- `data/candles/BTCUSDC_1m.csv`
- `data/candles/ETHBTC_1m.csv`
- `data/candles/ETHUSDT_1m.csv`
- `data/candles/USDCUSDT_1m.csv`
- `data/exchange_info/ETHUSDC_exchange_info.json`
- `data/market_features/agg_trades/ETHUSDC/*.csv`
- `data/live_microstructure/ETHUSDC/*.jsonl`

Die 1m-Klines enthalten nicht nur OHLCV, sondern die vollstaendigen Binance
Kline-Felder, u. a. Quote Volume, Trade Count und Taker-Buy-Base/Quote.

Derived Timeframes duerfen nur aus geschlossenen 1m-Kerzen entstehen:

- 5m
- 15m
- 30m
- 1h
- 4h
- 1d

Orderbook/BookTicker/Depth duerfen historisch nicht erfunden werden. Sie duerfen
erst als Backtestfeature verwendet werden, wenn genuegend echte, lokal
gesammelte, zeitstempelsichere Daten vorhanden sind.

## Regeln fuer jede Weiterentwicklung

1. Nur ETHUSDC Spot LONG-only.
2. Kein Short, Futures, Margin, Leverage.
3. Keine echten Orders.
4. Kein Lookahead.
5. Keine Blindtest-Optimierung.
6. Keine separate Smoke-Engine.
7. Keine Gate-Lockerung, nur damit Trades oder 3 USDC/Tag erscheinen.
8. Neue Datenquelle immer einzeln und reportbar einbauen.
9. Erst Training/Walkforward, dann eingefrorener Blindtest.
10. Wenn eine Research-Spur scheitert, dokumentieren und nicht im Kreis
    weiterpatchen.

## UI starten

Windows:

```bat
ETHUSDC_BotV2_UI_starten.bat
```

Direkt:

```bat
python -m src.ui.app
```

Der UI-Button fuer den Full-Backtest ist die echte Entscheidungsstrecke. Die
Smoke-Buttons daneben sind nur verkuerzte technische Varianten desselben
Backtestpfads.

## Pflichtchecks nach Codeaenderungen

```bat
python -m compileall src tests scripts
python -m pytest -q
git diff --check
```

Wenn diese Checks nicht gruen sind, ist der Stand nicht uebergabefaehig.

## GitHub-Regel

Nach GitHub gehoeren:

- `src/`
- `tests/`
- `scripts/`
- `docs/`
- `specs/`
- `README.md`
- `AGENTS.md`
- Projektkonfigurationen wie `pyproject.toml` und `requirements.txt`

Nicht nach GitHub gehoeren:

- `data/`
- `reports/`
- `logs/`
- `data_upload/`
- Python-Caches
- lokale Backtest- oder Research-Reports

Rohdaten werden lokal durch den Bot heruntergeladen/aktualisiert. Ein frischer
Clone soll sauber starten koennen und beim ersten Backtest die benoetigten
Daten neu aufbauen.
