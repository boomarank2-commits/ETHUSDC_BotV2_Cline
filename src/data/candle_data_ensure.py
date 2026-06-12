"""Ensure local ETHUSDC 1m candle data is ready before backtests."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from src.common.config import CONFIG
from src.data.binance_candle_downloader import (
    DEFAULT_BINANCE_CANDLE_PATH,
    ONE_MINUTE_MS,
    _open_time_to_ms,
    _utc_now_ms,
    download_ethusdc_1m_candles,
    update_ethusdc_1m_candles,
)
from src.data.candle_csv_io import load_candle_dataset_from_csv
from src.data.data_catalog import CandleDataCatalogEntry, get_catalog_path, save_data_catalog
from src.data.train_blind_split import REQUIRED_CANDLE_COUNT

DOWNLOAD_BUFFER_DAYS = 2
CURRENT_GRACE_MINUTES = 2
NETWORK_ERROR_MESSAGE = (
    "Binance konnte nicht erreicht werden. Internet/Firewall/Binance-Verbindung prüfen "
    "und später erneut versuchen."
)


@dataclass(frozen=True)
class CandleDataEnsureResult:
    """Result of checking/updating local ETHUSDC 1m candle data."""

    success: bool
    message: str
    symbol: str
    interval: str
    candle_count: int
    required_candles: int
    output_path: str | None
    catalog_path: str | None
    was_updated: bool
    full_download: bool
    incremental_update: bool
    already_current: bool
    last_open_time: str | None
    error: str | None


def _full_download_window_ms() -> tuple[int, int]:
    end_time_ms = _utc_now_ms()
    safety_candles = DOWNLOAD_BUFFER_DAYS * 24 * 60
    start_time_ms = end_time_ms - (REQUIRED_CANDLE_COUNT + safety_candles) * ONE_MINUTE_MS
    return start_time_ms, end_time_ms


def _save_default_catalog(target_path: Path) -> str:
    catalog_path = save_data_catalog(
        [CandleDataCatalogEntry(CONFIG.symbol, "1m", str(target_path))]
    )
    return str(catalog_path)


def _emit_progress(
    progress_callback: Callable[[dict], None] | None,
    mode: str,
    detail: str,
    progress_pct: float,
    **extra: object,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        {
            "phase": "data_ensure",
            "mode": mode,
            "detail": detail,
            "progress_pct": progress_pct,
            **extra,
        }
    )


def _is_network_error(message: str) -> bool:
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in (
            "binance request error",
            "winerror 10060",
            "timed out",
            "timeout",
            "connection",
            "verbindungsversuch",
        )
    )


def _is_current(last_open_time: str) -> bool:
    last_open_time_ms = _open_time_to_ms(last_open_time)
    return (_utc_now_ms() - last_open_time_ms) <= CURRENT_GRACE_MINUTES * ONE_MINUTE_MS


def _final_result(
    target_path: Path,
    message: str,
    was_updated: bool,
    full_download: bool,
    incremental_update: bool,
    already_current: bool,
) -> CandleDataEnsureResult:
    catalog_path = _save_default_catalog(target_path)
    dataset = load_candle_dataset_from_csv(target_path, symbol=CONFIG.symbol, interval="1m")
    candle_count = len(dataset.candles)
    last_open_time = dataset.candles[-1].open_time if dataset.candles else None
    success = candle_count >= REQUIRED_CANDLE_COUNT
    if not success:
        message = (
            f"Nicht genug ETHUSDC 1m Candles vorhanden: {candle_count} von "
            f"{REQUIRED_CANDLE_COUNT}. Backtest wurde nicht gestartet."
        )
    return CandleDataEnsureResult(
        success=success,
        message=message,
        symbol=CONFIG.symbol,
        interval="1m",
        candle_count=candle_count,
        required_candles=REQUIRED_CANDLE_COUNT,
        output_path=str(target_path),
        catalog_path=catalog_path,
        was_updated=was_updated,
        full_download=full_download,
        incremental_update=incremental_update,
        already_current=already_current and success,
        last_open_time=last_open_time,
        error=None if success else message,
    )


def _failure(
    error: Exception | str, candle_count: int = 0, target_path: Path | None = None
) -> CandleDataEnsureResult:
    error_message = str(error)
    message = (
        NETWORK_ERROR_MESSAGE
        if _is_network_error(error_message)
        else f"ETHUSDC 1m Daten konnten nicht vorbereitet werden: {error_message}"
    )
    return CandleDataEnsureResult(
        success=False,
        message=message,
        symbol=CONFIG.symbol,
        interval="1m",
        candle_count=candle_count,
        required_candles=REQUIRED_CANDLE_COUNT,
        output_path=str(target_path) if target_path is not None else None,
        catalog_path=str(get_catalog_path()),
        was_updated=False,
        full_download=False,
        incremental_update=False,
        already_current=False,
        last_open_time=None,
        error=error_message,
    )


def ensure_ethusdc_1m_data_ready(
    progress_callback: Callable[[dict], None] | None = None,
) -> CandleDataEnsureResult:
    """Check/update local ETHUSDC 1m data; never runs a backtest."""
    target_path = DEFAULT_BINANCE_CANDLE_PATH
    try:
        _emit_progress(progress_callback, "checking", "Prüfe lokale ETHUSDC 1m Daten", 0.0)
        if not target_path.exists():
            _emit_progress(
                progress_callback,
                "full_download",
                "Lokale CSV fehlt; vollständiger Download startet",
                1.0,
            )
            start_time_ms, end_time_ms = _full_download_window_ms()
            download_ethusdc_1m_candles(
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                output_path=target_path,
                progress_callback=progress_callback,
            )
            return _final_result(
                target_path,
                "ETHUSDC 1m Daten vollständig neu geladen.",
                was_updated=True,
                full_download=True,
                incremental_update=False,
                already_current=False,
            )

        existing_dataset = load_candle_dataset_from_csv(
            target_path, symbol=CONFIG.symbol, interval="1m"
        )
        existing_count = len(existing_dataset.candles)
        if existing_count < REQUIRED_CANDLE_COUNT:
            _emit_progress(
                progress_callback,
                "rebuild_incomplete_csv",
                "Unvollständige CSV erkannt; vollständiger Neuaufbau startet",
                1.0,
                candle_count=existing_count,
                required_candles=REQUIRED_CANDLE_COUNT,
            )
            start_time_ms, end_time_ms = _full_download_window_ms()
            download_ethusdc_1m_candles(
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                output_path=target_path,
                progress_callback=progress_callback,
            )
            return _final_result(
                target_path,
                "Unvollständige ETHUSDC 1m CSV erkannt und vollständig neu aufgebaut.",
                was_updated=True,
                full_download=True,
                incremental_update=False,
                already_current=False,
            )

        last_open_time = existing_dataset.candles[-1].open_time
        if _is_current(last_open_time):
            _emit_progress(
                progress_callback,
                "already_current",
                "Lokale ETHUSDC 1m Daten sind vollständig und aktuell",
                100.0,
                candle_count=existing_count,
                last_open_time=last_open_time,
            )
            return _final_result(
                target_path,
                "ETHUSDC 1m Daten sind bereits aktuell und vollständig.",
                was_updated=False,
                full_download=False,
                incremental_update=False,
                already_current=True,
            )

        _emit_progress(
            progress_callback,
            "incremental_update",
            "Lokale Daten sind vollständig, aber veraltet; Update startet",
            1.0,
            candle_count=existing_count,
            last_open_time=last_open_time,
        )
        update_ethusdc_1m_candles(
            output_path=target_path,
            required_candles=REQUIRED_CANDLE_COUNT,
            safety_days=DOWNLOAD_BUFFER_DAYS,
            progress_callback=progress_callback,
        )
        return _final_result(
            target_path,
            "ETHUSDC 1m Daten inkrementell aktualisiert.",
            was_updated=True,
            full_download=False,
            incremental_update=True,
            already_current=False,
        )
    except Exception as error:  # noqa: BLE001
        try:
            candle_count = (
                len(load_candle_dataset_from_csv(target_path).candles)
                if target_path.exists()
                else 0
            )
        except Exception:  # noqa: BLE001
            candle_count = 0
        result = _failure(error, candle_count=candle_count, target_path=target_path)
        _emit_progress(
            progress_callback,
            "failed",
            result.message,
            100.0,
            candle_count=candle_count,
            error=result.error,
        )
        return result


def utc_now_iso() -> str:
    """Return current UTC timestamp for diagnostics."""
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
