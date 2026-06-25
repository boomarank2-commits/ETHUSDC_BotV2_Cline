from pathlib import Path

import pytest

from src.common.report_paths import get_run_report_dir
from src.data.candle_csv_io import save_candle_dataset_to_csv
from src.data.candle_dataset import CandleDataset
from src.data.candle_quality import EXPECTED_MIN_CANDLES, CandleQualityReport
from src.data.candle_schema import Candle
from src.data.data_catalog import CandleDataCatalogEntry, get_catalog_path, save_data_catalog
from src.data.data_preparation_report import (
    DATA_PREPARATION_REPORT_FILENAME,
    build_data_preparation_report,
    load_data_preparation_report,
    save_data_preparation_report,
)


def _candle(open_time: str) -> Candle:
    return Candle(open_time, 100.0, 110.0, 90.0, 105.0, 1.0)


def _write_dataset_to_catalog(tmp_path: Path, dataset: CandleDataset) -> None:
    csv_path = tmp_path / "candles.csv"
    save_candle_dataset_to_csv(dataset, csv_path)
    save_data_catalog([CandleDataCatalogEntry("ETHUSDC", "1m", str(csv_path))])


def test_report_can_be_created_with_valid_local_test_data(tmp_path: Path) -> None:
    dataset = CandleDataset("ETHUSDC", "1m", [_candle("2026-01-01T00:00:00")])
    _write_dataset_to_catalog(tmp_path, dataset)

    report = build_data_preparation_report("run_20260612_180001")

    assert report.symbol == "ETHUSDC"
    assert report.interval == "1m"


def test_report_contains_derived_timeframe_counts_from_ethusdc_1m(tmp_path: Path) -> None:
    candles = [
        Candle(f"2026-01-01T00:{minute:02d}:00", 100.0, 110.0, 90.0, 105.0, 1.0)
        for minute in range(10)
    ]
    dataset = CandleDataset("ETHUSDC", "1m", candles)
    _write_dataset_to_catalog(tmp_path, dataset)

    report = build_data_preparation_report("run_20260612_180011")

    assert report.ethusdc_1m_available is True
    assert report.derived_timeframes_available is True
    assert report.derived_timeframe_candle_counts == {
        "5m": 2,
        "15m": 0,
        "30m": 0,
        "1h": 0,
        "4h": 0,
        "1d": 0,
    }


def test_missing_optional_data_sources_are_reported_honestly(tmp_path: Path) -> None:
    dataset = CandleDataset("ETHUSDC", "1m", [_candle("2026-01-01T00:00:00")])
    _write_dataset_to_catalog(tmp_path, dataset)

    report = build_data_preparation_report("run_20260612_180012")

    assert report.btcusdc_context_available is False
    assert report.ethbtc_context_available is False
    assert report.trades_available is False
    assert report.agg_trades_available is False
    assert report.bookticker_available is False
    assert report.orderbook_available is False
    assert report.data_source_status == {
        "ETHUSDC 1m": "available",
        "enhanced kline order flow": "available",
        "derived_timeframes": "missing",
        "BTCUSDC context": "missing",
        "ETHBTC context": "missing",
        "ETHUSDT context": "missing",
        "USDCUSDT context": "missing",
        "trades": "rejected_redundant_raw_source",
        "aggTrades": "missing",
        "bookTicker": "not_started",
        "orderbook": "not_started",
    }


def test_report_is_saved_in_run_report_dir(tmp_path: Path) -> None:
    dataset = CandleDataset("ETHUSDC", "1m", [_candle("2026-01-01T00:00:00")])
    _write_dataset_to_catalog(tmp_path, dataset)
    report = build_data_preparation_report("run_20260612_180002")

    report_path = save_data_preparation_report(report)

    assert report_path == get_run_report_dir(report.run_id) / DATA_PREPARATION_REPORT_FILENAME


def test_load_data_preparation_report_loads_same_report(tmp_path: Path) -> None:
    dataset = CandleDataset("ETHUSDC", "1m", [_candle("2026-01-01T00:00:00")])
    _write_dataset_to_catalog(tmp_path, dataset)
    report = build_data_preparation_report("run_20260612_180003")

    save_data_preparation_report(report)

    assert load_data_preparation_report(report.run_id) == report


def test_small_dataset_is_not_usable_for_backtest(tmp_path: Path) -> None:
    dataset = CandleDataset("ETHUSDC", "1m", [_candle("2026-01-01T00:00:00")])
    _write_dataset_to_catalog(tmp_path, dataset)

    report = build_data_preparation_report("run_20260612_180004")

    assert report.usable_for_backtest is False
    assert report.reason is not None


def test_dataset_with_gaps_is_not_usable_for_backtest(tmp_path: Path) -> None:
    dataset = CandleDataset(
        "ETHUSDC",
        "1m",
        [_candle("2026-01-01T00:00:00"), _candle("2026-01-01T00:02:00")],
    )
    _write_dataset_to_catalog(tmp_path, dataset)

    report = build_data_preparation_report("run_20260612_180005")
    assert report.usable_for_backtest is False
    assert report.detected_gaps == 1


def test_missing_catalog_or_csv_is_rejected(tmp_path: Path) -> None:
    catalog_path = get_catalog_path()
    backup_path = catalog_path.with_suffix(".json.prep_backup")
    if backup_path.exists():
        backup_path.unlink()
    if catalog_path.exists():
        catalog_path.replace(backup_path)
    try:
        with pytest.raises(FileNotFoundError):
            build_data_preparation_report("run_20260612_180006")
    finally:
        if backup_path.exists():
            backup_path.replace(catalog_path)

    save_data_catalog([CandleDataCatalogEntry("ETHUSDC", "1m", str(tmp_path / "missing.csv"))])
    with pytest.raises(FileNotFoundError):
        build_data_preparation_report("run_20260612_180007")


def test_invalid_run_id_is_rejected(tmp_path: Path) -> None:
    dataset = CandleDataset("ETHUSDC", "1m", [_candle("2026-01-01T00:00:00")])
    _write_dataset_to_catalog(tmp_path, dataset)

    with pytest.raises(ValueError):
        build_data_preparation_report("../unsafe")


def test_large_gap_free_dataset_is_usable_for_backtest() -> None:
    quality = CandleQualityReport(
        symbol="ETHUSDC",
        interval="1m",
        candle_count=EXPECTED_MIN_CANDLES,
        first_open_time="2026-01-01T00:00:00",
        last_open_time="2029-01-01T00:00:00",
        duplicate_open_times=0,
        sorted_ascending=True,
        detected_gaps=0,
        expected_min_candles=EXPECTED_MIN_CANDLES,
        has_required_lookback=True,
    )

    report = build_data_preparation_report("run_20260612_180008", quality=quality)
    assert report.usable_for_backtest is True
    assert report.reason is None


def test_expected_min_candles_keeps_confirmed_730_365_rule() -> None:
    assert EXPECTED_MIN_CANDLES == (730 + 365) * 24 * 60
