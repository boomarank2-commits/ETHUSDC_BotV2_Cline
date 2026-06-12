from pathlib import Path

import pytest

from src.data.candle_csv_io import save_candle_dataset_to_csv
from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle
from src.data.data_catalog import CandleDataCatalogEntry, get_catalog_path, save_data_catalog
from src.data.local_candle_loader import (
    build_local_candle_quality_from_catalog,
    load_local_candle_dataset_from_catalog,
)


def _dataset() -> CandleDataset:
    return CandleDataset(
        "ETHUSDC",
        "1m",
        [
            Candle("2026-01-01T00:00:00", 100.0, 110.0, 90.0, 105.0, 1.0),
            Candle("2026-01-01T00:01:00", 105.0, 115.0, 95.0, 110.0, 2.0),
        ],
    )


def _write_catalog_for_csv(csv_path: Path) -> None:
    save_data_catalog([CandleDataCatalogEntry("ETHUSDC", "1m", str(csv_path))])


def test_valid_catalog_and_csv_loads_candle_dataset(tmp_path: Path) -> None:
    csv_path = tmp_path / "candles.csv"
    dataset = _dataset()
    save_candle_dataset_to_csv(dataset, csv_path)
    _write_catalog_for_csv(csv_path)

    assert load_local_candle_dataset_from_catalog() == dataset


def test_quality_report_is_created(tmp_path: Path) -> None:
    csv_path = tmp_path / "candles.csv"
    save_candle_dataset_to_csv(_dataset(), csv_path)
    _write_catalog_for_csv(csv_path)

    report = build_local_candle_quality_from_catalog()

    assert report.symbol == "ETHUSDC"
    assert report.candle_count == 2


def test_missing_catalog_is_rejected() -> None:
    catalog_path = get_catalog_path()
    backup_path = catalog_path.with_suffix(".json.loader_backup")
    if backup_path.exists():
        backup_path.unlink()
    if catalog_path.exists():
        catalog_path.replace(backup_path)
    try:
        with pytest.raises(FileNotFoundError):
            load_local_candle_dataset_from_catalog()
    finally:
        if backup_path.exists():
            backup_path.replace(catalog_path)


def test_catalog_without_matching_entry_is_rejected() -> None:
    save_data_catalog([])

    with pytest.raises(ValueError):
        load_local_candle_dataset_from_catalog()


def test_missing_csv_is_file_not_found_error(tmp_path: Path) -> None:
    _write_catalog_for_csv(tmp_path / "missing.csv")

    with pytest.raises(FileNotFoundError):
        load_local_candle_dataset_from_catalog()


def test_invalid_csv_is_rejected(tmp_path: Path) -> None:
    csv_path = tmp_path / "candles.csv"
    csv_path.write_text(
        "open_time,open,high,low,close,volume\n2026-01-01T00:00:00,-1,1,1,1,1\n",
        encoding="utf-8",
    )
    _write_catalog_for_csv(csv_path)

    with pytest.raises(ValueError):
        load_local_candle_dataset_from_catalog()
