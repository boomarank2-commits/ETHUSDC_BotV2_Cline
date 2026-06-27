# Pflichtregeln für jeden Agenten

1. Zuerst vollständig `README.md` lesen. Es ist die einzige normative Wahrheit.
2. Nur danach dürfen Specs, Docs oder Memory-Dateien als Hintergrund gelesen
   werden. Bei Widerspruch ist die README verbindlich.
3. Es gibt nur den Activity-First-Backtestpfad. Keine V0/V1/Cluster-/Buy-and-
   Hold-Engine, kein Fallback und keine getrennte Smoke-Engine erstellen.
4. ETHUSDC, Binance Spot, LONG-only und USDC sind fest. Keine echten Orders,
   Futures, Margin, Leverage, Shorts, Fake-Trades, Lookahead oder
   Blindtest-Lernen.
5. Neue Daten immer einzeln, training-only, lookahead-sicher und mit Report
   einbauen. Keine Gates lockern, um Trades oder 3 USDC/Tag zu erzwingen.
6. Rohdaten und große lokale Reports nie committen.
7. Nach jeder Codeänderung zwingend `python -m compileall src tests` und
   `python -m pytest -q` ausführen.
