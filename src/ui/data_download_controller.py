"""UI controller for checking/updating public ETHUSDC 1m candle data."""

from dataclasses import dataclass
from typing import Callable

from src.common.config import CONFIG
from src.data.candle_data_ensure import ensure_ethusdc_1m_data_ready


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


def download_required_ethusdc_1m_data_for_ui(
    progress_callback: Callable[[dict], None] | None = None,
) -> DataDownloadUiResult:
    """Ensure enough public ETHUSDC 1m candles for the required lookback."""
    try:
        ensure_result = ensure_ethusdc_1m_data_ready(progress_callback=progress_callback)
        if not ensure_result.success:
            message = ensure_result.message
        elif ensure_result.full_download:
            message = "Daten vollständig neu geladen. Danach kann der Backtest gestartet werden."
        elif ensure_result.incremental_update:
            message = "Daten inkrementell aktualisiert. Danach kann der Backtest gestartet werden."
        elif ensure_result.already_current:
            message = "Daten waren bereits aktuell. Danach kann der Backtest gestartet werden."
        else:
            message = ensure_result.message
        return DataDownloadUiResult(
            success=ensure_result.success,
            message=message,
            symbol=CONFIG.symbol,
            interval="1m",
            candle_count=ensure_result.candle_count,
            output_path=ensure_result.output_path,
            catalog_updated=ensure_result.catalog_path is not None,
            error=ensure_result.error,
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
