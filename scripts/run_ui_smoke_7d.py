"""Run a 7-day UI-backed smoke test without opening the GUI."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.backtest_ui_controller import BacktestUiSettings, run_backtest_for_ui  # noqa: E402


def _print_json(prefix: str, payload: dict[str, Any]) -> None:
    print(f"{prefix} {json.dumps(payload, ensure_ascii=False, sort_keys=True)}", flush=True)


def _progress(event: dict[str, Any]) -> None:
    _print_json("PROGRESS", event)


def main() -> int:
    result = run_backtest_for_ui(
        BacktestUiSettings(
            stake_quote_amount=100.0,
            profile="normal",
            run_type="smoke_test",
            blindtest_days=7,
        ),
        progress_callback=_progress,
    )
    _print_json("RESULT", result.__dict__)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
