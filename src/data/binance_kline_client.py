"""Public Binance Spot kline client for ETHUSDC 1m market data only."""

import json
import socket
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from src.common.config import CONFIG

DEFAULT_BINANCE_TIMEOUT_SECONDS = 30


class BinanceRequestError(RuntimeError):
    """Public Binance market-data request failed."""


@dataclass(frozen=True)
class BinanceKline:
    """Minimal parsed Binance kline fields required for Candle conversion."""

    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


def _validate_kline_request(symbol: str, interval: str, start_time_ms: int, limit: int) -> None:
    if symbol != CONFIG.symbol:
        msg = f"symbol must be {CONFIG.symbol}"
        raise ValueError(msg)
    if interval != "1m":
        msg = 'interval must be "1m"'
        raise ValueError(msg)
    if start_time_ms <= 0:
        msg = "start_time_ms must be positive"
        raise ValueError(msg)
    if not 1 <= limit <= 1000:
        msg = "limit must be between 1 and 1000"
        raise ValueError(msg)


def _parse_binance_kline(raw_kline: list[Any]) -> BinanceKline:
    return BinanceKline(
        open_time_ms=int(raw_kline[0]),
        open=float(raw_kline[1]),
        high=float(raw_kline[2]),
        low=float(raw_kline[3]),
        close=float(raw_kline[4]),
        volume=float(raw_kline[5]),
    )


def fetch_binance_klines(
    symbol: str,
    interval: str,
    start_time_ms: int,
    end_time_ms: int | None = None,
    limit: int = 1000,
    base_url: str = "https://api.binance.com",
    timeout: int = DEFAULT_BINANCE_TIMEOUT_SECONDS,
) -> list[BinanceKline]:
    """Fetch public Binance Spot klines without API keys or trading actions."""
    _validate_kline_request(symbol, interval, start_time_ms, limit)
    query = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time_ms,
        "limit": limit,
    }
    if end_time_ms is not None:
        query["endTime"] = end_time_ms
    url = f"{base_url.rstrip('/')}/api/v3/klines?{urlencode(query)}"
    try:
        with urlopen(url, timeout=timeout) as response:  # noqa: S310
            raw_payload = response.read().decode("utf-8")
    except HTTPError as error:
        msg = f"Binance HTTP error: {error.code}"
        raise BinanceRequestError(msg) from error
    except (URLError, OSError, TimeoutError, socket.timeout) as error:
        reason = error.reason if hasattr(error, "reason") else error
        msg = f"Binance request error: {reason}"
        raise BinanceRequestError(msg) from error

    raw_klines = json.loads(raw_payload)
    return [_parse_binance_kline(raw_kline) for raw_kline in raw_klines]
