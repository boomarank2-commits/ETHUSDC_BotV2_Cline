"""Central data overview for backtest-visible data areas."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.data.agg_trade_data_ensure import load_agg_trade_data_status
from src.data.candle_csv_io import candle_csv_has_order_flow_fields
from src.data.candle_quality import EXPECTED_MIN_CANDLES
from src.data.data_catalog import load_data_catalog
from src.data.data_inventory import BACKTEST_DATA_INVENTORY
from src.data.exchange_info import ensure_exchange_info_current
from src.data.live_microstructure import load_live_microstructure_status
from src.data.local_candle_loader import build_local_candle_quality_from_catalog

DATA_OVERVIEW_REPORT_FILENAME = "data_overview_report.json"


@dataclass(frozen=True)
class DataAreaStatus:
    """UI/report status for one data area."""

    data_kind: str
    label: str
    status: str
    path: str | None
    first_timestamp: str | None
    last_timestamp: str | None
    data_age_hours: float | None
    row_count: int | None
    expected_min_rows: int | None
    detected_gaps: int | None
    usable_for_backtest: bool
    used_in_backtest: bool
    usage_reason: str


@dataclass(frozen=True)
class DataOverviewReport:
    """All data areas known to the current V2 backtest start workflow."""

    run_id: str
    generated_at: str
    areas: list[DataAreaStatus]

    def __post_init__(self) -> None:
        get_run_report_dir(self.run_id)


def _age_hours(timestamp: str | None) -> float | None:
    if not timestamp:
        return None
    normalized = timestamp.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized).astimezone(UTC)
    return round((datetime.now(tz=UTC) - parsed).total_seconds() / 3600, 4)


def _status_from_age(usable: bool, age_hours: float | None) -> str:
    if not usable:
        return "not_enough_data"
    if age_hours is not None and age_hours > 7 * 24:
        return "outdated"
    return "current"


def _ethusdc_candle_status() -> DataAreaStatus:
    quality = build_local_candle_quality_from_catalog("ETHUSDC", "1m")
    age_hours = _age_hours(quality.last_open_time)
    usable = quality.has_required_lookback and quality.detected_gaps == 0
    return DataAreaStatus(
        data_kind="ethusdc_klines_1m",
        label="ETHUSDC 1m Candles",
        status=_status_from_age(usable, age_hours),
        path=None,
        first_timestamp=quality.first_open_time,
        last_timestamp=quality.last_open_time,
        data_age_hours=age_hours,
        row_count=quality.candle_count,
        expected_min_rows=EXPECTED_MIN_CANDLES,
        detected_gaps=quality.detected_gaps,
        usable_for_backtest=usable,
        used_in_backtest=True,
        usage_reason="primary training/blindtest candle source",
    )


def _context_candle_status(symbol: str, label: str) -> DataAreaStatus:
    try:
        quality = build_local_candle_quality_from_catalog(symbol, "1m")
    except Exception as error:  # noqa: BLE001
        return DataAreaStatus(
            data_kind=f"{symbol.lower()}_klines_1m",
            label=label,
            status="not_available",
            path=None,
            first_timestamp=None,
            last_timestamp=None,
            data_age_hours=None,
            row_count=None,
            expected_min_rows=EXPECTED_MIN_CANDLES,
            detected_gaps=None,
            usable_for_backtest=False,
            used_in_backtest=False,
            usage_reason=f"context unavailable: {error}",
        )
    age_hours = _age_hours(quality.last_open_time)
    usable = quality.has_required_lookback and quality.detected_gaps == 0
    return DataAreaStatus(
        data_kind=f"{symbol.lower()}_klines_1m",
        label=label,
        status=_status_from_age(usable, age_hours),
        path=None,
        first_timestamp=quality.first_open_time,
        last_timestamp=quality.last_open_time,
        data_age_hours=age_hours,
        row_count=quality.candle_count,
        expected_min_rows=EXPECTED_MIN_CANDLES,
        detected_gaps=quality.detected_gaps,
        usable_for_backtest=usable,
        used_in_backtest=usable,
        usage_reason=(
            "Activity-First Router training-only cross-market diagnostics and frozen filter candidates"
            if usable
            else "context not usable"
        ),
    )


def _exchange_info_status() -> DataAreaStatus:
    status = ensure_exchange_info_current()
    return DataAreaStatus(
        data_kind="exchange_info",
        label="ETHUSDC exchange_info",
        status="current" if status.usable_for_backtest and not status.reason else "not_available",
        path=status.path,
        first_timestamp=None,
        last_timestamp=None,
        data_age_hours=status.data_age_hours,
        row_count=status.row_count,
        expected_min_rows=1,
        detected_gaps=None,
        usable_for_backtest=status.usable_for_backtest,
        used_in_backtest=status.usable_for_backtest,
        usage_reason="MIN_NOTIONAL, LOT_SIZE stepSize/minQty and PRICE_FILTER tickSize used by Activity-First simulation"
        if status.usable_for_backtest
        else f"exchange_info unavailable: {status.reason}",
    )


def _enhanced_kline_status() -> DataAreaStatus:
    path = next(
        (
            item.path
            for item in load_data_catalog()
            if item.symbol == "ETHUSDC" and item.interval == "1m"
        ),
        None,
    )
    available = path is not None and candle_csv_has_order_flow_fields(Path(path))
    return DataAreaStatus(
        data_kind="enhanced_kline_order_flow",
        label="ETHUSDC Kline Quote/Trade/Taker Fields",
        status="current" if available else "not_available",
        path=path,
        first_timestamp=None,
        last_timestamp=None,
        data_age_hours=None,
        row_count=None,
        expected_min_rows=EXPECTED_MIN_CANDLES,
        detected_gaps=None,
        usable_for_backtest=available,
        used_in_backtest=available,
        usage_reason=(
            "Activity-First Router training-only order-flow diagnostics and frozen filter candidates"
            if available
            else "legacy candle CSV lacks Binance quote/trade/taker fields"
        ),
    )


def _agg_trade_status() -> DataAreaStatus:
    status = load_agg_trade_data_status()
    available = bool(status and status.success)
    return DataAreaStatus(
        data_kind="ethusdc_agg_trades",
        label="ETHUSDC aggTrades 1m Features",
        status="current" if available else "not_available",
        path=status.output_path if status else None,
        first_timestamp=status.first_partition if status else None,
        last_timestamp=status.last_partition if status else None,
        data_age_hours=None,
        row_count=status.partition_count if status else 0,
        expected_min_rows=None,
        detected_gaps=None,
        usable_for_backtest=available,
        used_in_backtest=available,
        usage_reason=(
            "Activity-First Router training-only aggTrade diagnostics and frozen filter candidates"
            if available
            else "official Binance archive partitions are incomplete"
        ),
    )


def _live_microstructure_status(data_kind: str, label: str) -> DataAreaStatus:
    status = load_live_microstructure_status()
    collecting = bool(status and status.success and status.sample_count > 0)
    usable = bool(status and status.usable_for_backtest)
    return DataAreaStatus(
        data_kind=data_kind,
        label=label,
        status="current" if usable else ("collecting" if collecting else "not_available"),
        path=status.output_path if status else None,
        first_timestamp=status.first_sample_time if status else None,
        last_timestamp=status.last_sample_time if status else None,
        data_age_hours=_age_hours(status.last_sample_time) if status else None,
        row_count=status.sample_count if status else 0,
        expected_min_rows=30 * 24 * 60,
        detected_gaps=None,
        usable_for_backtest=usable,
        used_in_backtest=False,
        usage_reason=(
            "minimum 30-day live history reached; router wiring still requires validation"
            if usable
            else "live collection active; minimum 30 clean days required before backtest use"
        ),
    )


def _not_wired_status(data_kind: str, label: str, reason: str) -> DataAreaStatus:
    return DataAreaStatus(
        data_kind=data_kind,
        label=label,
        status="not_wired",
        path=None,
        first_timestamp=None,
        last_timestamp=None,
        data_age_hours=None,
        row_count=None,
        expected_min_rows=None,
        detected_gaps=None,
        usable_for_backtest=False,
        used_in_backtest=False,
        usage_reason=reason,
    )


def _inventory_not_available_status(data_kind: str) -> DataAreaStatus:
    item = next(item for item in BACKTEST_DATA_INVENTORY if item.data_kind == data_kind)
    return DataAreaStatus(
        data_kind=item.data_kind,
        label=item.label,
        status=item.status_reason,
        path=None,
        first_timestamp=None,
        last_timestamp=None,
        data_age_hours=None,
        row_count=None,
        expected_min_rows=None,
        detected_gaps=None,
        usable_for_backtest=False,
        used_in_backtest=False,
        usage_reason=(
            f"{item.status_reason}; historical_downloadable={item.historically_downloadable}; "
            f"live_collection_required={item.live_collection_required}; target_value={item.target_value}"
        ),
    )


def build_data_overview_report(run_id: str) -> DataOverviewReport:
    """Build the current data-area report without starting trading or live collection."""
    get_run_report_dir(run_id)
    return DataOverviewReport(
        run_id=run_id,
        generated_at=datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        areas=[
            _ethusdc_candle_status(),
            _enhanced_kline_status(),
            _exchange_info_status(),
            _context_candle_status("BTCUSDC", "BTCUSDC 1m Candles"),
            _context_candle_status("ETHBTC", "ETHBTC 1m Candles"),
            _context_candle_status("ETHUSDT", "ETHUSDT 1m Candles"),
            _context_candle_status("USDCUSDT", "USDCUSDT 1m Candles"),
            _agg_trade_status(),
            _inventory_not_available_status("ethusdc_trades"),
            _live_microstructure_status("bookticker_spread", "bookTicker / Spread"),
            _live_microstructure_status(
                "orderbook_depth_liquidity",
                "Orderbook / Depth / Liquidity",
            ),
        ],
    )


def save_data_overview_report(report: DataOverviewReport) -> Path:
    """Save data overview under reports/backtests/<run_id>."""
    report_dir = ensure_run_report_dir(report.run_id)
    path = report_dir / DATA_OVERVIEW_REPORT_FILENAME
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_data_overview_report(run_id: str) -> DataOverviewReport:
    """Load a saved data overview report."""
    raw = json.loads((get_run_report_dir(run_id) / DATA_OVERVIEW_REPORT_FILENAME).read_text(encoding="utf-8"))
    return DataOverviewReport(
        run_id=raw["run_id"],
        generated_at=raw["generated_at"],
        areas=[DataAreaStatus(**area) for area in raw["areas"]],
    )
