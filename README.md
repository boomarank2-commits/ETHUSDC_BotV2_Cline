# ETHUSDC Bot V2 - einzige Arbeitswahrheit

Stand: 2026-07-02.

Dieses Projekt ist ausschließlich fuer einen Zweck da:

> ETHUSDC Spot LONG-only auf Binance mit USDC-Kapital so trainieren, dass aus
> 730 Tagen Training eine eingefrorene Strategie / ein eingefrorener
> Kandidatenpool entsteht und danach ein 365-Tage-Blindtest ohne Lernen zeigt,
> ob diese Logik wirklich tragfaehig ist.

Zielwert/Wunsch bleibt: mindestens `3.00 USDC/Tag` im 365-Tage-Blindtest bei
`100 USDC` Einsatzbasis. Das ist kein Versprechen und darf nicht durch
Blindtest-Lernen, Fake-Trades, Gate-Lockerung oder getrennte Backtestpfade
erzwungen werden. Ein ehrlicher negativer oder defensiver Befund ist besser
als ein schoengerechneter Backtest.

## Wichtigste Dateien

- GPT/Codex-Fortsetzung: `docs/GPT_CONTINUATION_GUIDE_20260701.md`
- Operativer Plan: `docs/IMPLEMENTATION_PLAN.md`
- Aktuelle UI-Full-Backtest-Freigabe: ja, aber nur zur Pruefung der neuen
  EREM-defensiven Router-Integration; kein Live/Paper und keine Uebernahme
  ohne positiven, plausiblen 365-Tage-Blindtest.
- Kernregeln: `AGENTS.md`
- Backtest-Vertrag: `specs/07_FINAL_ONE_YEAR_BLINDTEST_CONTRACT.md`

Alte verstreute Truth-/Arena-/Patch-Dateien wurden entfernt. Die aktuelle
Wahrheit steht bewusst nur noch in wenigen Dateien, damit GPT/Codex nicht
zwischen alten Zwischenstaenden hin- und herspringt.

Wenn eine Datei widerspricht, gilt diese Reihenfolge:

1. `README.md`
2. `AGENTS.md`
3. `docs/GPT_CONTINUATION_GUIDE_20260701.md`
4. `docs/IMPLEMENTATION_PLAN.md`
5. `specs/`

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

Die zuletzt untersuchten reinen Profit-Alpha-Spuren sind bewusst nicht
integriert. EREM ist die einzige neue Router-Integration und dient zuerst als
defensives ETH-Exposure-/Drawdown-Zwischenziel:

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
- BRH-v1-DIAG: Post-Mortem-Diagnose wurde gebaut und ausgefuehrt.
  Ergebnis: keine Threshold-Leakage, aber deutliche Gewinnkonzentration und
  Fragilitaet. Aktuelle BRH-v1-Form archivieren; keine BRH-v2 ohne externe
  neue, training-only begruendete Spezifikation.
- BRH Window Selection Edge Check: neuer training-only Pre-v2-Check wurde
  gebaut und lokal ausgefuehrt. Ergebnis: `window_selection_edge_found`.
  BRH/ERV-v1 hat im Training tatsaechlich bessere ETH-Exposure-Fenster
  selektiert als ein einfacher BTC-Risk-On-Baseline-Hold. Aber: bester
  Kandidat nach diesem Check ist wieder die alte v1-Auswahl
  `erv_risk_on_orderflow_cooldown_72h`, die bereits frozen blindgetestet
  wurde und nur schwach positiv war. Deshalb bleibt BRH-v1 archiviert.
- BRH Selection Edge Robustness v2Check: strenger training-only Gatekeeper
  wurde gebaut und lokal ausgefuehrt. Ergebnis:
  `new_training_only_candidate_found`. Genau eine Variante besteht:
  `brh_btc_risk_on_72h`. Das ist nicht die alte verbrauchte v1-Variante.
  Dieser Befund erlaubt hoechstens einen separaten frozen Research-Blindtest
  fuer genau diese Variante; noch keinen UI-Full-Backtest und keine
  Router-Integration.
