"""UI controller for downloading public ETHUSDC 1m candle data."""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from src.common.config import CONFIG
from src.data.binance_candle_downloader import (
    DEFAULT_BINANCE_CANDLE_PATH,
    update_ethusdc_1m_candles,
)
from src.data.train_blind_split import REQUIRED_CANDLE_COUNT

DOWNLOAD_BUFFER_DAYS = 2
MILLISECONDS_PER_MINUTE = 60_000


@dataclass(frozen=True)
class DataDownloadUiResult:
    """UI-friendly result for local candle data download/update."""

    success: bool
    message: str
    symbol: str
    interval: str
    candle_count: int | None
    output_path: str | None
    catalog_updated: bool
    error: str | None


def _calculate_download_window_ms(now: datetime) -> tuple[int, int]:
    required_minutes = REQUIRED_CANDLE_COUNT + DOWNLOAD_BUFFER_DAYS * 24 * 60
    end_time_ms = int(now.timestamp() * 1000)
    start_time_ms = end_time_ms - required_minutes * MILLISECONDS_PER_MINUTE
    return start_time_ms, end_time_ms


def download_required_ethusdc_1m_data_for_ui(
    progress_callback: Callable[[dict], None] | None = None,
) -> DataDownloadUiResult:
    """Download enough public ETHUSDC 1m candles for the required lookback."""
    try:
        modes: list[str] = []

        def capture_progress(progress: dict) -> None:
            mode = progress.get("mode")
            if isinstance(mode, str):
                modes.append(mode)
            if progress_callback is not None:
                progress_callback(progress)

        dataset = update_ethusdc_1m_candles(
            output_path=DEFAULT_BINANCE_CANDLE_PATH,
            required_candles=REQUIRED_CANDLE_COUNT,
            safety_days=DOWNLOAD_BUFFER_DAYS,
            progress_callback=capture_progress,
        )
        if "full_download" in modes:
            message = "Daten vollständig neu geladen. Danach kann der Backtest gestartet werden."
        elif "incremental_update" in modes:
            message = "Daten aktualisiert. Danach kann der Backtest gestartet werden."
        else:
            message = "Daten waren bereits aktuell. Danach kann der Backtest gestartet werden."
        return DataDownloadUiResult(
            success=True,
            message=message,
            symbol=CONFIG.symbol,
            interval="1m",
            candle_count=len(dataset.candles),
            output_path=str(DEFAULT_BINANCE_CANDLE_PATH),
            catalog_updated=True,
            error=None,
        )
    except Exception as error:  # noqa: BLE001
        return DataDownloadUiResult(
            success=False,
            message=f"Daten konnten nicht geladen werden: {error}",
            symbol=CONFIG.symbol,
            interval="1m",
            candle_count=None,
            output_path=None,
            catalog_updated=False,
            error=str(error),
        )
