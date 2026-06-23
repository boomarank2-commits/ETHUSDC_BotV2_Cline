from pathlib import Path

from src.common.paths import CONFIGS_DIR, DATA_DIR, MEMORY_BANK_DIR, PROJECT_ROOT, REPORTS_DIR
from src.common.runtime_state import RuntimeState, load_runtime_state, save_runtime_state
from src.data.data_catalog import CandleDataCatalogEntry, load_data_catalog, save_data_catalog
from src.maintenance.clean_project_data import clean_downloaded_data_and_reports


def test_clean_deletes_downloaded_data_and_reports_but_keeps_project_files() -> None:
    candle_path = DATA_DIR / "candles" / "ETHUSDC_1m.csv"
    report_path = REPORTS_DIR / "backtests" / "run_test" / "backtest_summary.json"
    memory_path = MEMORY_BANK_DIR / "keep.md"
    code_marker = PROJECT_ROOT / "src" / "keep_marker.txt"
    for path in (candle_path, report_path, memory_path, code_marker):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    save_data_catalog([CandleDataCatalogEntry("ETHUSDC", "1m", str(candle_path))])
    save_runtime_state(RuntimeState("run_test", "completed", None))

    result = clean_downloaded_data_and_reports()

    assert result.message.startswith("Clean-Zustand")
    assert not candle_path.exists()
    assert not report_path.exists()
    assert memory_path.exists()
    assert code_marker.exists()
    assert load_data_catalog() == []
    assert load_runtime_state().status == "idle"


def test_clean_keeps_config_directory_structure() -> None:
    clean_downloaded_data_and_reports()

    assert CONFIGS_DIR.exists()
    assert (CONFIGS_DIR / "data_catalog.json").exists()
    assert (CONFIGS_DIR / "runtime_state.json").exists()