- BRH BTC-Risk-On Frozen Blindtest: separater research-only Blindtest fuer
  genau `brh_btc_risk_on_72h` wurde gebaut und lokal ausgefuehrt. Ergebnis:
  positiv, aber nicht robust genug:
  `+10.62 USDC`, `+0.029 USDC/Tag`, 26 Trades, PF ca. `1.26`, aber
  Leave-two-out PF ca. `0.85` und Top-2-Gewinnkonzentration ca. `157.6%`.
  Deshalb keine Router-Integration und kein UI-Full-Backtest.
- EREM Exposure Edge Check + Frozen Blindtest + Router-Integration: BRH/ERV
  wurde geschlossen und
  als neues, anderes Research-Thema wurde ETH-Regime-Exposure-Management
  geprueft: ETH halten, aber in BTC-Risk-Off-Phasen flach sein. Training-only
  fand `erem_btc_drawdown_q35_or_ema_below0`; der frozen Blindtest bestaetigte
  robust bessere Drawdown-Vermeidung als Buy-and-Hold. Ergebnis:
  EREM `-0.53 USDC` vs. Buy-and-Hold `-37.00 USDC`, MaxDD `58.69` vs.
  `140.05 USDC`, verteilte Avoided-Loss-Bloecke. Das ist kein 3-USDC/Tag-
  Profit-Edge, aber ein robuster Exposure-/Drawdown-Befund. Nach Nutzer-
  Klarstellung (`3 USDC` ist Wunsch, kein Versprechen) wurde genau dieser
  Kandidat minimal in den gemeinsamen `activity_first_router` integriert:
  `erem_defensive_router_v1_20260702`.
- VEC-v1 Exhaustion Scan: weil der Nutzer ausdruecklich `3 USDC/Tag` Profit-
  Alpha statt nur Exposure-Management will, wurde ein neuer Microstructure-
  Alpha-Pfad getestet: Volume-Climax + Taker-Sell-Exhaustion + Reclaim auf
  geschlossenen 15m/1h Bars, kalibriert nur in Training/Walkforward. Ergebnis:
  `no_vec_training_edge`, 0/4 Varianten bestanden. Die wenigen positiven
  Mini-Ergebnisse hatten nur 2-6 Trades und scheiterten an Mindesttrades,
  Fold-Stabilitaet, Leave-two-out-PF, Top-2-Konzentration und Worst-Fold.
  Deshalb keine frozen VEC-Blindtest-Freigabe, keine Router-Integration und
  kein UI-Full-Backtest.
- AFP-v1 Flow Persistence Scan: nach Arena.ai wurde als erste echte
  aggTrade-Kernspur nicht Climax/Reversion, sondern anhaltende aggressive
  Kauf-Flow-Persistenz getestet. Der Runner prueft zuerst Datenvollstaendigkeit
  und dann einen Training-only Sanity-Kill-Switch, bevor Varianten ueberhaupt
  simuliert werden. Ergebnis:
  `afp_sanity_failed`, 0/6 Sanity-Folds bestanden. Die ETHUSDC
  aggTrade-Minuten sind effektiv vollstaendig; 47.022 Minuten ohne
  aggTrade-Zeile waren echte Null-Trade-Minuten aus den Klines und wurden als
  Null-Flow behandelt. Das Top-Persistenz-Quintil hatte in allen Folds nach
  Kosten negative Forward-PnL. Deshalb keine Varianten-Simulation, kein
  frozen Blindtest, keine Router-Integration und kein UI-Full-Backtest.

Konsequenz:

- keinen neuen UI-Full-Backtest nur fuer tote Profit-Alpha-Spuren starten;
- R2-v2/R2-v3 nicht weiter ueber TP/SL/Hold/Gates erzwingen;
- ERH-v1 nicht weiter ueber Gate-/Exit-/Hold-Tuning retten. Nach
  Next-Open-Korrektur ist der Befund klar negativ.
