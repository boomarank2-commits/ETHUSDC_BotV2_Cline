"""CSV IO for technical candle datasets."""

import csv
from dataclasses import asdict
from pathlib import Path

from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle

CANDLE_CSV_FIELDS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "close_time",
]
REQUIRED_CANDLE_CSV_FIELDS = ["open_time", "open", "high", "low", "close", "volume"]
ORDER_FLOW_CANDLE_CSV_FIELDS = [
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
]


def candle_csv_has_order_flow_fields(path: Path) -> bool:
    """Return whether a candle CSV preserves Binance kline order-flow columns."""
    if not path.exists():
        return False
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        fieldnames = csv.DictReader(csv_file).fieldnames or []
    return all(field in fieldnames for field in ORDER_FLOW_CANDLE_CSV_FIELDS)


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
            field
            for field in REQUIRED_CANDLE_CSV_FIELDS
            if field not in (reader.fieldnames or [])
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
                    quote_volume=float(row.get("quote_volume") or 0.0),
                    trade_count=int(row.get("trade_count") or 0),
                    taker_buy_base_volume=float(
                        row.get("taker_buy_base_volume") or 0.0
                    ),
                    taker_buy_quote_volume=float(
                        row.get("taker_buy_quote_volume") or 0.0
                    ),
                    close_time=row.get("close_time") or None,
                )
            )
    return CandleDataset(symbol=symbol, interval=interval, candles=candles)
