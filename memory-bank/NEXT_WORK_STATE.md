# Next Work State

- Aktueller Auftrag abgeschlossen: Derived-Timeframes vom reinen Datenstatus an Router-Kandidatendiagnosen angeschlossen.
- Vorher wurden 5m/15m/30m/1h/4h/1d nur in `data_preparation_report.json` gezaehlt; Router und Kandidatensuche bekamen nur 1m-Candles.
- Neu: zeit-sichere Feature-Snapshots je Trainings-Entry aus der jeweils zuletzt vollstaendig geschlossenen HTF-Kerze.
- Router-Report zeigt `derived_timeframes_available`, `derived_timeframes_used_by_router`, `used_timeframes` und `missing_timeframe_reason`.
- Nutzung ist absichtlich nur Diagnose: keine Gate-, Score-, Kandidaten-, Pool- oder Trade-Aenderung.
- Pool-Overlap-Guard und gemeinsamer Smoke-/Full-Pfad bleiben unveraendert.
- Tests gruen: `python -m compileall src tests`; `python -m pytest -q`.
- Nicht erneut analysieren: keine ganzen Reports/Data/Logs, keine alten Bot-Dateien, kein Full-Backtest durch Cline.
- Naechster Schritt: einen UI-nahen Smoke nur zur Report-/Coverage-Pruefung starten; danach training-only untersuchen, ob einzelne HTF-Metriken Kandidaten sinnvoll trennen, bevor sie Scores oder Gates beeinflussen.