- naechster sinnvoller Schritt ist nicht UI-Full-Backtest. Nach dem
  schwach-positiven, aber fragilen BTC-Risk-On-Frozen-Blindtest sollte die
  BRH/ERV-Linie nicht integriert werden. Wenn weitergearbeitet wird, dann nur
  mit externer Re-Einschaetzung oder einem klar neuen Research-Thema; kein
  weiteres Nachoptimieren auf diesen Blindtest.
- EREM ist als defensives Zwischenziel jetzt minimal in den gemeinsamen
  Routerpfad integriert. Der naechste UI-Full-Backtest ist deshalb sinnvoll,
  aber nur zur ehrlichen Messung dieser defensiven Integration. Erwartung:
  bessere Risiko-/Drawdown-Struktur; `3 USDC/Tag` bleibt Wunsch/Zielwert,
  nicht Erwartung und nicht Patch-Versprechen.
- VEC-v1 ist ebenfalls kein Uebernahmekandidat. Der naechste sinnvolle Schritt
  ist eine externe Re-Einschaetzung oder ein neuer, klar abgegrenzter
  Research-Scan, der echte aggTrade-Microstructure nutzt statt dieselbe
  Kline-Orderflow-Idee mit gelockerten Gates zu wiederholen.
- AFP-v1 hat diese echte aggTrade-Microstructure-Spur getestet und bereits im
  Sanity-Kill-Switch verworfen. Der naechste Schritt ist nicht ein UI-Backtest
  und nicht eine Gate-Lockerung. Sinnvoll ist jetzt entweder externe
  Re-Einschaetzung mit dem AFP-Report oder die Auswertung des neuen EREM-
  UI-Full-Backtests als defensives Zwischenziel.

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

Aktueller BRH-v1-DIAG-Befund:

- Dateien:
  - `src/research/brh_v1_diagnostics.py`
  - `scripts/run_brh_v1_diagnostics.py`
  - `tests/test_brh_v1_diagnostics.py`
- `strategy_version = brh_v1_attribution_decay_diagnostics_20260702`
- `status = diagnostic_complete`
- Die Blindtest-Quantile wurden gegen Recalculation geprueft:
  `thresholds_training_only = true`.
- Kein klarer Risk-On-Verfuegbarkeits-Kollaps:
  Risk-On-Bars/Tag Blind vs. Training ca. `0.64`.
- Kein klarer 72h-Horizon-Decay:
  Im Blindtest waren 6h/12h/24h/36h/48h im Mittel schlechter als 72h.
- Hauptproblem: PnL-Konzentration / Fragilitaet.
  - Training selected variant:
    - 45 Trades
    - total ca. `+135.41 USDC`
    - Median Trade ca. `+1.95 USDC`
    - Top-2 Trades ca. `36.9%` des Gesamt-PnL
    - Leave-two-out PF ca. `2.86`
  - Blindtest selected variant:
    - 22 Trades
    - total ca. `+4.65 USDC`
    - Median Trade ca. `-0.37 USDC`
    - Top-1 Trade ca. `337%` des Gesamt-PnL
    - Top-2 Trades ca. `572%` des Gesamt-PnL
    - Leave-one-out PF ca. `0.76`
    - Leave-two-out PF ca. `0.53`
- Same-window ETH Attribution:
  fixed Spot-Long hat innerhalb eines gewaehlten Fensters kein eigenes Alpha;
  der Edge kann nur aus besserer Auswahl der ETH-Exposure-Fenster kommen.

Interpretation: Der leicht positive Blindtest ist nicht stabil genug. BRH-v1
darf nicht in UI/Router integriert werden. Eine v2 ist nur erlaubt, wenn eine
neue training-only Spezifikation vorliegt, die Konzentration/Selection-Bias
vor dem Blindtest bestraft. Kein zweiter Blindtest auf alten Varianten.

Aktueller BRH Window Selection Edge Check:

- Dateien:
  - `src/research/brh_window_selection_edge.py`
  - `scripts/run_brh_window_selection_edge_check.py`
  - `tests/test_brh_window_selection_edge.py`
