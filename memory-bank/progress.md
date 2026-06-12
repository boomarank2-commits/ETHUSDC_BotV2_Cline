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

## 2026-06-12 - Blindtest and Test Trade purpose documented

Updated documentation:
- docs/BACKTEST_TRUTH.md
- docs/UI_TRUTH.md
- memory-bank/productContext.md

Confirmed additions:
- Blindtest should later provide an expectation frame for Paper and Live, not only total profit or loss.
- Paper/Live results clearly worse or better than the blindtest frame are analysis triggers.
- Later Test Trade button means exactly one complete trade after conscious configuration takeover, with diagnostic comparison data, then automatic stop.

Scope:
- Documentation only.
- No code changed.

## 2026-06-12 - Blindtest expectation report schema created

Created:
- src/reports/blindtest_expectation_schema.py
- tests/test_blindtest_expectation_schema.py

Adjusted:
- .gitignore now ignores only root runtime reports via /reports/ so src/reports/ can be versioned.

Purpose:
- Technical schema for future blindtest expectation reports.
- Stores monthly results and expectation range fields.
- Allows negative pnl, final_result and total_pnl.
- Rejects negative trade and no_trade counts.

Scope:
- Schema and validation only.
- No trading code.
- No backtest calculation.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 30 passed in 0.06s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 22 files already formatted.

## 2026-06-12 - Blindtest expectation report IO created

Created:
- src/reports/blindtest_expectation_io.py
- tests/test_blindtest_expectation_io.py

Purpose:
- Save BlindtestExpectationSummary as readable JSON in reports/backtests/<run_id>/blindtest_expectation.json.
- Load the same JSON back through the schema.

Scope:
- Technical writer/reader only.
- No trading code.
- No backtest calculation.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 36 passed in 0.07s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 24 files already formatted.

## 2026-06-12 - Backtest run request schema created

Created:
- src/backtest/run_request.py
- tests/test_backtest_run_request.py

Purpose:
- Technical request schema for a later Backtest start.
- Validates confirmed ETHUSDC / USDC / Binance Spot / 730 / 365 settings.
- Rejects forbidden modes and unsafe run_id values.

Scope:
- Schema and validation only.
- No trading code.
- No backtest execution.
- No backtest calculation.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 50 passed in 0.08s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 26 files already formatted.

## 2026-06-12 - Backtest run request IO created

Created:
- src/backtest/run_request_io.py
- tests/test_backtest_run_request_io.py

Purpose:
- Save BacktestRunRequest as readable JSON in reports/backtests/<run_id>/run_request.json.
- Load the same JSON back through the request schema.

Scope:
- Technical writer/reader only.
- No trading code.
- No backtest execution.
- No backtest calculation.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 58 passed in 0.10s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 28 files already formatted.

## 2026-06-12 - Backtest run initialization created

Created:
- src/backtest/run_initializer.py
- tests/test_backtest_run_initializer.py

Purpose:
- Create a new run_id.
- Create a default BacktestRunRequest.
- Create the Run-Report folder.
- Save run_request.json.
- Set runtime_state.json to running with active_run_id.

Scope:
- Technical initialization only.
- No trading code.
- No real backtest.
- No backtest calculation.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 68 passed in 0.13s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 30 files already formatted.

## 2026-06-12 - Backtest run finalization created

Created:
- src/backtest/run_finalizer.py
- tests/test_backtest_run_finalizer.py

Purpose:
- Mark a run as completed in runtime_state.json.
- Mark a run as failed in runtime_state.json with last_error.
- Ensure the Run-Report folder exists.

Scope:
- Technical finalization only.
- No trading code.
- No real backtest.
- No backtest calculation.
- No strategy.
- No data logic.
- No Binance connection.
- No UI.

Tests:
- python -m pytest: 76 passed in 0.15s
- python -m ruff check . --no-cache: All checks passed.
- python -m ruff format --check . --no-cache: 32 files already formatted.

