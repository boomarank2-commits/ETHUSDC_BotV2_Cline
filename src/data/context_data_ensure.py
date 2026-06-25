"""Ensure optional public context candle data is locally available."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.data.binance_candle_downloader import (
    DEFAULT_CONTEXT_CANDLE_PATHS,
    ONE_MINUTE_MS,
    _open_time_to_ms,
    _utc_now_ms,
    download_ethusdc_1m_candles,
    update_ethusdc_1m_candles,
)
from src.data.candle_csv_io import (
    candle_csv_has_order_flow_fields,
    load_candle_dataset_from_csv,
)
from src.data.candle_quality import build_candle_quality_report
from src.data.data_catalog import CandleDataCatalogEntry, upsert_data_catalog_entry
from src.data.train_blind_split import REQUIRED_CANDLE_COUNT

CONTEXT_SYMBOLS = ("BTCUSDC", "ETHBTC", "ETHUSDT", "USDCUSDT")
CONTEXT_MAX_AGE_DAYS = 7
DOWNLOAD_BUFFER_DAYS = 2


@dataclass(frozen=True)
class ContextDataEnsureResult:
    symbol: str
    success: bool
    message: str
    candle_count: int
    last_open_time: str | None
    was_updated: bool
    already_current: bool
    output_path: str
    error: str | None


def _is_current(last_open_time: str) -> bool:
    return (_utc_now_ms() - _open_time_to_ms(last_open_time)) <= CONTEXT_MAX_AGE_DAYS * 24 * 60 * ONE_MINUTE_MS


def _emit(progress_callback: Callable[[dict], None] | None, payload: dict) -> None:
    if progress_callback is not None:
        progress_callback(payload)


def _validate_context_dataset(symbol: str, target_path: Path) -> tuple[bool, str, int, str | None]:
    dataset = load_candle_dataset_from_csv(target_path, symbol=symbol, interval="1m")
    quality = build_candle_quality_report(dataset)
    last_open_time = quality.last_open_time if dataset.candles else None
    if quality.candle_count < REQUIRED_CANDLE_COUNT:
        return False, f"{symbol} not_enough_data: {quality.candle_count}/{REQUIRED_CANDLE_COUNT} candles", quality.candle_count, last_open_time
    if quality.detected_gaps != 0:
        return False, f"{symbol} has {quality.detected_gaps} detected 1m gaps", quality.candle_count, last_open_time
    if last_open_time is None or not _is_current(last_open_time):
        return False, f"{symbol} context data outdated: last_open_time={last_open_time}", quality.candle_count, last_open_time
    return True, f"{symbol} 1m context data current and complete", quality.candle_count, last_open_time


def _upsert_context_catalog(symbol: str, target_path: Path) -> None:
    upsert_data_catalog_entry(CandleDataCatalogEntry(symbol, "1m", str(target_path)))


def ensure_context_1m_data_ready(
    symbol: str,
    progress_callback: Callable[[dict], None] | None = None,
) -> ContextDataEnsureResult:
    """Ensure one optional context symbol has enough 1m candles."""
    if symbol not in CONTEXT_SYMBOLS:
        msg = f"unsupported context symbol: {symbol}"
        raise ValueError(msg)
    target_path = DEFAULT_CONTEXT_CANDLE_PATHS[symbol]
    try:
        _emit(progress_callback, {"phase": "context_data_check", "symbol": symbol, "mode": "checking"})
        if target_path.exists():
            if not candle_csv_has_order_flow_fields(target_path):
                start_time_ms = (
                    _utc_now_ms()
                    - (REQUIRED_CANDLE_COUNT + DOWNLOAD_BUFFER_DAYS * 24 * 60)
                    * ONE_MINUTE_MS
                )
                download_ethusdc_1m_candles(
                    start_time_ms=start_time_ms,
                    end_time_ms=_utc_now_ms(),
                    output_path=target_path,
                    progress_callback=progress_callback,
                    symbol=symbol,
                    replace_existing=True,
                )
                success, message, candle_count, last_open_time = _validate_context_dataset(
                    symbol,
                    target_path,
                )
                if success:
                    _upsert_context_catalog(symbol, target_path)
                return ContextDataEnsureResult(
                    symbol,
                    success,
                    f"{symbol} refreshed with complete Binance kline order-flow fields",
                    candle_count,
                    last_open_time,
                    True,
                    False,
                    str(target_path),
                    None if success else message,
                )

            success, message, candle_count, last_open_time = _validate_context_dataset(symbol, target_path)
            if success:
                _upsert_context_catalog(symbol, target_path)
                _emit(
                    progress_callback,
                    {
                        "phase": "context_data_check",
                        "symbol": symbol,
                        "mode": "already_current",
                        "candle_count": candle_count,
                        "last_open_time": last_open_time,
                    },
                )
                return ContextDataEnsureResult(
                    symbol, True, message, candle_count, last_open_time, False, True, str(target_path), None
                )
        update_ethusdc_1m_candles(
            output_path=target_path,
            required_candles=REQUIRED_CANDLE_COUNT,
            safety_days=DOWNLOAD_BUFFER_DAYS,
            progress_callback=progress_callback,
            symbol=symbol,
        )
        success, message, candle_count, last_open_time = _validate_context_dataset(symbol, target_path)
        if success:
            _upsert_context_catalog(symbol, target_path)
        return ContextDataEnsureResult(
            symbol,
            success,
            message,
            candle_count,
            last_open_time,
            True,
            False,
            str(target_path),
            None if success else message,
        )
    except Exception as error:  # noqa: BLE001
        count = 0
        last_open_time = None
        if Path(target_path).exists():
            try:
                dataset = load_candle_dataset_from_csv(target_path, symbol=symbol, interval="1m")
                count = len(dataset.candles)
                last_open_time = dataset.candles[-1].open_time if dataset.candles else None
            except Exception:  # noqa: BLE001
                pass
        return ContextDataEnsureResult(symbol, False, str(error), count, last_open_time, False, False, str(target_path), str(error))


def ensure_all_context_data_ready(progress_callback: Callable[[dict], None] | None = None) -> list[ContextDataEnsureResult]:
    """Ensure all currently wired optional context candle datasets."""
    return [ensure_context_1m_data_ready(symbol, progress_callback=progress_callback) for symbol in CONTEXT_SYMBOLS]