- `strategy_version = brh_window_selection_edge_check_20260702`
- `status = window_selection_edge_found`
- rein training-only; kein neuer Blindtest; keine UI-/Router-Integration.
- Frage des Checks:
  Selektiert BRH-v1 innerhalb derselben Training/Walkforward-Folds bessere
  ETHUSDC-72h-Exposure-Fenster als ein einfacher BTC-Risk-On-Baseline-Hold?
- Ergebnis:
  - `passing_variant_count = 3`
  - bester Kandidat:
    `erv_risk_on_orderflow_cooldown_72h`
  - selected-window mean ca. `+2.52 USDC` je 100-USDC-Fenster
  - all-risk-on baseline mean ca. `+1.08 USDC`
  - non-overlap-risk-on baseline mean ca. `+2.03 USDC`
  - window-selection edge ca. `+1.44 USDC`
  - non-overlap edge ca. `+0.49 USDC`
  - positive Edge-Folds: `6/6`
  - worst Fold Edge ca. `+0.15 USDC`
- Zwei weitere Varianten bestehen knapp mit `5/6` positiven Edge-Folds:
  - `erv_risk_on_ethbtc_dip_72h`
  - `erv_risk_on_any_eth_dip_72h`

Interpretation:

- BRH/ERV ist nicht komplett leer; die Window-Auswahl hat training-only
  messbaren Mehrwert gegen eine naive Risk-On-Baseline.
- Trotzdem ist der beste Kandidat exakt die alte v1-Auswahl. Dieser Kandidat
  wurde bereits frozen blindgetestet und hat nur `+0.013 USDC/Tag` erreicht.
- Deshalb kein neuer UI-Full-Backtest und kein zweiter Blindtest auf dieser
  alten Variante.
- Eine v2 ist nur als neuer research-only Selection-Rule-Runner erlaubt:
  ohne Blindtest, mit Konzentrationsstrafe, ohne alte-v1-Wiederwahl als neue
  Erfolgsmeldung und mit klaren Walkforward-Gates.

Aktueller BRH Selection Edge Robustness v2Check:

- Dateien:
  - `src/research/brh_selection_edge_robustness_v2check.py`
  - `scripts/run_brh_selection_edge_robustness_v2check.py`
  - `tests/test_brh_selection_edge_robustness_v2check.py`
- `strategy_version = brh_selection_edge_robustness_v2check_20260702`
- `status = new_training_only_candidate_found`
- rein training-only; kein neuer Blindtest; keine UI-/Router-Integration.
- Der Check ergaenzt gegenueber dem einfachen Window-Selection-Check:
  - deterministic random/unconditional ETH-72h-Baseline
  - volle ETH Buy-and-Hold-Baseline fuer denselben Validation-Zeitraum
  - Top-1/Top-2-Konzentrationsgrenzen
  - Leave-one/two-out Profit Factor
  - Mindestanzahl Trades
  - PF-Obergrenze als Overfit-Schutz
  - No-Repeat-Regel fuer bereits blindgetestete v1-Varianten
- Ergebnis:
  - `passing_variant_count = 1`
  - passing/bester Kandidat: `brh_btc_risk_on_72h`
  - nicht bereits in v1 blindgetestet
  - 68 Validation-Trades
  - Training/Walkforward-PnL ca. `+138.06 USDC`
  - Training/Walkforward ca. `+0.251 USDC/Tag`
  - PF ca. `2.36`
  - Leave-one-out PF ca. `2.07`
  - Leave-two-out PF ca. `1.89`
  - Top-1 Share ca. `20.9%`
  - Top-2 Share ca. `34.5%`
  - Random-baseline trimmed Edge ca. `+1.49 USDC` je Fenster
  - ETH Buy-and-Hold-Baseline ca. `+0.011 USDC/Tag`
  - Strategie minus Buy-and-Hold ca. `+0.240 USDC/Tag`
