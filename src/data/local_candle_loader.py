"""Load local candle datasets through the data catalog."""

from pathlib import Path

from src.data.candle_csv_io import load_candle_dataset_from_csv
from src.data.candle_dataset import CandleDataset
from src.data.candle_quality import CandleQualityReport, build_candle_quality_report
from src.data.data_catalog import load_data_catalog


def load_local_candle_dataset_from_catalog(
    symbol: str = "ETHUSDC",
    interval: str = "1m",
) -> CandleDataset:
    """Load a local candle dataset referenced by the data catalog."""
    entries = load_data_catalog()
    for entry in entries:
        if entry.symbol == symbol and entry.interval == interval:
            return load_candle_dataset_from_csv(
                Path(entry.path), symbol=entry.symbol, interval=entry.interval
            )

    msg = f"no candle data catalog entry found for {symbol} {interval}"
    raise ValueError(msg)


def build_local_candle_quality_from_catalog(
    symbol: str = "ETHUSDC",
    interval: str = "1m",
) -> CandleQualityReport:
    """Build a candle quality report for a local catalog dataset."""
    dataset = load_local_candle_dataset_from_catalog(symbol=symbol, interval=interval)
    return build_candle_quality_report(dataset)
