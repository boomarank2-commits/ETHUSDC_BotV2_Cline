"""One shared UI data-readiness workflow for smoke and full backtests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.data.agg_trade_data_ensure import (
    AggTradeDataEnsureResult,
    ensure_ethusdc_agg_trade_features_ready,
)
from src.data.candle_data_ensure import (
    CandleDataEnsureResult,
    ensure_ethusdc_1m_data_ready,
)
from src.data.context_data_ensure import (
    ContextDataEnsureResult,
    ensure_all_context_data_ready,
)
from src.data.exchange_info import ExchangeInfoStatus, ensure_exchange_info_current
from src.data.live_microstructure import (
    LiveMicrostructureStatus,
    ensure_live_microstructure_collection_started,
)

ProgressCallback = Callable[[dict], None]


@dataclass(frozen=True)
class BacktestMarketDataEnsureResult:
    """Readiness result for every source required at the UI start boundary."""

    success: bool
    message: str
    primary_candles: CandleDataEnsureResult
    context_candles: list[ContextDataEnsureResult]
    exchange_info: ExchangeInfoStatus
    agg_trades: AggTradeDataEnsureResult
    live_microstructure: LiveMicrostructureStatus
    blocking_errors: list[str]


def _emit(
    progress_callback: ProgressCallback | None,
    detail: str,
    progress_pct: float,
) -> None:
    if progress_callback is not None:
        progress_callback(
            {
                "phase": "backtest_market_data_ensure",
                "detail": detail,
                "message": detail,
                "progress_pct": progress_pct,
            }
        )


def ensure_all_backtest_market_data_ready(
    progress_callback: ProgressCallback | None = None,
) -> BacktestMarketDataEnsureResult:
    """Ensure the same validated market-data set before every smoke/full run."""
    _emit(progress_callback, "ETHUSDC Haupt-Candles werden geprüft", 0.0)
    primary = ensure_ethusdc_1m_data_ready(progress_callback=progress_callback)

    _emit(progress_callback, "ETH-Kontextmärkte werden geprüft", 20.0)
    contexts = ensure_all_context_data_ready(progress_callback=progress_callback)

    _emit(progress_callback, "Binance Spot Handelsregeln werden geprüft", 45.0)
    exchange = ensure_exchange_info_current()

    _emit(progress_callback, "Historische ETHUSDC aggTrades werden geprüft", 55.0)
    agg_trades = ensure_ethusdc_agg_trade_features_ready(
        progress_callback=progress_callback
    )

    _emit(progress_callback, "Live Spread-/Orderbuchsammlung wird geprüft", 90.0)
    live_microstructure = ensure_live_microstructure_collection_started()

    blocking_errors: list[str] = []
    if not primary.success:
        blocking_errors.append(primary.message)
    blocking_errors.extend(
        f"{result.symbol}: {result.message}"
        for result in contexts
        if not result.success
    )
    if not exchange.usable_for_backtest:
        blocking_errors.append(
            f"exchange_info: {exchange.reason or 'not usable'}"
        )
    if not agg_trades.success:
        blocking_errors.append(f"aggTrades: {agg_trades.message}")
    if not live_microstructure.success:
        blocking_errors.append(
            f"live microstructure: {live_microstructure.message}"
        )

    success = not blocking_errors
    message = (
        "Alle aktuell erforderlichen ETHUSDC Backtest-Daten sind vorhanden und aktuell"
        if success
        else "Backtest-Daten unvollständig: " + "; ".join(blocking_errors)
    )
    _emit(progress_callback, message, 100.0)
    return BacktestMarketDataEnsureResult(
        success=success,
        message=message,
        primary_candles=primary,
        context_candles=contexts,
        exchange_info=exchange,
        agg_trades=agg_trades,
        live_microstructure=live_microstructure,
        blocking_errors=blocking_errors,
    )