- Die alte v1-Auswahl `erv_risk_on_orderflow_cooldown_72h` besteht den
  strengeren Check nicht:
  - zu wenig Trades (`45 < 48`)
  - worst Fold nicht positiv
  - PF ueber Overfit-Obergrenze

Interpretation:

- BRH/ERV-v1 bleibt archiviert.
- Der strengere Check findet keinen Grund, die alte Orderflow-v1 erneut zu
  testen.
- Es gibt aber eine breitere, einfachere Risk-On-Variante, die training-only
  robust genug fuer genau einen spaeteren frozen Research-Blindtest sein kann.
- Dieser Research-Blindtest ist noch nicht gebaut und darf keine Parameter
  veraendern. UI-Full-Backtest bleibt verboten, bis ein Research-Blindtest
  bestanden und bewusst zur Router-Integration freigegeben wurde.

Aktueller BRH BTC-Risk-On Frozen Blindtest:

- Dateien:
  - `src/research/brh_btc_risk_on_frozen_blindtest.py`
  - `scripts/run_brh_btc_risk_on_frozen_blindtest.py`
  - `tests/test_brh_btc_risk_on_frozen_blindtest.py`
- `strategy_version = brh_btc_risk_on_72h_frozen_blindtest_20260702`
- `status = frozen_research_blindtest_completed`
- rein research-only; keine Variantensuche; keine Parameteraenderung; keine
  UI-/Router-Integration.
- Kandidat:
  - `brh_btc_risk_on_72h`
  - aus dem strengen v2Check freigegeben
  - nicht bereits in v1 blindgetestet
- Frozen Blindtest:
  - PnL ca. `+10.62 USDC`
  - ca. `+0.029 USDC/Tag`
  - 26 Trades
  - PF ca. `1.26`
  - Median Trade ca. `+0.49 USDC`
  - Max Drawdown ca. `18.63 USDC`
  - Leave-one-out PF ca. `1.01`
  - Leave-two-out PF ca. `0.85`
  - Top-1 Share ca. `97.7%`
  - Top-2 Share ca. `157.6%`
  - ETH Buy-and-Hold im selben Blindtest ca. `-35.84 USDC`
  - Strategie minus Buy-and-Hold ca. `+0.127 USDC/Tag`
- Entscheidung:
  - `positive_blindtest_edge = true`
  - `robust_blindtest_edge = false`
  - `router_integration_allowed_now = false`
  - `ui_full_backtest_allowed_now = false`

Interpretation:

- Der breite BTC-Risk-On-Kandidat ist besser als der alte BRH-v1-Kandidat und
  besser als ETH Buy-and-Hold im Blindtest-Fenster.
- Er ist aber immer noch sehr weit vom Ziel `3 USDC/Tag` entfernt.
- Der Gewinn ist zu stark auf wenige Trades konzentriert; nach Entfernung der
  zwei besten Trades kippt der PF unter 1.
- Deshalb nicht integrieren, keinen UI-Full-Backtest starten und nicht durch
  Nachoptimieren auf diesen Blindtest retten.

Aktueller EREM Exposure Edge Check:

- Dateien:
  - `src/research/erem_exposure_edge_check.py`
  - `scripts/run_erem_exposure_edge_check.py`
  - `tests/test_erem_exposure_edge_check.py`
- `strategy_version = erem_exposure_edge_check_20260702`
- `status = erem_training_edge_found`
- rein training-only; kein Blindtest; kein UI-/Router-Backtest.
- Neues Ziel:
  - nicht Trade-Alpha pro Entry;
  - sondern ETH-Exposure reduzieren, wenn BTC-Risk-Off erkannt wird;
  - Erfolg relativ zu ETH Buy-and-Hold und Drawdown, nicht absolut zu
    `3 USDC/Tag`.
