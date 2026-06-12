"""Strategy V0 training/blindtest report persistence."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.backtest.strategy_v0 import (
    StrategyV0Candidate,
    run_strategy_v0_on_candles,
    select_best_strategy_v0,
)
from src.common.config import CONFIG
from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.data.train_blind_split import TrainBlindSplit

STRATEGY_V0_REPORT_FILENAME = "strategy_v0_report.json"


@dataclass(frozen=True)
class StrategyV0TrainingBlindtestReport:
    """Training-selected Strategy V0 result on blindtest candles."""

    run_id: str
    symbol: str
    quote_asset: str
    start_capital: float
    selected_candidate: StrategyV0Candidate
    training_final_capital: float
    training_total_pnl: float
    training_total_pnl_pct: float
    training_trade_count: int
    blindtest_final_capital: float
    blindtest_total_pnl: float
    blindtest_total_pnl_pct: float
    blindtest_trade_count: int
    blindtest_winning_trades: int
    blindtest_losing_trades: int
    blindtest_max_drawdown: float
    blindtest_start: str
    blindtest_end: str

    def __post_init__(self) -> None:
        get_run_report_dir(self.run_id)


def _get_strategy_v0_report_path(run_id: str) -> Path:
    return get_run_report_dir(run_id) / STRATEGY_V0_REPORT_FILENAME


def build_strategy_v0_training_blindtest_report(
    run_id: str,
    split: TrainBlindSplit,
    start_capital: float = 100.0,
) -> StrategyV0TrainingBlindtestReport:
    """Train on training candles, then run frozen candidate on blindtest candles."""
    get_run_report_dir(run_id)
    training_result = select_best_strategy_v0(split.training_candles, start_capital)
    blindtest_result = run_strategy_v0_on_candles(
        split.blindtest_candles, training_result.candidate, start_capital
    )
    return StrategyV0TrainingBlindtestReport(
        run_id=run_id,
        symbol=split.symbol,
        quote_asset=CONFIG.quote_asset,
        start_capital=start_capital,
        selected_candidate=training_result.candidate,
        training_final_capital=training_result.final_capital,
        training_total_pnl=training_result.total_pnl,
        training_total_pnl_pct=training_result.total_pnl_pct,
        training_trade_count=training_result.trade_count,
        blindtest_final_capital=blindtest_result.final_capital,
        blindtest_total_pnl=blindtest_result.total_pnl,
        blindtest_total_pnl_pct=blindtest_result.total_pnl_pct,
        blindtest_trade_count=blindtest_result.trade_count,
        blindtest_winning_trades=blindtest_result.winning_trades,
        blindtest_losing_trades=blindtest_result.losing_trades,
        blindtest_max_drawdown=blindtest_result.max_drawdown,
        blindtest_start=split.blindtest_start,
        blindtest_end=split.blindtest_end,
    )


def save_strategy_v0_report(report: StrategyV0TrainingBlindtestReport) -> Path:
    """Save Strategy V0 report as readable JSON."""
    report_dir = ensure_run_report_dir(report.run_id)
    report_path = report_dir / STRATEGY_V0_REPORT_FILENAME
    content = json.dumps(asdict(report), indent=2, sort_keys=True)
    report_path.write_text(f"{content}\n", encoding="utf-8")
    return report_path


def load_strategy_v0_report(run_id: str) -> StrategyV0TrainingBlindtestReport:
    """Load and validate Strategy V0 report."""
    raw_report: dict[str, Any] = json.loads(
        _get_strategy_v0_report_path(run_id).read_text(encoding="utf-8")
    )
    raw_report["selected_candidate"] = StrategyV0Candidate(**raw_report["selected_candidate"])
    return StrategyV0TrainingBlindtestReport(**raw_report)
