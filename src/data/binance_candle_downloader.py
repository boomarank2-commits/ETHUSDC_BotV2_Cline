"""Download public Binance Spot ETHUSDC 1m klines into local candle CSV files."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from src.common.config import CONFIG
from src.common.paths import DATA_DIR
from src.data.binance_kline_client import BinanceKline, fetch_binance_klines
from src.data.candle_csv_io import load_candle_dataset_from_csv, save_candle_dataset_to_csv
from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle
from src.data.data_catalog import CandleDataCatalogEntry, upsert_data_catalog_entry
from src.data.train_blind_split import REQUIRED_CANDLE_COUNT

DEFAULT_BINANCE_CANDLE_PATH = DATA_DIR / "candles" / "ETHUSDC_1m.csv"
DEFAULT_CONTEXT_CANDLE_PATHS = {
    "BTCUSDC": DATA_DIR / "candles" / "BTCUSDC_1m.csv",
    "ETHBTC": DATA_DIR / "candles" / "ETHBTC_1m.csv",
    "ETHUSDT": DATA_DIR / "candles" / "ETHUSDT_1m.csv",
    "USDCUSDT": DATA_DIR / "candles" / "USDCUSDT_1m.csv",
}
ONE_MINUTE_MS = 60_000
MAX_EMPTY_PAGES = 1
MAX_RETRIES = 3
REQUEST_TIMEOUT_SECONDS = 30
SAVE_EVERY_PAGES = 25


def binance_kline_to_candle(kline: BinanceKline) -> Candle:
    """Convert a Binance kline into the local Candle contract."""
    open_time = datetime.fromtimestamp(kline.open_time_ms / 1000, tz=UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    close_time = (
        datetime.fromtimestamp(kline.close_time_ms / 1000, tz=UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        if kline.close_time_ms is not None
        else None
    )
    return Candle(
        open_time=open_time,
        open=kline.open,
        high=kline.high,
        low=kline.low,
        close=kline.close,
        volume=kline.volume,
        quote_volume=kline.quote_volume,
        trade_count=kline.trade_count,
        taker_buy_base_volume=kline.taker_buy_base_volume,
        taker_buy_quote_volume=kline.taker_buy_quote_volume,
        close_time=close_time,
    )


def _open_time_to_ms(open_time: str) -> int:
    normalized = open_time.replace("Z", "+00:00")
    return int(datetime.fromisoformat(normalized).timestamp() * 1000)


def _utc_now_ms() -> int:
    return int(datetime.now(tz=UTC).timestamp() * 1000)


def _save_dataset_and_catalog(dataset: CandleDataset, target_path: Path) -> None:
    save_candle_dataset_to_csv(dataset, target_path)
    upsert_data_catalog_entry(CandleDataCatalogEntry(dataset.symbol, "1m", str(target_path)))


def _default_candle_path(symbol: str) -> Path:
    if symbol == CONFIG.symbol:
        return DEFAULT_BINANCE_CANDLE_PATH
    return DEFAULT_CONTEXT_CANDLE_PATHS[symbol]


def _dataset_by_open_time(dataset: CandleDataset | None = None) -> dict[str, Candle]:
    if dataset is None:
        return {}
    return {candle.open_time: candle for candle in dataset.candles}


def _dataset_from_map(candles_by_open_time: dict[str, Candle], symbol: str = CONFIG.symbol) -> CandleDataset:
    return CandleDataset(
        symbol,
        "1m",
        [candles_by_open_time[key] for key in sorted(candles_by_open_time)],
    )


def _emit_progress(
    progress_callback: Callable[[dict], None] | None,
    loaded_candles: int,
    expected_candles: int,
    last_kline: BinanceKline,
    mode: str,
    retry_attempt: int = 0,
    max_retries: int = MAX_RETRIES,
    message: str | None = None,
    symbol: str = CONFIG.symbol,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        {
            "symbol": symbol,
            "interval": "1m",
            "phase": "data_download",
            "mode": mode,
            "retry_attempt": retry_attempt,
            "max_retries": max_retries,
            "loaded_candles": loaded_candles,
            "expected_candles": expected_candles,
            "progress_pct": min(100.0, loaded_candles / expected_candles * 100),
            "last_open_time": binance_kline_to_candle(last_kline).open_time,
            "message": message or f"{symbol} 1m {mode}: {loaded_candles}/{expected_candles}",
        }
    )


def _emit_retry_progress(
    progress_callback: Callable[[dict], None] | None,
    retry_attempt: int,
    start_time_ms: int,
    mode: str,
    error: Exception,
    symbol: str = CONFIG.symbol,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        {
            "symbol": symbol,
            "interval": "1m",
            "phase": "data_download",
            "mode": mode,
            "retry_attempt": retry_attempt,
            "max_retries": MAX_RETRIES,
            "loaded_candles": 0,
            "expected_candles": 0,
            "progress_pct": None,
            "last_open_time": None,
            "message": f"Binance Timeout/Fehler, Retry {retry_attempt}/{MAX_RETRIES}: {error}",
            "start_time_ms": start_time_ms,
        }
    )


def _fetch_page_with_retries(
    start_time_ms: int,
    end_time_ms: int,
    progress_callback: Callable[[dict], None] | None,
    mode: str,
    symbol: str = CONFIG.symbol,
) -> list[BinanceKline]:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fetch_binance_klines(
                symbol=symbol,
                interval="1m",
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                limit=1000,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as error:  # noqa: BLE001
            last_error = error
            _emit_retry_progress(progress_callback, attempt, start_time_ms, mode, error, symbol=symbol)
    if last_error is None:
        msg = "Binance request failed without error detail"
        raise RuntimeError(msg)
    raise last_error


def _fetch_klines_range(
    start_time_ms: int,
    end_time_ms: int,
    progress_callback: Callable[[dict], None] | None,
    mode: str,
    symbol: str = CONFIG.symbol,
) -> list[BinanceKline]:
    klines: list[BinanceKline] = []
    current_start = start_time_ms
    expected_candles = max(1, ((end_time_ms - start_time_ms) // ONE_MINUTE_MS) + 1)
    previous_next_start: int | None = None
    empty_pages = 0

    while current_start <= end_time_ms:
        page = _fetch_page_with_retries(current_start, end_time_ms, progress_callback, mode, symbol=symbol)
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
        _emit_progress(progress_callback, len(klines), expected_candles, new_klines[-1], mode, symbol=symbol)
        next_start = new_klines[-1].open_time_ms + ONE_MINUTE_MS
        if previous_next_start is not None and next_start <= previous_next_start:
            msg = "Binance pagination did not advance"
            raise RuntimeError(msg)
        previous_next_start = next_start
        current_start = next_start
    return klines


def _load_existing_dataset(target_path: Path, symbol: str = CONFIG.symbol) -> CandleDataset | None:
    if not target_path.exists():
        return None
    return load_candle_dataset_from_csv(target_path, symbol=symbol, interval="1m")


def _download_range_to_dataset(
    start_time_ms: int,
    end_time_ms: int,
    target_path: Path,
    progress_callback: Callable[[dict], None] | None,
    mode: str,
    existing_dataset: CandleDataset | None = None,
    symbol: str = CONFIG.symbol,
    resume_from_existing_end: bool = True,
) -> CandleDataset:
    candles_by_open_time = _dataset_by_open_time(existing_dataset)
    current_start = start_time_ms
    if resume_from_existing_end and existing_dataset is not None and existing_dataset.candles:
        current_start = max(
            current_start, _open_time_to_ms(existing_dataset.candles[-1].open_time) + ONE_MINUTE_MS
        )
    expected_candles = max(1, ((end_time_ms - start_time_ms) // ONE_MINUTE_MS) + 1)
    previous_next_start: int | None = None
    empty_pages = 0
    pages_since_save = 0

    try:
        while current_start <= end_time_ms:
            page = _fetch_page_with_retries(current_start, end_time_ms, progress_callback, mode, symbol=symbol)
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
            for candle in [binance_kline_to_candle(kline) for kline in new_klines]:
                candles_by_open_time[candle.open_time] = candle
            dataset = _dataset_from_map(candles_by_open_time, symbol=symbol)
            pages_since_save += 1
            if pages_since_save >= SAVE_EVERY_PAGES:
                _save_dataset_and_catalog(dataset, target_path)
                pages_since_save = 0
            _emit_progress(
                progress_callback,
                len(dataset.candles),
                expected_candles,
                new_klines[-1],
                mode,
                symbol=symbol,
            )
            next_start = new_klines[-1].open_time_ms + ONE_MINUTE_MS
            if previous_next_start is not None and next_start <= previous_next_start:
                msg = "Binance pagination did not advance"
                raise RuntimeError(msg)
            previous_next_start = next_start
            current_start = next_start
    except Exception:
        if candles_by_open_time:
            _save_dataset_and_catalog(_dataset_from_map(candles_by_open_time, symbol=symbol), target_path)
        raise
    dataset = _dataset_from_map(candles_by_open_time, symbol=symbol)
    _save_dataset_and_catalog(dataset, target_path)
    return dataset


def download_ethusdc_1m_candles(
    start_time_ms: int,
    end_time_ms: int,
    output_path: Path | None = None,
    progress_callback: Callable[[dict], None] | None = None,
    symbol: str = CONFIG.symbol,
    replace_existing: bool = False,
) -> CandleDataset:
    """Download public ETHUSDC 1m klines, save CSV, and update the data catalog."""
    if start_time_ms <= 0:
        msg = "start_time_ms must be positive"
        raise ValueError(msg)
    if end_time_ms <= start_time_ms:
        msg = "end_time_ms must be greater than start_time_ms"
        raise ValueError(msg)

    target_path = output_path or _default_candle_path(symbol)
    existing_dataset = (
        None if replace_existing else _load_existing_dataset(target_path, symbol=symbol)
    )
    mode = (
        "resume_partial_download"
        if existing_dataset and existing_dataset.candles
        else "full_download"
    )
    dataset = _download_range_to_dataset(
        start_time_ms,
        end_time_ms,
        target_path,
        progress_callback,
        mode,
        existing_dataset,
        symbol,
        resume_from_existing_end=not replace_existing,
    )
    _save_dataset_and_catalog(dataset, target_path)
    return dataset


def update_ethusdc_1m_candles(
    output_path: Path | None = None,
    required_candles: int | None = None,
    safety_days: int = 2,
    progress_callback: Callable[[dict], None] | None = None,
    symbol: str = CONFIG.symbol,
) -> CandleDataset:
    """Incrementally update local public ETHUSDC 1m candle data."""
    target_path = output_path or _default_candle_path(symbol)
    now_ms = _utc_now_ms()
    needed_candles = required_candles or REQUIRED_CANDLE_COUNT
    safety_candles = safety_days * 24 * 60

    if not target_path.exists():
        start_time_ms = now_ms - (needed_candles + safety_candles) * ONE_MINUTE_MS
        return download_ethusdc_1m_candles(
            start_time_ms=start_time_ms,
            end_time_ms=now_ms,
            output_path=target_path,
            progress_callback=progress_callback,
            symbol=symbol,
        )

    existing_dataset = load_candle_dataset_from_csv(target_path, symbol=symbol, interval="1m")
    desired_start_time_ms = now_ms - (needed_candles + safety_candles) * ONE_MINUTE_MS
    if len(existing_dataset.candles) < needed_candles:
        first_open_time_ms = _open_time_to_ms(existing_dataset.candles[0].open_time)
        if first_open_time_ms > desired_start_time_ms:
            existing_dataset = _download_range_to_dataset(
                desired_start_time_ms,
                first_open_time_ms - ONE_MINUTE_MS,
                target_path,
                progress_callback,
                "historical_backfill",
                existing_dataset,
                symbol,
                resume_from_existing_end=False,
            )
    last_open_time_ms = _open_time_to_ms(existing_dataset.candles[-1].open_time)
    next_missing_time_ms = last_open_time_ms + ONE_MINUTE_MS
    if next_missing_time_ms > now_ms:
        _save_dataset_and_catalog(existing_dataset, target_path)
        return existing_dataset

    updated_dataset = _download_range_to_dataset(
        next_missing_time_ms,
        now_ms,
        target_path,
        progress_callback,
        "backfill_resume" if len(existing_dataset.candles) < needed_candles else "incremental_update",
        existing_dataset,
        symbol,
    )
    _save_dataset_and_catalog(updated_dataset, target_path)
    return updated_dataset
