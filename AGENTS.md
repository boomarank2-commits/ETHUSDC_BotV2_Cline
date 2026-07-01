# Pflichtregeln fuer jeden Agenten

1. Zuerst vollstaendig `README.md` lesen. Es ist die einzige normative Wahrheit.
2. Danach `docs/GPT_CONTINUATION_GUIDE_20260701.md` lesen.
3. Specs, Docs und Memory-Dateien sind nur Hintergrund. Bei Widerspruch gewinnt
   immer `README.md`.
4. Es gibt nur den Activity-First-Backtestpfad. Keine V0/V1/Cluster-/Buy-and-
   Hold-Engine, kein Fallback und keine getrennte Smoke-Engine erstellen.
5. ETHUSDC, Binance Spot, LONG-only und USDC sind fest. Keine echten Orders,
   Futures, Margin, Leverage, Shorts, Fake-Trades, Lookahead oder
   Blindtest-Lernen.
6. Neue Daten immer einzeln, training-only, lookahead-sicher und mit Report
   einbauen. Keine Gates lockern, um Trades oder 3 USDC/Tag zu erzwingen.
7. Rohdaten, lokale Upload-ZIPs und grosse lokale Reports nie committen.
8. Tote Research-Spuren nicht erneut ueber TP/SL/Hold/Gates erzwingen:
   Attempt 053, ERRO-L v1, ECMD-L v1 und EPX-L/R2-v2/R2-v3 sind nicht
   integrationsfaehig.
9. Nach jeder Codeaenderung zwingend ausfuehren:

```bat
python -m compileall src tests scripts
python -m pytest -q
git diff --check
```
