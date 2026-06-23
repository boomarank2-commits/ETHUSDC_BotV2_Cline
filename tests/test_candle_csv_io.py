import csv
from pathlib import Path

import pytest

from src.data.candle_csv_io import (
    CANDLE_CSV_FIELDS,
    load_candle_dataset_from_csv,
    save_candle_dataset_to_csv,
)
from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle


def _dataset() -> CandleDataset:
    return CandleDataset(
        symbol="ETHUSDC",
        interval="1m",
        candles=[
            Candle("2026-01-01T00:00:00Z", 100.0, 110.0, 90.0, 105.0, 1.0),
            Candle("2026-01-01T00:01:00Z", 105.0, 115.0, 95.0, 110.0, 2.0),
        ],
    )


def test_valid_candle_dataset_can_be_saved_and_loaded(tmp_path: Path) -> None:
    csv_path = tmp_path / "candles.csv"
    dataset = _dataset()

    save_candle_dataset_to_csv(dataset, csv_path)

    assert load_candle_dataset_from_csv(csv_path) == dataset


def test_csv_contains_right_header(tmp_path: Path) -> None:
    csv_path = tmp_path / "candles.csv"

    save_candle_dataset_to_csv(_dataset(), csv_path)

    with csv_path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        assert next(reader) == CANDLE_CSV_FIELDS


def test_loaded_data_matches_saved_data(tmp_path: Path) -> None:
    csv_path = tmp_path / "candles.csv"
    dataset = _dataset()

    save_candle_dataset_to_csv(dataset, csv_path)
    loaded_dataset = load_candle_dataset_from_csv(csv_path)

    assert loaded_dataset.candles == dataset.candles


def test_parent_folder_is_created_on_save(tmp_path: Path) -> None:
    csv_path = tmp_path / "nested" / "candles.csv"

    save_candle_dataset_to_csv(_dataset(), csv_path)

    assert csv_path.is_file()


def test_missing_file_is_file_not_found_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_candle_dataset_from_csv(tmp_path / "missing.csv")


def test_missing_required_column_is_rejected(tmp_path: Path) -> None:
    csv_path = tmp_path / "candles.csv"
    csv_path.write_text("open_time,open,high,low,close\n2026-01-01T00:00:00Z,1,1,1,1\n")

    with pytest.raises(ValueError):
        load_candle_dataset_from_csv(csv_path)


def test_invalid_price_value_is_rejected(tmp_path: Path) -> None:
    csv_path = tmp_path / "candles.csv"
    csv_path.write_text("open_time,open,high,low,close,volume\n2026-01-01T00:00:00Z,-1,1,1,1,1\n")

    with pytest.raises(ValueError):
        load_candle_dataset_from_csv(csv_path)


def test_wrong_symbol_on_load_is_rejected(tmp_path: Path) -> None:
    csv_path = tmp_path / "candles.csv"
    save_candle_dataset_to_csv(_dataset(), csv_path)

    with pytest.raises(ValueError):
        load_candle_dataset_from_csv(csv_path, symbol="XRPUSDC")


def test_wrong_interval_on_load_is_rejected(tmp_path: Path) -> None:
    csv_path = tmp_path / "candles.csv"
    save_candle_dataset_to_csv(_dataset(), csv_path)

    with pytest.raises(ValueError):
        load_candle_dataset_from_csv(csv_path, interval="5m")


def test_save_uses_atomic_temp_file_without_leftover(tmp_path: Path) -> None:
    csv_path = tmp_path / "candles.csv"

    save_candle_dataset_to_csv(_dataset(), csv_path)

    assert csv_path.is_file()
    assert not csv_path.with_suffix(".csv.tmp").exists()
