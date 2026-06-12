"""Buy-and-hold blindtest benchmark report.

This is a simple LONG-only Spot benchmark without fees or slippage.
It is not a strategy optimizer, router, cluster model or final bot logic.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.common.config import CONFIG
from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.data.train_blind_split import TrainBlindSplit

BUY_HOLD_BENCHMARK_REPORT_FILENAME = "buy_hold_benchmark_report.json"


@dataclass(frozen=True)
class BuyHoldBenchmarkReport:
    """Technical Buy-and-Hold benchmark for the blindtest window."""

    run_id: str
    symbol: str
    quote_asset: str
    start_capital: float
    blindtest_start: str
    blindtest_end: str
    entry_price: float
    exit_price: float
    quantity: float
    final_capital: float
    total_pnl: float
    total_pnl_pct: float
    trade_count: int

    def __post_init__(self) -> None:
        get_run_report_dir(self.run_id)


def _get_buy_hold_benchmark_report_path(run_id: str) -> Path:
    return get_run_report_dir(run_id) / BUY_HOLD_BENCHMARK_REPORT_FILENAME


def build_buy_hold_benchmark_report(
    run_id: str,
    split: TrainBlindSplit,
    start_capital: float = 100.0,
) -> BuyHoldBenchmarkReport:
    """Build a LONG-only Spot buy-and-hold benchmark from blindtest candles only."""
    get_run_report_dir(run_id)
    if start_capital <= 0:
        msg = "start_capital must be positive"
        raise ValueError(msg)
    if not split.blindtest_candles:
        msg = "blindtest_candles must not be empty"
        raise ValueError(msg)

    entry_price = split.blindtest_candles[0].close
    exit_price = split.blindtest_candles[-1].close
    quantity = start_capital / entry_price
    final_capital = quantity * exit_price
    total_pnl = final_capital - start_capital
    total_pnl_pct = total_pnl / start_capital * 100
    return BuyHoldBenchmarkReport(
        run_id=run_id,
        symbol=split.symbol,
        quote_asset=CONFIG.quote_asset,
        start_capital=start_capital,
        blindtest_start=split.blindtest_start,
        blindtest_end=split.blindtest_end,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        final_capital=final_capital,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        trade_count=1,
    )


def save_buy_hold_benchmark_report(report: BuyHoldBenchmarkReport) -> Path:
    """Save a Buy-and-Hold benchmark report as readable JSON."""
    report_dir = ensure_run_report_dir(report.run_id)
    report_path = report_dir / BUY_HOLD_BENCHMARK_REPORT_FILENAME
    content = json.dumps(asdict(report), indent=2, sort_keys=True)
    report_path.write_text(f"{content}\n", encoding="utf-8")
    return report_path


def load_buy_hold_benchmark_report(run_id: str) -> BuyHoldBenchmarkReport:
    """Load and validate a Buy-and-Hold benchmark report."""
    raw_report: dict[str, Any] = json.loads(
        _get_buy_hold_benchmark_report_path(run_id).read_text(encoding="utf-8")
    )
    return BuyHoldBenchmarkReport(**raw_report)
