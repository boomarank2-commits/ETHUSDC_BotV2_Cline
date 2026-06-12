"""Download public Binance Spot ETHUSDC 1m klines into local candle CSV files."""

from datetime import UTC, datetime
from pathlib import Path

from src.common.config import CONFIG
from src.common.paths import DATA_DIR
from src.data.binance_kline_client import BinanceKline, fetch_binance_klines
from src.data.candle_csv_io import save_candle_dataset_to_csv
from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle
from src.data.data_catalog import CandleDataCatalogEntry, save_data_catalog

DEFAULT_BINANCE_CANDLE_PATH = DATA_DIR / "candles" / "ETHUSDC_1m.csv"
ONE_MINUTE_MS = 60_000
MAX_EMPTY_PAGES = 1


def binance_kline_to_candle(kline: BinanceKline) -> Candle:
    """Convert a Binance kline into the local Candle contract."""
    open_time = datetime.fromtimestamp(kline.open_time_ms / 1000, tz=UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return Candle(
        open_time=open_time,
        open=kline.open,
        high=kline.high,
        low=kline.low,
        close=kline.close,
        volume=kline.volume,
    )


def download_ethusdc_1m_candles(
    start_time_ms: int,
    end_time_ms: int,
    output_path: Path | None = None,
) -> CandleDataset:
    """Download public ETHUSDC 1m klines, save CSV, and update the data catalog."""
    if start_time_ms <= 0:
        msg = "start_time_ms must be positive"
        raise ValueError(msg)
    if end_time_ms <= start_time_ms:
        msg = "end_time_ms must be greater than start_time_ms"
        raise ValueError(msg)

    target_path = output_path or DEFAULT_BINANCE_CANDLE_PATH
    klines: list[BinanceKline] = []
    current_start = start_time_ms
    previous_next_start: int | None = None
    empty_pages = 0

    while current_start <= end_time_ms:
        page = fetch_binance_klines(
            symbol=CONFIG.symbol,
            interval="1m",
            start_time_ms=current_start,
            end_time_ms=end_time_ms,
            limit=1000,
        )
        if not page:
            empty_pages += 1
            if empty_pages >= MAX_EMPTY_PAGES:
                break
            current_start += ONE_MINUTE_MS
            continue

        empty_pages = 0
        new_klines = [kline for kline in page if kline.open_time_ms >= current_start]
        if not new_klines:
            msg = "Binance pagination did not return new klines"
            raise RuntimeError(msg)
        klines.extend(new_klines)
        next_start = new_klines[-1].open_time_ms + ONE_MINUTE_MS
        if previous_next_start is not None and next_start <= previous_next_start:
            msg = "Binance pagination did not advance"
            raise RuntimeError(msg)
        previous_next_start = next_start
        current_start = next_start

    candles = [binance_kline_to_candle(kline) for kline in klines]
    dataset = CandleDataset(symbol=CONFIG.symbol, interval="1m", candles=candles)
    save_candle_dataset_to_csv(dataset, target_path)
    save_data_catalog([CandleDataCatalogEntry(CONFIG.symbol, "1m", str(target_path))])
    return dataset
