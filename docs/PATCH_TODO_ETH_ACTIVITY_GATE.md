# PATCH TODO: ETH-Regime-Aktivitaetsfreigabe skalieren

Stand: Der Code-Fix ist noch nicht umgesetzt.

Problem:
`src/router/activity_first_router_report.py::_candidate_rejection` blockiert aktuell jeden Kandidaten mit `trades_per_day < 1.0` als `rejected_by_activity`.

Das ist fuer normale Activity-Kandidaten okay, aber fuer ETH-Regime-Kandidaten falsch. In den 14- und 30-Tage-Smokes wurden positive ETH-Regime-Kandidaten nur deshalb nicht im Blindtest ausgefuehrt.

Ziel:
Eine einzige Logik fuer 1d/7d/14d/30d/Full. Unterschied nur die Zeitfenstergroesse.

Regel:
- Standard-Kandidaten behalten `trades_per_day >= 1.0`.
- ETH-Regime-Kandidaten (`candidate.search_pass.startswith("eth_")`) bekommen eine skalierte Mindestaktivitaet.

Vorschlag:
```
min_trades = max(2, min(20, ceil(training_days * 0.20)))
min_active_days = max(1, min(10, ceil(training_days * 0.10)))
```

Dazu neue Helper:
- `_ceil_positive(value)`
- `_training_days_from_result(result)`
- `_active_day_count(trades)`
- `_is_eth_regime_candidate(result)`
- `_eth_regime_activity_minimums(result)`
- `_passes_activity_gate(result)`

Dann in `_candidate_rejection` zuerst:
```
if not _passes_activity_gate(result):
    return "rejected_by_activity"
```

Und in `_search_pass_summary` sowie `_candidate_space_status` nicht mehr direkt `trades_per_day >= 1.0`, sondern `_passes_activity_gate(e.result)` nutzen.

Nach dem Patch:
- `candidate_generation_version` auf `activity_first_v5_scaled_eth_activity_gate` setzen.
- `router_artifact["scaled_eth_activity_gate_used"] = True` setzen.
- Tests fuer ETH-Regime-Low-Activity ergaenzen.
