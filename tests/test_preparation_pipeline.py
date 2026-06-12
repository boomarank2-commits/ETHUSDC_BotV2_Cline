from dataclasses import fields
from pathlib import Path

import pytest

import src.backtest.preparation_pipeline as pipeline_module
import src.data.train_blind_split as split_module
from src.backtest.buy_hold_benchmark import load_buy_hold_benchmark_report
from src.backtest.preparation_pipeline import (
    PreparationPipelineResult,
    run_backtest_preparation_pipeline,
)
from src.backtest.run_progress import load_run_progress
from src.data.candle_csv_io import save_candle_dataset_to_csv
from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle
from src.data.data_catalog import CandleDataCatalogEntry, get_catalog_path, save_data_catalog
from src.data.data_preparation_report import DataPreparationReport
from src.reports.backtest_summary import load_backtest_summary


def _candle(index: int) -> Candle:
    return Candle(f"2026-01-01T00:{index:02d}:00", 100.0, 110.0, 90.0, 105.0, 1.0)


def _dataset(count: int) -> CandleDataset:
    return CandleDataset("ETHUSDC", "1m", [_candle(index) for index in range(count)])


def _write_catalog(tmp_path: Path, dataset: CandleDataset) -> None:
    csv_path = tmp_path / "candles.csv"
    save_candle_dataset_to_csv(dataset, csv_path)
    save_data_catalog([CandleDataCatalogEntry("ETHUSDC", "1m", str(csv_path))])


def _usable_report(run_id: str) -> DataPreparationReport:
    return DataPreparationReport(
        run_id=run_id,
        symbol="ETHUSDC",
        interval="1m",
        candle_count=5,
        first_open_time="2026-01-01T00:00:00",
        last_open_time="2026-01-01T00:04:00",
        detected_gaps=0,
        has_required_lookback=True,
        usable_for_backtest=True,
        reason=None,
    )


@pytest.fixture()
def fast_success_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(split_module, "TRAINING_CANDLE_COUNT", 3)
    monkeypatch.setattr(split_module, "BLINDTEST_CANDLE_COUNT", 2)
    monkeypatch.setattr(split_module, "REQUIRED_CANDLE_COUNT", 5)
    monkeypatch.setattr(pipeline_module, "build_data_preparation_report", _usable_report)
    _write_catalog(tmp_path, _dataset(5))


def test_successful_pipeline_creates_data_preparation_report(fast_success_pipeline: None) -> None:
    result = run_backtest_preparation_pipeline()

    assert Path(result.data_preparation_report_path).is_file()


def test_successful_pipeline_creates_train_blind_split_report(fast_success_pipeline: None) -> None:
    result = run_backtest_preparation_pipeline()

    assert Path(result.train_blind_split_report_path).is_file()


def test_successful_pipeline_creates_buy_hold_benchmark_report(
    fast_success_pipeline: None,
) -> None:
    result = run_backtest_preparation_pipeline()

    assert result.buy_hold_benchmark_report_path is not None
    assert Path(result.buy_hold_benchmark_report_path).is_file()


def test_successful_pipeline_creates_strategy_v0_report(fast_success_pipeline: None) -> None:
    result = run_backtest_preparation_pipeline()

    assert result.strategy_v0_report_path is not None
    assert Path(result.strategy_v0_report_path).is_file()


def test_result_contains_buy_hold_benchmark_report_path(fast_success_pipeline: None) -> None:
    result = run_backtest_preparation_pipeline()

    assert result.buy_hold_benchmark_report_path is not None


def test_loaded_buy_hold_benchmark_has_one_trade(fast_success_pipeline: None) -> None:
    result = run_backtest_preparation_pipeline()

    report = load_buy_hold_benchmark_report(result.run_id)

    assert report.trade_count == 1


def test_successful_pipeline_creates_backtest_summary(fast_success_pipeline: None) -> None:
    result = run_backtest_preparation_pipeline()

    assert result.backtest_summary_path is not None
    assert Path(result.backtest_summary_path).is_file()


def test_result_contains_backtest_summary_path(fast_success_pipeline: None) -> None:
    result = run_backtest_preparation_pipeline()

    assert result.backtest_summary_path is not None


def test_loaded_summary_has_completed_status(fast_success_pipeline: None) -> None:
    result = run_backtest_preparation_pipeline()

    assert load_backtest_summary(result.run_id).status == "completed"


def test_loaded_summary_contains_benchmark_result(fast_success_pipeline: None) -> None:
    result = run_backtest_preparation_pipeline()
    summary = load_backtest_summary(result.run_id)

    assert summary.final_capital is not None
    assert summary.total_pnl is not None


def test_successful_pipeline_sets_completed_status(fast_success_pipeline: None) -> None:
    result = run_backtest_preparation_pipeline()

    assert result.status == "completed"


def test_progress_ends_completed(fast_success_pipeline: None) -> None:
    result = run_backtest_preparation_pipeline()

    assert load_run_progress(result.run_id).status == "completed"


def test_missing_catalog_results_in_failed_or_clear_error() -> None:
    catalog_path = get_catalog_path()
    backup_path = catalog_path.with_suffix(".json.pipeline_backup")
    if backup_path.exists():
        backup_path.unlink()
    if catalog_path.exists():
        catalog_path.replace(backup_path)
    try:
        result = run_backtest_preparation_pipeline()
    finally:
        if backup_path.exists():
            backup_path.replace(catalog_path)

    assert result.status == "failed"
    assert result.error is not None


def test_not_enough_dataset_fails_and_saves_data_report(tmp_path: Path) -> None:
    _write_catalog(tmp_path, _dataset(1))

    result = run_backtest_preparation_pipeline()

    assert result.status == "failed"
    assert Path(result.data_preparation_report_path).is_file()
    assert result.buy_hold_benchmark_report_path is None
    assert result.strategy_v0_report_path is None
    assert result.backtest_summary_path is not None
    assert load_backtest_summary(result.run_id).status == "failed"


def test_hard_error_without_reports_has_no_summary_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_before_run_created(time_budget_minutes: int | None = None) -> None:
        raise RuntimeError("hard initialization failure")

    monkeypatch.setattr(pipeline_module, "initialize_backtest_run", fail_before_run_created)

    result = run_backtest_preparation_pipeline()

    assert result.status == "failed"
    assert result.backtest_summary_path is None


def test_pipeline_result_has_no_trade_pnl_or_signal_fields() -> None:
    field_names = {field.name for field in fields(PreparationPipelineResult)}

    assert "trade" not in field_names
    assert "pnl" not in field_names
    assert "signal" not in field_names


def test_pipeline_result_has_no_short_futures_margin_or_leverage_fields() -> None:
    field_names = {field.name for field in fields(PreparationPipelineResult)}

    assert "short" not in field_names
    assert "futures" not in field_names
    assert "margin" not in field_names
    assert "leverage" not in field_names
