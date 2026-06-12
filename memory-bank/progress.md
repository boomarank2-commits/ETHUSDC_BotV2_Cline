# Progress

## 2026-06-12

Created clean project structure.

Created:
- .clineignore
- .clinerules
- docs
- memory-bank

No bot code created yet.
Old READMEs are not used as truth.

## 2026-06-12 - Foundation test added

Created:
- tests/test_project_foundation.py

Purpose:
- Verify required foundation files exist.
- Verify minimal confirmed truth is present.
- Verify old READMEs are not treated as truth.

No trading logic created.

## 2026-06-12 - Foundation consistency check

Checked:
- .clinerules
- README.md
- docs
- memory-bank

Result:
- No contradictions found in the new project basis.
- ETHUSDC / USDC / Binance Spot / LONG-only is clear.
- 730 days training plus 365 days blindtest is clear.
- Blindtest must not learn.
- No capital stop because of calculated loss.
- UI / Paper / Test Trade / Live come later.
- Old READMEs, old reports, old code and old bot folders are not truth.

## 2026-06-12 - Minimal common skeleton created

Created:
- src/common/paths.py
- src/common/config.py
- src/common/logging.py
- tests/test_common_skeleton.py

Updated:
- memory-bank/techContext.md

Scope:
- Technical project base only.
- No trading code.
- No backtest code.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Test:
- python -m pytest
- Result: 10 passed in 0.03s
