# 07_FINAL_ONE_YEAR_BLINDTEST_CONTRACT.md

## Verbindliches Zielbild

Der fertige Bot wird am 365-Tage-Blindtest gemessen.

Die finale Standardstruktur ist:

- 730 Tage Training / Optimierung
- 365 Tage Blindtest
- ein gemeinsamer Backtest-Apparat
- ein gemeinsamer Router
- ein gemeinsamer Kapital-/Zeitkontext
- keine Blindtest-Reoptimierung

## Smoke ist nur Testphase

1 Tag, 7 Tage, 14 Tage und 30 Tage sind nur technische Kurzversionen dieses einen Backtests.

Sie existieren, damit Patches schnell geprüft werden können.

Sie dürfen keine Sonderlogik bekommen.

Sobald der 365-Tage-Blindtest-Prozess stabil ist, sind diese kurzen Fenster nicht mehr die Entscheidungsgrundlage.

## Adaptiv im richtigen Sinn

Adaptiv bedeutet:

- Training lernt Marktsituationen und passende Setups.
- Der Router friert diese Logik ein.
- Der Blindtest erkennt die Situation mit zeit-sicheren Features.
- Der Blindtest wählt setup oder no_trade.
- Der Blindtest lernt nicht aus seinem eigenen Ergebnis.

## Datenbasis

Der Backtest darf langfristig nicht nur auf rohe 1m-Kerzen reduziert werden.

Zulaessig, wenn sauber validiert und lookahead-sicher:

- ETHUSDC 1m-Kerzen
- daraus abgeleitete Timeframes: 5m, 15m, 30m, 1h, 4h, 1d
- vollständige Kline-Felder für Quote-Volumen, Trade Count und Taker-Buy
- ETHUSDC aggTrades
- exchange_info
- Binance-Regeln
- Gebührenmodell
- Slippage-Modell
- BTCUSDC als Marktkontext, falls valide
- ETHBTC als relative ETH-Stärke, falls valide
- ETHUSDT als liquider ETH-Preisfindungskontext, falls valide
- USDCUSDT als Stablecoin-/Quote-Kontext, falls valide
- bookTicker, falls live gesammelt und validiert
- Orderbuchdaten / Snapshots, falls live gesammelt und validiert

BookTicker und Orderbuchdaten dürfen erst genutzt werden, wenn sie historisch für den jeweiligen Zeitpunkt wirklich vorhanden waren. Als praktische Mindestbasis gelten mindestens 30 Tage sauber gesammelte, lückenarme und zeit-sichere Live-Daten.

Ziel der zusätzlichen Daten ist bessere Situationserkennung, nicht künstlich bessere Reports.

Vor jedem Smoke- oder Full-Lauf aus der UI wird dieselbe zentrale
Datenbereitschaft ausgeführt. Fehlende, unvollständige oder veraltete Pflichtdaten
werden geladen/aktualisiert oder blockieren den Lauf. Raw-Trades werden nicht
zusätzlich dupliziert, solange aggTrades und Kline-Trade-Counts die festgelegte
kompakte historische Orderflow-Basis bilden.

## Pool-Regel

Ein Pool aus mehreren Kandidaten ist erlaubt.

Aber der Pool ist kein Kapital-Multiplikator.

Falsch:

- Kandidat A wird gerechnet.
- Kandidat B wird gerechnet.
- Kandidat C wird gerechnet.
- Alle Ergebnisse werden addiert.

Richtig:

- Kandidaten liefern Vorschläge.
- Der Router entscheidet je Zeit-/Kapital-Kontext.
- Überlappende Vorschläge werden auf eine Aktion reduziert.
- Reports zeigen, was übersprungen wurde.

## Nächster Pflichtpatch

Die Pool-Ausführung muss gegen überlappende Vorschläge abgesichert werden.

Pflichtfelder:

- pool_overlap_guard_used
- pool_execution_policy
- pool_raw_proposals
- pool_executed_trades
- pool_skipped_overlaps

## Fertig-Kriterium

Der Bot gilt erst als fertig, wenn der 365-Tage-Blindtest akzeptabel ist, die Reports nachvollziehbar sind und der Nutzer das Ergebnis bewusst übernimmt.
