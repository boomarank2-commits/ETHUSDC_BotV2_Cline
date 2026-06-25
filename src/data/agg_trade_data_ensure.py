"""Ensure compact historical ETHUSDC aggregate-trade features are available."""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from io import TextIOWrapper
from pathlib import Path
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from zipfile import ZipFile

from src.common.paths import DATA_DIR
from src.data.train_blind_split import REQUIRED_CANDLE_COUNT

AGG_TRADE_FEATURE_DIR = DATA_DIR / "market_features" / "agg_trades" / "ETHUSDC"
AGG_TRADE_STATUS_PATH = AGG_TRADE_FEATURE_DIR / "status.json"
BINANCE_DATA_BASE_URL = "https://data.binance.vision/data/spot"
REQUEST_TIMEOUT_SECONDS = 60
DOWNLOAD_BUFFER_DAYS = 2
ARCHIVE_PUBLICATION_LAG_DAYS = 2
FEATURE_FIELDS = [
    "open_time",
    "agg_trade_count",
    "raw_trade_count",
    "base_volume",
    "quote_volume",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "taker_sell_base_volume",
    "taker_sell_quote_volume",
    "vwap",
    "max_agg_trade_quote",
]

ProgressCallback = Callable[[dict], None]


@dataclass(frozen=True)
class AggTradeDataEnsureResult:
    """Readiness of compact ETHUSDC aggregate-trade minute features."""

    success: bool
    message: str
    partition_count: int
    first_partition: str | None
    last_partition: str | None
    latest_complete_date: str | None
    output_path: str
    was_updated: bool
    error: str | None


@dataclass
class _MinuteAggregate:
    agg_trade_count: int = 0
    raw_trade_count: int = 0
    base_volume: float = 0.0
    quote_volume: float = 0.0
    taker_buy_base_volume: float = 0.0
    taker_buy_quote_volume: float = 0.0
    taker_sell_base_volume: float = 0.0
    taker_sell_quote_volume: float = 0.0
    max_agg_trade_quote: float = 0.0


def _emit(
    progress_callback: ProgressCallback | None,
    detail: str,
    progress_pct: float | None = None,
    **extra: object,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        {
            "phase": "agg_trade_data_ensure",
            "data_kind": "ethusdc_agg_trades",
            "detail": detail,
            "message": detail,
            "progress_pct": progress_pct,
            **extra,
        }
    )


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _previous_month(value: date) -> date:
    return (value.replace(day=1) - timedelta(days=1)).replace(day=1)


def _next_month(value: date) -> date:
    return (value.replace(day=28) + timedelta(days=4)).replace(day=1)


def _month_keys(start: date, end: date) -> list[str]:
    keys: list[str] = []
    current = _month_start(start)
    final = _month_start(end)
    while current <= final:
        keys.append(current.strftime("%Y-%m"))
        current = _next_month(current)
    return keys


