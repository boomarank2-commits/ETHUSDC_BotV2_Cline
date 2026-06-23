"""Public Binance Spot exchange-info cache for ETHUSDC."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from src.common.config import CONFIG
from src.common.paths import DATA_DIR

EXCHANGE_INFO_PATH = DATA_DIR / "exchange_info" / "ETHUSDC_exchange_info.json"
EXCHANGE_INFO_MAX_AGE_DAYS = 7
BINANCE_BASE_URL = "https://api.binance.com"
REQUEST_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class ExchangeInfoStatus:
    """Status of the local public exchange-info cache."""

    symbol: str
    path: str
    exists: bool
    was_updated: bool
    data_age_hours: float | None
    row_count: int
    usable_for_backtest: bool
    used_in_backtest: bool
    reason: str | None


@dataclass(frozen=True)
class ExchangeInfoFilters:
    min_notional: float | None
    lot_step_size: float | None
    lot_min_qty: float | None
    price_tick_size: float | None


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _file_age_hours() -> float | None:
    if not EXCHANGE_INFO_PATH.exists():
        return None
    modified = datetime.fromtimestamp(EXCHANGE_INFO_PATH.stat().st_mtime, tz=UTC)
    return round((_utc_now() - modified).total_seconds() / 3600, 4)


def _is_stale() -> bool:
    if not EXCHANGE_INFO_PATH.exists():
        return True
    modified = datetime.fromtimestamp(EXCHANGE_INFO_PATH.stat().st_mtime, tz=UTC)
    return _utc_now() - modified > timedelta(days=EXCHANGE_INFO_MAX_AGE_DAYS)


def _validate_payload(payload: dict[str, Any]) -> None:
    symbols = payload.get("symbols")
    if not isinstance(symbols, list) or len(symbols) != 1:
        msg = "exchange_info must contain exactly one symbol"
        raise ValueError(msg)
    symbol_payload = symbols[0]
    if symbol_payload.get("symbol") != CONFIG.symbol:
        msg = f"exchange_info symbol must be {CONFIG.symbol}"
        raise ValueError(msg)
    if not isinstance(symbol_payload.get("filters"), list) or not symbol_payload["filters"]:
        msg = "exchange_info filters must not be empty"
        raise ValueError(msg)


def fetch_exchange_info() -> dict[str, Any]:
    """Fetch public Binance Spot exchangeInfo for ETHUSDC without API keys."""
    query = urlencode({"symbol": CONFIG.symbol})
    url = f"{BINANCE_BASE_URL}/api/v3/exchangeInfo?{query}"
    try:
        with urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        msg = f"Binance exchangeInfo HTTP error: {error.code}"
        raise RuntimeError(msg) from error
    except (URLError, OSError, TimeoutError) as error:
        reason = error.reason if hasattr(error, "reason") else error
        msg = f"Binance exchangeInfo request error: {reason}"
        raise RuntimeError(msg) from error
    _validate_payload(payload)
    return payload


def ensure_exchange_info_current() -> ExchangeInfoStatus:
    """Ensure local exchange-info cache exists and is at most 7 days old."""
    was_updated = False
    reason = None
    try:
        if _is_stale():
            payload = fetch_exchange_info()
            EXCHANGE_INFO_PATH.parent.mkdir(parents=True, exist_ok=True)
            EXCHANGE_INFO_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            was_updated = True
        else:
            payload = json.loads(EXCHANGE_INFO_PATH.read_text(encoding="utf-8"))
            _validate_payload(payload)
    except Exception as error:  # noqa: BLE001
        reason = str(error)
    exists = EXCHANGE_INFO_PATH.exists()
    row_count = 0
    usable = False
    if exists and reason is None:
        payload = json.loads(EXCHANGE_INFO_PATH.read_text(encoding="utf-8"))
        row_count = len(payload.get("symbols", []))
        usable = row_count == 1
    return ExchangeInfoStatus(
        symbol=CONFIG.symbol,
        path=str(EXCHANGE_INFO_PATH),
        exists=exists,
        was_updated=was_updated,
        data_age_hours=_file_age_hours(),
        row_count=row_count,
        usable_for_backtest=usable,
        used_in_backtest=usable,
        reason=reason,
    )


def load_exchange_info_filters() -> ExchangeInfoFilters | None:
    """Load minimal Binance Spot filters used by the backtest simulation."""
    status = ensure_exchange_info_current()
    if not status.usable_for_backtest:
        return None
    payload = json.loads(EXCHANGE_INFO_PATH.read_text(encoding="utf-8"))
    symbol_payload = payload["symbols"][0]
    filters = {item.get("filterType"): item for item in symbol_payload.get("filters", [])}
    notional = filters.get("MIN_NOTIONAL") or filters.get("NOTIONAL") or {}
    lot_size = filters.get("LOT_SIZE") or {}
    price_filter = filters.get("PRICE_FILTER") or {}
    return ExchangeInfoFilters(
        min_notional=float(notional["minNotional"]) if notional.get("minNotional") else None,
        lot_step_size=float(lot_size["stepSize"]) if lot_size.get("stepSize") else None,
        lot_min_qty=float(lot_size["minQty"]) if lot_size.get("minQty") else None,
        price_tick_size=float(price_filter["tickSize"]) if price_filter.get("tickSize") else None,
    )


def round_quantity_to_step(quantity: float, step_size: float | None) -> float:
    if step_size is None or step_size <= 0:
        return quantity
    return math.floor(quantity / step_size) * step_size


def round_price_to_tick(price: float, tick_size: float | None) -> float:
    if tick_size is None or tick_size <= 0:
        return price
    return math.floor(price / tick_size) * tick_size


def exchange_info_status_as_dict(status: ExchangeInfoStatus) -> dict[str, object]:
    """Return a JSON-friendly exchange-info status."""
    return asdict(status)