"""Technical data preparation report for local candle data."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.data.agg_trade_data_ensure import load_agg_trade_data_status
from src.data.candle_csv_io import candle_csv_has_order_flow_fields
from src.data.candle_quality import CandleQualityReport, build_candle_quality_report
from src.data.data_catalog import load_data_catalog
from src.data.derived_timeframes import build_derived_timeframe_counts
from src.data.live_microstructure import load_live_microstructure_status
from src.data.local_candle_loader import (
    build_local_candle_quality_from_catalog,
    load_local_candle_dataset_from_catalog,
)

DATA_PREPARATION_REPORT_FILENAME = "data_preparation_report.json"


@dataclass(frozen=True)
class DataPreparationReport:
    """Technical report describing local candle data readiness."""

    run_id: str
    symbol: str
    interval: str
    candle_count: int
    first_open_time: str
    last_open_time: str
    detected_gaps: int
    has_required_lookback: bool
    usable_for_backtest: bool
    reason: str | None
    ethusdc_1m_available: bool = True
    enhanced_kline_fields_available: bool = False
    derived_timeframes_available: bool = False
    derived_timeframe_candle_counts: dict[str, int] | None = None
    btcusdc_context_available: bool = False
    ethbtc_context_available: bool = False
    ethusdt_context_available: bool = False
    usdcusdt_context_available: bool = False
    trades_available: bool = False
    agg_trades_available: bool = False
    bookticker_available: bool = False
    orderbook_available: bool = False
    live_microstructure_usable_for_backtest: bool = False
    data_source_status: dict[str, str] | None = None

    def __post_init__(self) -> None:
        get_run_report_dir(self.run_id)


def _get_data_preparation_report_path(run_id: str) -> Path:
    return get_run_report_dir(run_id) / DATA_PREPARATION_REPORT_FILENAME


def _build_unusable_reason(has_required_lookback: bool, detected_gaps: int) -> str | None:
    reasons: list[str] = []
    if not has_required_lookback:
        reasons.append("not enough candles for required lookback")
    if detected_gaps != 0:
        reasons.append("detected candle time gaps")
    if not reasons:
        return None
    return "; ".join(reasons)


def _context_available(symbol: str) -> bool:
    try:
        build_local_candle_quality_from_catalog(symbol, "1m")
    except Exception:  # noqa: BLE001
        return False
    return True


def _status(available: bool) -> str:
    return "available" if available else "missing"


def _catalog_path(symbol: str) -> Path | None:
    for entry in load_data_catalog():
        if entry.symbol == symbol and entry.interval == "1m":
            return Path(entry.path)
    return None


def build_data_preparation_report(
    run_id: str,
    quality: CandleQualityReport | None = None,
) -> DataPreparationReport:
    """Build a technical data preparation report without backtest calculation."""
    get_run_report_dir(run_id)
    derived_counts: dict[str, int] | None = None
    if quality is None:
        dataset = load_local_candle_dataset_from_catalog("ETHUSDC", "1m")
        quality = build_candle_quality_report(dataset)
        derived_counts = build_derived_timeframe_counts(dataset.candles)
    else:
        derived_counts = {timeframe: 0 for timeframe in ("5m", "15m", "30m", "1h", "4h", "1d")}
    usable_for_backtest = quality.has_required_lookback and quality.detected_gaps == 0
    btcusdc_available = _context_available("BTCUSDC")
    ethbtc_available = _context_available("ETHBTC")
    ethusdt_available = _context_available("ETHUSDT")
    usdcusdt_available = _context_available("USDCUSDT")
    ethusdc_path = _catalog_path("ETHUSDC")
    enhanced_klines_available = (
        ethusdc_path is not None and candle_csv_has_order_flow_fields(ethusdc_path)
    )
    agg_trade_status = load_agg_trade_data_status()
    agg_trades_available = bool(agg_trade_status and agg_trade_status.success)
    live_status = load_live_microstructure_status()
    live_available = bool(live_status and live_status.sample_count > 0)
    live_usable = bool(live_status and live_status.usable_for_backtest)
    live_source_status = (
        "available"
        if live_usable
        else ("collecting_not_mature" if live_available else "not_started")
    )
    derived_available = bool(derived_counts) and any(count > 0 for count in derived_counts.values())
    data_source_status = {
        "ETHUSDC 1m": _status(True),
        "enhanced kline order flow": _status(enhanced_klines_available),
        "derived_timeframes": _status(derived_available),
        "BTCUSDC context": _status(btcusdc_available),
        "ETHBTC context": _status(ethbtc_available),
        "ETHUSDT context": _status(ethusdt_available),
        "USDCUSDT context": _status(usdcusdt_available),
        "trades": "rejected_redundant_raw_source",
        "aggTrades": _status(agg_trades_available),
        "bookTicker": live_source_status,
        "orderbook": live_source_status,
    }
    return DataPreparationReport(
        run_id=run_id,
        symbol=quality.symbol,
        interval=quality.interval,
        candle_count=quality.candle_count,
        first_open_time=quality.first_open_time,
        last_open_time=quality.last_open_time,
        detected_gaps=quality.detected_gaps,
        has_required_lookback=quality.has_required_lookback,
        usable_for_backtest=usable_for_backtest,
        reason=_build_unusable_reason(quality.has_required_lookback, quality.detected_gaps),
        ethusdc_1m_available=True,
        enhanced_kline_fields_available=enhanced_klines_available,
        derived_timeframes_available=derived_available,
        derived_timeframe_candle_counts=derived_counts,
        btcusdc_context_available=btcusdc_available,
        ethbtc_context_available=ethbtc_available,
        ethusdt_context_available=ethusdt_available,
        usdcusdt_context_available=usdcusdt_available,
        trades_available=False,
        agg_trades_available=agg_trades_available,
        bookticker_available=live_available,
        orderbook_available=live_available,
        live_microstructure_usable_for_backtest=live_usable,
        data_source_status=data_source_status,
    )


def save_data_preparation_report(report: DataPreparationReport) -> Path:
    """Save a data preparation report as readable JSON."""
    report_dir = ensure_run_report_dir(report.run_id)
    report_path = report_dir / DATA_PREPARATION_REPORT_FILENAME
    content = json.dumps(asdict(report), indent=2, sort_keys=True)
    report_path.write_text(f"{content}\n", encoding="utf-8")
    return report_path


def load_data_preparation_report(run_id: str) -> DataPreparationReport:
    """Load and validate a data preparation report."""
    raw_report: dict[str, Any] = json.loads(
        _get_data_preparation_report_path(run_id).read_text(encoding="utf-8")
    )
    return DataPreparationReport(**raw_report)