def _daily_keys(start: date, end: date) -> list[str]:
    if start > end:
        return []
    result: list[str] = []
    current = start
    while current <= end:
        result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def _required_start_date(today: date) -> date:
    required_days = (REQUIRED_CANDLE_COUNT // (24 * 60)) + DOWNLOAD_BUFFER_DAYS
    return today - timedelta(days=required_days)


def _required_partition_keys(current_date: date) -> tuple[list[str], date]:
    required_start = _required_start_date(current_date)
    previous_month = _previous_month(current_date)
    last_monthly_archive = _previous_month(previous_month)
    required_months = _month_keys(required_start, last_monthly_archive)
    first_daily_date = max(required_start, previous_month)
    latest_complete_date = current_date - timedelta(days=ARCHIVE_PUBLICATION_LAG_DAYS)
    required_days = _daily_keys(first_daily_date, latest_complete_date)
    return required_months + required_days, latest_complete_date


def _partition_path(period: str) -> Path:
    return AGG_TRADE_FEATURE_DIR / f"{period}.csv"


def _archive_url(period: str) -> str:
    if len(period) == 7:
        return (
            f"{BINANCE_DATA_BASE_URL}/monthly/aggTrades/ETHUSDC/"
            f"ETHUSDC-aggTrades-{period}.zip"
        )
    return (
        f"{BINANCE_DATA_BASE_URL}/daily/aggTrades/ETHUSDC/"
        f"ETHUSDC-aggTrades-{period}.zip"
    )


def _timestamp_to_datetime(raw_timestamp: str) -> datetime:
    timestamp = int(raw_timestamp)
    divisor = 1_000_000 if timestamp >= 100_000_000_000_000 else 1_000
    return datetime.fromtimestamp(timestamp / divisor, tz=UTC)


def _looks_like_header(row: list[str]) -> bool:
    if not row:
        return True
    try:
        int(row[0])
    except ValueError:
        return True
    return False


def _aggregate_rows(rows: Iterable[list[str]]) -> dict[str, _MinuteAggregate]:
    minutes: dict[str, _MinuteAggregate] = {}
    for row in rows:
        if len(row) < 8 or _looks_like_header(row):
            continue
        price = float(row[1])
        quantity = float(row[2])
        first_trade_id = int(row[3])
        last_trade_id = int(row[4])
        timestamp = _timestamp_to_datetime(row[5])
        is_buyer_maker = row[6].strip().lower() == "true"
        minute = timestamp.replace(second=0, microsecond=0).strftime(
            "%Y-%m-%dT%H:%M:00Z"
        )
        quote_value = price * quantity
        aggregate = minutes.setdefault(minute, _MinuteAggregate())
        aggregate.agg_trade_count += 1
        aggregate.raw_trade_count += max(1, last_trade_id - first_trade_id + 1)
        aggregate.base_volume += quantity
        aggregate.quote_volume += quote_value
        aggregate.max_agg_trade_quote = max(
            aggregate.max_agg_trade_quote,
            quote_value,
        )
        if is_buyer_maker:
            aggregate.taker_sell_base_volume += quantity
            aggregate.taker_sell_quote_volume += quote_value
        else:
            aggregate.taker_buy_base_volume += quantity
            aggregate.taker_buy_quote_volume += quote_value
    return minutes


def _save_partition(path: Path, minutes: dict[str, _MinuteAggregate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".csv.tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FEATURE_FIELDS)
        writer.writeheader()
        for open_time in sorted(minutes):
            aggregate = minutes[open_time]
            writer.writerow(
                {
                    "open_time": open_time,
                    **asdict(aggregate),
                    "vwap": (
                        aggregate.quote_volume / aggregate.base_volume
                        if aggregate.base_volume > 0
                        else 0.0
                    ),
                }
            )
    temp_path.replace(path)


def _download_archive(
    period: str,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    url = _archive_url(period)
    AGG_TRADE_FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = AGG_TRADE_FEATURE_DIR / f"{period}.zip.tmp"
    _emit(progress_callback, f"ETHUSDC aggTrades {period} werden geladen", period=period)
    try:
        with urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310
            with zip_path.open("wb") as output:
                shutil.copyfileobj(response, output)
    except HTTPError as error:
        if zip_path.exists():
            zip_path.unlink()
        msg = f"Binance aggTrades archive HTTP error {error.code}: {period}"
        raise RuntimeError(msg) from error
    except (URLError, OSError, TimeoutError) as error:
        if zip_path.exists():
            zip_path.unlink()
        msg = f"Binance aggTrades archive request error: {period}: {error}"
        raise RuntimeError(msg) from error
    return zip_path


def _download_and_aggregate_archive(
    period: str,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    target_path = _partition_path(period)
    zip_path = _download_archive(period, progress_callback)
    try:
        with ZipFile(zip_path) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            if len(names) != 1:
                msg = f"unexpected Binance aggTrades archive contents: {period}"
                raise RuntimeError(msg)
            with archive.open(names[0]) as raw_file:
                reader = csv.reader(TextIOWrapper(raw_file, encoding="utf-8"))
                minutes = _aggregate_rows(reader)
        if not minutes:
            msg = f"Binance aggTrades archive contains no usable rows: {period}"
            raise RuntimeError(msg)
        _save_partition(target_path, minutes)
        return target_path
    finally:
        if zip_path.exists():
            zip_path.unlink()


def _existing_partitions() -> list[str]:
    if not AGG_TRADE_FEATURE_DIR.exists():
        return []
    return sorted(
        path.stem
        for path in AGG_TRADE_FEATURE_DIR.glob("*.csv")
        if len(path.stem) in {7, 10}
    )


def _save_status(result: AggTradeDataEnsureResult) -> None:
    AGG_TRADE_FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    AGG_TRADE_STATUS_PATH.write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_agg_trade_data_status() -> AggTradeDataEnsureResult | None:
    """Load the latest aggregate-trade readiness status."""
    if not AGG_TRADE_STATUS_PATH.exists():
        return None
    return AggTradeDataEnsureResult(
        **json.loads(AGG_TRADE_STATUS_PATH.read_text(encoding="utf-8"))
    )


def ensure_ethusdc_agg_trade_features_ready(
    progress_callback: ProgressCallback | None = None,
    today: date | None = None,
) -> AggTradeDataEnsureResult:
    """Download missing official Binance archives and store compact 1m features."""
    current_date = today or datetime.now(tz=UTC).date()
    required_partitions, latest_complete_date = _required_partition_keys(current_date)
    was_updated = False
    try:
        for index, period in enumerate(required_partitions, start=1):
            if _partition_path(period).exists():
                continue
            _download_and_aggregate_archive(period, progress_callback)
            was_updated = True
            _emit(
                progress_callback,
                f"ETHUSDC aggTrades {period} vorbereitet",
                index / max(1, len(required_partitions)) * 100,
                period=period,
            )
        existing = _existing_partitions()
        missing = [
            period for period in required_partitions if not _partition_path(period).exists()
        ]
        success = not missing
        message = (
            "ETHUSDC aggTrades minute features are complete"
            if success
            else f"missing ETHUSDC aggTrades partitions: {', '.join(missing[:5])}"
        )
        result = AggTradeDataEnsureResult(
            success=success,
            message=message,
            partition_count=len(existing),
            first_partition=existing[0] if existing else None,
            last_partition=existing[-1] if existing else None,
            latest_complete_date=latest_complete_date.isoformat(),
            output_path=str(AGG_TRADE_FEATURE_DIR),
            was_updated=was_updated,
            error=None if success else message,
        )
    except Exception as error:  # noqa: BLE001
        existing = _existing_partitions()
        result = AggTradeDataEnsureResult(
            success=False,
            message=str(error),
            partition_count=len(existing),
            first_partition=existing[0] if existing else None,
            last_partition=existing[-1] if existing else None,
            latest_complete_date=None,
            output_path=str(AGG_TRADE_FEATURE_DIR),
            was_updated=was_updated,
            error=str(error),
        )
    _save_status(result)
    return result
