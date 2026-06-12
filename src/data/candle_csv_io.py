"""CSV IO for technical candle datasets."""

import csv
from dataclasses import asdict
from pathlib import Path

from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle

CANDLE_CSV_FIELDS = ["open_time", "open", "high", "low", "close", "volume"]


def save_candle_dataset_to_csv(dataset: CandleDataset, path: Path) -> Path:
    """Save a candle dataset to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CANDLE_CSV_FIELDS)
        writer.writeheader()
        for candle in dataset.candles:
            writer.writerow(asdict(candle))
    temp_path.replace(path)
    return path


def load_candle_dataset_from_csv(
    path: Path,
    symbol: str = "ETHUSDC",
    interval: str = "1m",
) -> CandleDataset:
    """Load a candle dataset from CSV and validate it."""
    candles: list[Candle] = []
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        missing_fields = [
            field for field in CANDLE_CSV_FIELDS if field not in (reader.fieldnames or [])
        ]
        if missing_fields:
            msg = f"missing required candle CSV fields: {', '.join(missing_fields)}"
            raise ValueError(msg)

        for row in reader:
            candles.append(
                Candle(
                    open_time=row["open_time"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )
    return CandleDataset(symbol=symbol, interval=interval, candles=candles)
