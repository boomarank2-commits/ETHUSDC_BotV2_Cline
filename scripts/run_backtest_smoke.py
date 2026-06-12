"""Run the real UI backend workflow without opening the GUI."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.candle_csv_io import load_candle_dataset_from_csv  # noqa: E402
from src.data.data_catalog import get_catalog_path, load_data_catalog  # noqa: E402
from src.data.train_blind_split import REQUIRED_CANDLE_COUNT  # noqa: E402
from src.ui.backtest_ui_controller import BacktestUiSettings, run_backtest_for_ui  # noqa: E402


def _print_json(prefix: str, payload: dict[str, Any]) -> None:
    print(f"{prefix} {json.dumps(payload, ensure_ascii=False, sort_keys=True)}", flush=True)


def _progress(event: dict[str, Any]) -> None:
    _print_json("PROGRESS", event)


def _diagnose_data() -> None:
    csv_path = Path("data/candles/ETHUSDC_1m.csv")
    print(f"REQUIRED_CANDLE_COUNT={REQUIRED_CANDLE_COUNT}", flush=True)
    print(f"CSV_EXISTS={csv_path.exists()} CSV_PATH={csv_path}", flush=True)
    if csv_path.exists():
        dataset = load_candle_dataset_from_csv(csv_path, symbol="ETHUSDC", interval="1m")
        print(f"CSV_CANDLE_COUNT={len(dataset.candles)}", flush=True)
        print(f"CSV_FIRST={dataset.candles[0].open_time if dataset.candles else None}", flush=True)
        print(f"CSV_LAST={dataset.candles[-1].open_time if dataset.candles else None}", flush=True)
    catalog_path = get_catalog_path()
    print(f"CATALOG_EXISTS={catalog_path.exists()} CATALOG_PATH={catalog_path}", flush=True)
    if catalog_path.exists():
        print(f"CATALOG={load_data_catalog()}", flush=True)


def main() -> int:
    _diagnose_data()
    result = run_backtest_for_ui(
        BacktestUiSettings(stake_quote_amount=100.0, profile="normal"),
        progress_callback=_progress,
    )
    _print_json("RESULT", result.__dict__)
    _diagnose_data()
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