- Bester Training-only Kandidat:
  - `erem_btc_drawdown_q35_or_ema_below0`
  - EREM Training/Walkforward ca. `+117.65 USDC`
  - Buy-and-Hold in denselben Folds ca. `+12.51 USDC`
  - Strategie minus Buy-and-Hold ca. `+0.163 USDC/Tag`
  - 5/6 Folds mit Return-Verbesserung
  - 6/6 Folds mit Drawdown-Verbesserung
  - Time-in-market ca. `40.7%`
  - Top-1 avoided-loss share ca. `8.4%`
  - Top-2 avoided-loss share ca. `15.3%`
- Damit war genau ein frozen EREM-Research-Blindtest erlaubt.

Aktueller EREM Frozen Blindtest:

- Dateien:
  - `src/research/erem_frozen_blindtest.py`
  - `scripts/run_erem_frozen_blindtest.py`
  - `tests/test_erem_frozen_blindtest.py`
- `strategy_version = erem_frozen_blindtest_20260702`
- `status = erem_frozen_blindtest_completed`
- Kandidat:
  - `erem_btc_drawdown_q35_or_ema_below0`
  - keine Variantensuche
  - keine Parameteraenderung
  - urspruenglich keine UI-/Router-Integration im Research-Run
- Frozen Blindtest:
  - EREM PnL ca. `-0.53 USDC`
  - ETH Buy-and-Hold ca. `-37.00 USDC`
  - Strategie minus Buy-and-Hold ca. `+0.100 USDC/Tag`
  - EREM MaxDD ca. `58.69 USDC`
  - Buy-and-Hold MaxDD ca. `140.05 USDC`
  - Time-in-market ca. `34.9%`
  - Top-1 avoided-loss share ca. `36.2%`
  - Top-2 avoided-loss share ca. `46.5%`
- Entscheidung:
  - `return_not_worse_than_buy_hold = true`
  - `drawdown_better_than_buy_hold = true`
  - `top1_avoided_block_concentration_ok = true`
  - `return_to_maxdd_ratio_better_than_buy_hold = true`
  - `robust_blindtest_edge = true`
  - `router_integration_allowed_now = true`
  - `ui_full_backtest_allowed_now = false` im reinen Research-Report

Interpretation:

- EREM bestaetigt keine 3-USDC/Tag-Profit-Strategie.
- EREM bestaetigt aber robustes Drawdown-/Exposure-Management gegenueber
  passivem ETH-Halten.
- Der Nutzer hat danach klargestellt, dass `3 USDC/Tag` ein Wunsch/Zielwert
  und kein Versprechen ist. Deshalb wurde EREM als defensives Zwischenziel
  akzeptiert.
- EREM wurde danach minimal in den gemeinsamen Routerpfad integriert:
  `erem_defensive_router_v1_20260702`.
- Der aktuelle UI-Full-Backtest sieht EREM jetzt. Er soll als naechster
  Volltest gestartet werden, um dieselbe 730/365-Logik im echten
  Backtestpfad zu pruefen. Keine Uebernahme ohne plausibel positiven Report.

Aktuelle EREM-Router-Integration:

- Datei:
  - `src/router/__init__.py`
- Version:
  - `erem_defensive_router_v1_20260702`
- Kandidat:
  - `erem_btc_drawdown_q35_or_ema_below0`
- Familie:
  - `erem_exposure_management`
- Regeln:
  - nur Training kalibriert Thresholds;
  - Blindtest bleibt eingefroren;
  - keine Variantensuche im Blindtest;
  - keine alten BRH/ERV/VEC/AFP-Gates werden gelockert;
  - Smoke/Full bleiben derselbe Routerpfad.
- Report-Sichtbarkeit:
  - `router_artifact.erem_defensive_router_integration`
  - `rejection_summary.erem_defensive_router_integration`
  - `selected_setups[0].strategy_family = erem_exposure_management`
  - UI-Summary zeigt diese Setup-Familie statt sie hinter
    `activity_first_router` zu verstecken.
- Short-Smokes koennen EREM deaktivieren, wenn zu wenig Trainingsdauer fuer
  die Training-only Kalibrierung vorhanden ist. Das ist kein zweiter Pfad,
  sondern derselbe Pfad mit zu kurzem Fenster.

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
