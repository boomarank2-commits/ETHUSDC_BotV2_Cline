from dataclasses import fields
from pathlib import Path

import pytest

import src.backtest.preparation_pipeline as pipeline_module
import src.data.train_blind_split as split_module
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
from src.data.train_blind_split_report import load_train_blind_split_report
from src.reports.backtest_summary import load_backtest_summary
from src.router.activity_first_router_report import load_activity_first_router_report


def _candle(index: int) -> Candle:
    close = 100.0 + index * 0.05
    return Candle(
        f"2026-01-01T00:{index:02d}:00",
        close,
        close + 1.0,
        close - 1.0,
        close,
        1.0,
        quote_volume=100.0 + index,
        trade_count=10 + index,
        taker_buy_base_volume=0.5,
        taker_buy_quote_volume=50.0,
    )


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


def test_pipeline_creates_only_activity_first_reports(
    fast_success_pipeline: None,
) -> None:
    result = run_backtest_preparation_pipeline()

    assert Path(result.data_preparation_report_path).is_file()
    assert Path(result.train_blind_split_report_path).is_file()
    assert result.activity_first_router_report_path is not None
    assert Path(result.activity_first_router_report_path).is_file()
    assert result.backtest_summary_path is not None
    assert Path(result.backtest_summary_path).is_file()


def test_pipeline_uses_package_activity_first_router_patch_layer() -> None:
    assert pipeline_module.build_activity_first_router_report.__module__ == "src.router"


def test_smoke_pipeline_uses_same_activity_router_with_short_split(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(split_module, "CANDLES_PER_DAY_1M", 2)
    monkeypatch.setattr(pipeline_module, "build_data_preparation_report", _usable_report)
    _write_catalog(tmp_path, _dataset(50))
    captured: dict[str, object] = {}
    original_activity_router = pipeline_module.build_activity_first_router_report

    def capturing_activity_router(run_id, split, **kwargs):
        captured["engine"] = "activity_first_router"
        captured["training_candles"] = len(split.training_candles)
        captured["blindtest_candles"] = len(split.blindtest_candles)
        return original_activity_router(run_id, split, **kwargs)

    monkeypatch.setattr(
        pipeline_module,
        "build_activity_first_router_report",
        capturing_activity_router,
    )

    result = run_backtest_preparation_pipeline(run_type="smoke_test", blindtest_days=7)
    split_report = load_train_blind_split_report(result.run_id)
    summary = load_backtest_summary(result.run_id)
    activity_report = load_activity_first_router_report(result.run_id)

    assert captured == {
        "engine": "activity_first_router",
        "training_candles": 28,
        "blindtest_candles": 14,
    }
    assert split_report.training_candle_count == 28
    assert split_report.blindtest_candle_count == 14
    assert summary.run_type == "smoke_test"
    assert summary.selected_family == "activity_first_router"
    assert activity_report.router_artifact["run_type"] == "smoke_test"
    assert activity_report.router_artifact["smoke_test_not_performance_proof"] is True


def test_pipeline_progress_has_no_parallel_strategy_phase(
    fast_success_pipeline: None,
) -> None:
    events: list[dict] = []

    result = run_backtest_preparation_pipeline(progress_callback=events.append)

    phases = {event.get("phase") for event in events}
    assert result.status == "completed"
    assert "activity_first_router_started" in phases
    assert "activity_first_router_completed" in phases
    assert "strategy_v0_started" not in phases
    assert "strategy_v1_training_started" not in phases
    assert "buyhold_started" not in phases


def test_not_enough_dataset_fails_without_alternate_engine_reports(tmp_path: Path) -> None:
    _write_catalog(tmp_path, _dataset(1))

    result = run_backtest_preparation_pipeline()

    assert result.status == "failed"
    assert Path(result.data_preparation_report_path).is_file()
    assert result.activity_first_router_report_path is None
    assert result.backtest_summary_path is not None
    assert load_backtest_summary(result.run_id).status == "failed"


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


def test_pipeline_result_exposes_one_router_report_path() -> None:
    field_names = {field.name for field in fields(PreparationPipelineResult)}

    assert "activity_first_router_report_path" in field_names
    assert not {"strategy_v0_report_path", "strategy_v1_report_path", "cluster_router_report_path", "buy_hold_benchmark_report_path"} & field_names
