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

## 2026-06-12 - Minimal quality checks stabilized

Checked:
- python -m pytest
- python -m ruff check .
- python -m ruff format --check .

Adjusted:
- Ruff-only import / format cleanup.

Final result:
- pytest: 10 passed in 0.04s
- ruff check: All checks passed.
- ruff format --check: 13 files already formatted.

Scope:
- Technical quality standard only.
- No trading code.
- No backtest code.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

## 2026-06-12 - Run identity and report paths created

Created:
- src/common/run_identity.py
- src/common/report_paths.py
- tests/test_run_identity_and_report_paths.py

Purpose:
- Technical run IDs.
- Isolated report directories under reports/backtests/<run_id>.
- Minimal run_id validation against unsafe paths.

Scope:
- Technical run/report foundation only.
- No trading code.
- No backtest code.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 16 passed in 0.04s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 16 files already formatted.

## 2026-06-12 - Runtime state foundation created

Created:
- src/common/runtime_state.py
- tests/test_runtime_state.py

Purpose:
- Technical runtime state file at configs/runtime_state.json.
- Minimal status validation for idle, running, completed and failed.
- Minimal active_run_id validation against unsafe paths.

Scope:
- Technical runtime-state foundation only.
- No trading code.
- No backtest code.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 23 passed in 0.05s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 18 files already formatted.