## 2026-06-12 - Short handoff rules added

Updated:
- .clinerules/04-token-discipline.md
- .clinerules/05-testing-and-handoff.md

Purpose:
- Final reports max 10 lines.
- Use Changed / Tests / Result / Next format.
- Avoid repeated long negative lists unless there is risk.
- Closely related files may be handled in one task.

## 2026-06-12 - Backtest run progress created

Created:
- src/backtest/run_progress.py
- tests/test_backtest_run_progress.py

Purpose:
- Save and load technical run progress in reports/backtests/<run_id>/progress.json.

Tests:
- python -m pytest
- python -m ruff check . --no-cache
- python -m ruff format --check . --no-cache

## 2026-06-12 - Candle schema and dataset validation created

Created:
- src/data/candle_schema.py
- src/data/candle_dataset.py
- tests/test_candle_schema.py
- tests/test_candle_dataset.py

Purpose:
- Validate technical ETHUSDC 1m candle data contracts before any later data loading.

## 2026-06-12 - Candle CSV IO created

Created:
- src/data/candle_csv_io.py
- tests/test_candle_csv_io.py

Purpose:
- Save and load local ETHUSDC 1m candle datasets as CSV without download or Binance access.

## 2026-06-12 - Candle quality report created

Created:
- src/data/candle_quality.py
- tests/test_candle_quality.py

Purpose:
- Build a technical quality report for local ETHUSDC 1m CandleDataset data.

## 2026-06-12 - Local candle data catalog created

Created:
- src/data/data_catalog.py
- tests/test_data_catalog.py

Purpose:
- Reference local ETHUSDC 1m candle CSV files via configs/data_catalog.json.

## 2026-06-12 - Local candle loader created

Created:
- src/data/local_candle_loader.py
- tests/test_local_candle_loader.py

Purpose:
- Load local ETHUSDC 1m CandleDataset data through configs/data_catalog.json and build quality reports.

## 2026-06-12 - Data preparation report created

Created:
- src/data/data_preparation_report.py
- tests/test_data_preparation_report.py

Purpose:
- Save/load a technical local candle data readiness report per run.

## 2026-06-12 - Test runtime optimized

Changed:
- tests/test_candle_quality.py
- src/data/candle_quality.py

Purpose:
- Avoid generating a full 730+365 day candle list in unit tests while keeping EXPECTED_MIN_CANDLES unchanged.

## 2026-06-12 - Data preparation runtime optimized

Changed:
- tests/test_data_preparation_report.py
- src/data/data_preparation_report.py

Purpose:
- Avoid generating and writing a full 730+365 day candle CSV in unit tests while keeping EXPECTED_MIN_CANDLES unchanged.

## 2026-06-12 - Train/blind candle split created

Created:
- src/data/train_blind_split.py
- tests/test_train_blind_split.py

Purpose:
- Split ETHUSDC 1m CandleDataset into technical 730 day training and 365 day blindtest windows.

## 2026-06-12 - Train/blind split report created

Created:
- src/data/train_blind_split_report.py
- tests/test_train_blind_split_report.py

Purpose:
- Save/load technical run report for training and blindtest candle windows.

## 2026-06-12 - Backtest preparation pipeline created

Created:
- src/backtest/preparation_pipeline.py
- tests/test_preparation_pipeline.py

Purpose:
- Run technical preparation: initialize run, load local candles, save data and split reports, update progress, finalize run.

## 2026-06-12 - Buy-and-Hold benchmark created

Created:
- src/backtest/buy_hold_benchmark.py
- tests/test_buy_hold_benchmark.py

Purpose:
- Calculate and save a simple LONG-only Spot Buy-and-Hold benchmark for the blindtest window.

## 2026-06-12 - Preparation pipeline benchmark extended

Changed:
- src/backtest/preparation_pipeline.py
- tests/test_preparation_pipeline.py

Purpose:
- Successful preparation now also saves buy_hold_benchmark_report.json.
