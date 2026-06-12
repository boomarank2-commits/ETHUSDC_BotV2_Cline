"""Strategy V1 training/blindtest report persistence."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.backtest.strategy_v1 import (
    StrategyV1Candidate,
    StrategyV1Trade,
    run_strategy_v1_on_candles,
    select_best_strategy_v1,
)
from src.common.config import CONFIG
from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.data.train_blind_split import TrainBlindSplit

STRATEGY_V1_REPORT_FILENAME = "strategy_v1_report.json"


@dataclass(frozen=True)
class StrategyV1TrainingBlindtestReport:
    """Training-selected Strategy V1 result on blindtest candles."""

    run_id: str
    symbol: str
    quote_asset: str
    start_capital_reference: float
    stake_usdt: float
    selected_candidate: StrategyV1Candidate
    training_family: str
    training_final_capital_reference: float
    training_total_net_pnl: float
    training_total_net_pnl_pct: float
    training_usdt_per_day: float
    training_trade_count: int
    blindtest_final_capital_reference: float
    blindtest_total_net_pnl: float
    blindtest_total_net_pnl_pct: float
    blindtest_usdt_per_day: float
    blindtest_trade_count: int
    blindtest_winning_trades: int
    blindtest_losing_trades: int
    blindtest_neutral_trades: int
    blindtest_max_drawdown: float
    blindtest_start: str
    blindtest_end: str
    positive_days: int
    negative_days: int
    neutral_days: int
    best_day_pnl: float
    worst_day_pnl: float

    def __post_init__(self) -> None:
        get_run_report_dir(self.run_id)


def _get_strategy_v1_report_path(run_id: str) -> Path:
    return get_run_report_dir(run_id) / STRATEGY_V1_REPORT_FILENAME


def _daily_pnls(trades: list[StrategyV1Trade]) -> dict[str, float]:
    daily: dict[str, float] = {}
    for trade in trades:
        day = trade.exit_time[:10]
        daily[day] = daily.get(day, 0.0) + trade.net_pnl
    return daily


def build_strategy_v1_training_blindtest_report(
    run_id: str,
    split: TrainBlindSplit,
    start_capital_reference: float = 100.0,
    stake_usdt: float = 100.0,
) -> StrategyV1TrainingBlindtestReport:
    """Train on training candles, then run frozen V1 candidate on blindtest candles."""
    get_run_report_dir(run_id)
    training_result = select_best_strategy_v1(split.training_candles, start_capital_reference)
    selected = StrategyV1Candidate(
        **{**asdict(training_result.candidate), "stake_usdt": stake_usdt}
    )
    blindtest_result = run_strategy_v1_on_candles(
        split.blindtest_candles, selected, start_capital_reference
    )
    daily = _daily_pnls(blindtest_result.trades)
    daily_values = list(daily.values())
    return StrategyV1TrainingBlindtestReport(
        run_id=run_id,
        symbol=split.symbol,
        quote_asset=CONFIG.quote_asset,
        start_capital_reference=start_capital_reference,
        stake_usdt=stake_usdt,
        selected_candidate=selected,
        training_family=selected.family,
        training_final_capital_reference=training_result.final_capital_reference,
        training_total_net_pnl=training_result.total_net_pnl,
        training_total_net_pnl_pct=training_result.total_net_pnl_pct,
        training_usdt_per_day=training_result.usdt_per_day,
        training_trade_count=training_result.trade_count,
        blindtest_final_capital_reference=blindtest_result.final_capital_reference,
        blindtest_total_net_pnl=blindtest_result.total_net_pnl,
        blindtest_total_net_pnl_pct=blindtest_result.total_net_pnl_pct,
        blindtest_usdt_per_day=blindtest_result.usdt_per_day,
        blindtest_trade_count=blindtest_result.trade_count,
        blindtest_winning_trades=blindtest_result.winning_trades,
        blindtest_losing_trades=blindtest_result.losing_trades,
        blindtest_neutral_trades=blindtest_result.neutral_trades,
        blindtest_max_drawdown=blindtest_result.max_drawdown,
        blindtest_start=split.blindtest_start,
        blindtest_end=split.blindtest_end,
        positive_days=sum(1 for pnl in daily_values if pnl > 0),
        negative_days=sum(1 for pnl in daily_values if pnl < 0),
        neutral_days=sum(1 for pnl in daily_values if pnl == 0),
        best_day_pnl=max(daily_values, default=0.0),
        worst_day_pnl=min(daily_values, default=0.0),
    )


def save_strategy_v1_report(report: StrategyV1TrainingBlindtestReport) -> Path:
    """Save Strategy V1 report as readable JSON."""
    report_dir = ensure_run_report_dir(report.run_id)
    report_path = report_dir / STRATEGY_V1_REPORT_FILENAME
    content = json.dumps(asdict(report), indent=2, sort_keys=True)
    report_path.write_text(f"{content}\n", encoding="utf-8")
    return report_path


def load_strategy_v1_report(run_id: str) -> StrategyV1TrainingBlindtestReport:
    """Load and validate Strategy V1 report."""
    raw_report: dict[str, Any] = json.loads(
        _get_strategy_v1_report_path(run_id).read_text(encoding="utf-8")
    )
    raw_report["selected_candidate"] = StrategyV1Candidate(**raw_report["selected_candidate"])
    return StrategyV1TrainingBlindtestReport(**raw_report)
