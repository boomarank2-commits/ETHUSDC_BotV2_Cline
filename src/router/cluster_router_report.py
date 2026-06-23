"""Minimal time-safe Situation -> Cluster -> Router -> Setup -> Trade report."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from src.backtest.strategy_v1 import StrategyV1Candidate, StrategyV1Result, StrategyV1Trade, run_strategy_v1_on_candles
from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.data.candle_schema import Candle
from src.data.train_blind_split import TrainBlindSplit

CLUSTER_ROUTER_REPORT_FILENAME = "cluster_router_report.json"
CLUSTER_ROUTER_DIAGNOSTICS_FILENAME = "cluster_router_diagnostics.json"
BASE_SETUP_CANDIDATE = StrategyV1Candidate(
    "situation_router",
    "cluster_router_setup_tp0.018_sl0.008_hold480",
    20,
    120,
    0.01,
    0.018,
    0.008,
    480,
    2,
    10.0,
    100.0,
    use_context_filter=False,
)
SETUP_CANDIDATES = tuple(
    StrategyV1Candidate(
        family,
        f"cluster_router_{family}_lb{lookback}_th{threshold}_tp{take_profit}_sl{stop_loss}_hold{hold}",
        lookback,
        secondary,
        threshold,
        take_profit,
        stop_loss,
        hold,
        cooldown,
        10.0,
        100.0,
        use_context_filter=False,
        trailing_stop_pct=trailing,
    )
    for family, lookback, secondary, threshold, take_profit, stop_loss, hold, cooldown, trailing in (
        ("momentum_breakout", 5, None, 0.003, 0.006, 0.004, 60, 1, None),
        ("momentum_breakout", 5, None, 0.002, 0.004, 0.003, 45, 1, None),
        ("momentum_breakout", 8, None, 0.003, 0.005, 0.003, 60, 1, 0.003),
        ("momentum_breakout", 10, None, 0.004, 0.008, 0.005, 90, 1, None),
        ("momentum_breakout", 20, None, 0.006, 0.010, 0.006, 120, 2, None),
        ("range_breakout", 8, None, 0.0015, 0.004, 0.003, 60, 1, None),
        ("range_breakout", 10, None, 0.002, 0.006, 0.004, 90, 1, None),
        ("range_breakout", 20, None, 0.003, 0.008, 0.005, 120, 2, None),
        ("range_breakout", 30, None, 0.004, 0.010, 0.006, 180, 2, None),
        ("trend_pullback", 10, 60, 0.004, 0.008, 0.005, 120, 1, None),
        ("trend_pullback", 12, 90, 0.003, 0.006, 0.004, 90, 1, None),
        ("trend_pullback", 20, 120, 0.006, 0.010, 0.006, 180, 2, None),
        ("trend_pullback", 30, 180, 0.006, 0.012, 0.006, 240, 3, None),
        ("situation_router", 10, 60, 0.006, 0.010, 0.006, 180, 2, None),
        ("situation_router", 10, 60, 0.003, 0.006, 0.004, 90, 1, None),
        ("situation_router", 20, 120, 0.006, 0.012, 0.006, 240, 2, None),
        ("situation_router", 20, 120, 0.008, 0.014, 0.007, 360, 2, 0.006),
        ("situation_router", 20, 120, 0.010, 0.018, 0.008, 480, 2, None),
        ("situation_router", 30, 180, 0.010, 0.020, 0.008, 480, 3, None),
        ("situation_router", 30, 180, 0.006, 0.012, 0.006, 240, 3, None),
        ("situation_router", 45, 270, 0.006, 0.012, 0.006, 240, 5, None),
        ("trend_pullback", 45, 270, 0.008, 0.018, 0.008, 360, 5, None),
        ("range_breakout", 45, None, 0.006, 0.018, 0.008, 360, 3, None),
        ("momentum_breakout", 30, None, 0.008, 0.016, 0.007, 240, 2, 0.006),
    )
)
SECOND_PASS_SETUP_CANDIDATES = tuple(
    StrategyV1Candidate(
        family,
        f"cluster_router_activity_pass_{family}_lb{lookback}_th{threshold}_tp{take_profit}_sl{stop_loss}_hold{hold}",
        lookback,
        secondary,
        threshold,
        take_profit,
        stop_loss,
        hold,
        cooldown,
        10.0,
        100.0,
        use_context_filter=False,
        trailing_stop_pct=trailing,
    )
    for family, lookback, secondary, threshold, take_profit, stop_loss, hold, cooldown, trailing in (
        ("momentum_breakout", 3, None, 0.0015, 0.0035, 0.0025, 45, 0, None),
        ("momentum_breakout", 5, None, 0.0020, 0.0040, 0.0030, 60, 0, 0.0025),
        ("range_breakout", 5, None, 0.0010, 0.0035, 0.0025, 45, 0, None),
        ("range_breakout", 8, None, 0.0015, 0.0040, 0.0030, 60, 0, None),
        ("trend_pullback", 8, 45, 0.0020, 0.0045, 0.0030, 75, 0, None),
        ("situation_router", 8, 45, 0.0020, 0.0045, 0.0030, 75, 0, None),
    )
)
TARGET_ACTIVITY_SETUP_CANDIDATES = tuple(
    StrategyV1Candidate(
        family,
        f"cluster_router_target_activity_{family}_lb{lookback}_th{threshold}_tp{take_profit}_sl{stop_loss}_hold{hold}",
        lookback,
        secondary,
        threshold,
        take_profit,
        stop_loss,
        hold,
        cooldown,
        10.0,
        100.0,
        use_context_filter=False,
        trailing_stop_pct=trailing,
    )
    for family, lookback, secondary, threshold, take_profit, stop_loss, hold, cooldown, trailing in (
        ("momentum_breakout", 2, None, 0.0010, 0.0030, 0.0020, 30, 0, None),
        ("momentum_breakout", 3, None, 0.0012, 0.0030, 0.0020, 45, 0, 0.0020),
        ("range_breakout", 3, None, 0.0008, 0.0030, 0.0020, 30, 0, None),
        ("trend_pullback", 5, 30, 0.0012, 0.0035, 0.0025, 45, 0, None),
        ("situation_router", 5, 30, 0.0012, 0.0035, 0.0025, 45, 0, None),
    )
)
MIN_CLUSTER_TRADES = 12
MIN_CLUSTER_NET_PNL = 0.0
MIN_CLUSTER_PROFIT_FACTOR = 1.25
VALIDATION_FRACTION = 0.25
MIN_VALIDATION_TRADES = 3
MIN_TRAIN_NET_PER_TRADE = 0.15
MIN_VALIDATION_NET_PER_TRADE = 0.15
MIN_VALIDATION_PROFIT_FACTOR = 1.35
ROBUSTNESS_BLOCK_COUNT = 4
MIN_POSITIVE_BLOCKS = 3
MIN_BLOCK_NET_PER_TRADE = -0.05
MIN_BLOCK_TRADE_COUNT = 2
MIN_SPARSE_HIGH_EDGE_ACTIVE_BLOCKS = 1
MIN_SPARSE_HIGH_EDGE_TRAIN_TRADES = 10
MIN_SPARSE_HIGH_EDGE_TRAIN_NET_PER_TRADE = 0.30
MIN_SPARSE_HIGH_EDGE_SPLIT_NET_PER_TRADE = 0.25
MIN_SPARSE_HIGH_EDGE_VALIDATION_NET_PER_TRADE = 0.30
MIN_SPARSE_HIGH_EDGE_VALIDATION_PROFIT_FACTOR = 1.60
TARGET_USDC_PER_DAY = 3.0
TARGET_MIN_SERIOUS_TRADES_PER_DAY = 24.0 / 365.0
MAX_REQUIRED_NET_PER_TRADE_RATIO = 0.10
MIN_TARGET_RELEVANT_TRADES_PER_DAY = 1.0
TARGET_ACTIVITY_MIN_TRADES_PER_DAY = 3.0
TARGET_ACTIVITY_MAX_TRADES_PER_DAY = 6.0
MIN_TARGET_RELEVANT_ACTIVE_DAYS_PER_YEAR = 120.0
MIN_TARGET_RELEVANT_NET_PER_TRADE = 0.02
OPPORTUNITY_LOOKAHEAD_CANDLES = 60
MIN_OPPORTUNITY_NET_MOVE = 0.003
MAX_OPPORTUNITY_MAE = 0.004


OPPORTUNITY_SETUP_CANDIDATES = tuple(
    StrategyV1Candidate(
        family,
        f"cluster_router_opportunity_{family}_lb{lookback}_th{threshold}_tp{take_profit}_sl{stop_loss}_hold{hold}",
        lookback,
        secondary,
        threshold,
        take_profit,
        stop_loss,
        hold,
        cooldown,
        10.0,
        100.0,
        use_context_filter=False,
        trailing_stop_pct=trailing,
    )
    for family, lookback, secondary, threshold, take_profit, stop_loss, hold, cooldown, trailing in (
        ("momentum_breakout", 2, None, 0.0006, 0.0025, 0.0018, 20, 0, None),
        ("momentum_breakout", 3, None, 0.0008, 0.0030, 0.0020, 30, 0, 0.0018),
        ("range_breakout", 3, None, 0.0005, 0.0025, 0.0018, 20, 0, None),
        ("range_breakout", 5, None, 0.0008, 0.0030, 0.0020, 30, 0, None),
        ("trend_pullback", 4, 20, 0.0008, 0.0030, 0.0020, 35, 0, None),
        ("situation_router", 4, 20, 0.0008, 0.0030, 0.0020, 35, 0, None),
        ("trend_pullback", 6, 30, 0.0010, 0.0040, 0.0025, 45, 0, None),
        ("situation_router", 6, 30, 0.0010, 0.0040, 0.0025, 45, 0, 0.0020),
    )
)


@dataclass(frozen=True)
class ClusterRouterReport:
    run_id: str
    symbol: str
    quote_asset: str
    start_capital_reference: float
    stake_quote_amount: float
    training_start: str
    training_end: str
    blindtest_start: str
    blindtest_end: str
    opportunity_event_count: int
    situation_cluster_count: int
    tested_cluster_count: int
    learned_setup_count: int
    adoption_allowed_setup_count: int
    trade_allowed_setup_count: int
    router_frozen: bool
    router_setup_count: int
    router_trade_signals: int
    blindtest_used_frozen_router: bool
    blindtest_trade_count: int
    blindtest_total_net_pnl: float
    blindtest_quote_per_day: float
    blindtest_gross_pnl: float
    blindtest_fees: float
    blindtest_no_trade_count: int
    blindtest_blocked_signal_count: int
    final_capital_reference: float
    positive_days: int | None = None
    negative_days: int | None = None
    best_day_pnl: float | None = None
    worst_day_pnl: float | None = None
    best_day: dict[str, Any] | None = None
    worst_day: dict[str, Any] | None = None
    best_full_month: dict[str, Any] | None = None
    worst_full_month: dict[str, Any] | None = None
    blindtest_daily_distribution: list[dict[str, Any]] = field(default_factory=list)
    blindtest_monthly_distribution: list[dict[str, Any]] = field(default_factory=list)
    selected_setups: list[dict[str, Any]] = field(default_factory=list)
    rejected_clusters: list[dict[str, Any]] = field(default_factory=list)
    router_artifact: dict[str, Any] = field(default_factory=dict)
    blindtest_trades: list[dict[str, Any]] = field(default_factory=list)
    rejection_summary: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        get_run_report_dir(self.run_id)


def _cluster_key(candles: list[Candle], index: int) -> str | None:
    if index < 120:
        return None
    current = candles[index]
    close = current.close
    trend_120 = close / candles[index - 120].close - 1
    trend_20 = close / candles[index - 20].close - 1
    pullback_5 = close / candles[index - 5].close - 1
    impulse_3 = close / candles[index - 3].close - 1
    recent = candles[index - 20 : index]
    volatility_20 = (max(candle.high for candle in recent) - min(candle.low for candle in recent)) / close
    if trend_120 <= -0.05 or (trend_20 <= -0.018 and impulse_3 <= -0.004):
        return None
    if trend_120 < -0.02:
        trend_bucket = "trend_recover"
    elif trend_120 >= 0.04:
        trend_bucket = "trend_high"
    elif trend_120 >= 0.01:
        trend_bucket = "trend_mid"
    else:
        trend_bucket = "trend_low"
    if trend_20 < -0.006 and impulse_3 > 0.002:
        momentum_bucket = "mom_reversal"
    elif trend_20 >= 0.012:
        momentum_bucket = "mom_high"
    elif trend_20 >= 0.004:
        momentum_bucket = "mom_mid"
    else:
        momentum_bucket = "mom_recover"
    if pullback_5 <= -0.018:
        pullback_bucket = "deep_pullback"
    elif pullback_5 < 0:
        pullback_bucket = "pullback"
    elif impulse_3 >= 0.004:
        pullback_bucket = "impulse"
    else:
        pullback_bucket = "continuation"
    vol_bucket = "vol_high" if volatility_20 >= 0.018 else "vol_low"
    return f"{trend_bucket}|{momentum_bucket}|{pullback_bucket}|{vol_bucket}"


def _activity_pass_cluster_key(candles: list[Candle], index: int) -> str | None:
    key = _cluster_key(candles, index)
    if key is None:
        return None
    trend_bucket, momentum_bucket, _pullback_bucket, vol_bucket = key.split("|")
    trend_group = "trend_strong" if trend_bucket in {"trend_high", "trend_mid"} else trend_bucket
    momentum_group = "mom_active" if momentum_bucket in {"mom_high", "mom_mid"} else momentum_bucket
    return f"activity_pass|{trend_group}|{momentum_group}|{vol_bucket}"


def _target_activity_cluster_key(candles: list[Candle], index: int) -> str | None:
    key = _cluster_key(candles, index)
    if key is None:
        return None
    trend_bucket, momentum_bucket, _pullback_bucket, _vol_bucket = key.split("|")
    trend_group = "trend_tradeable" if trend_bucket in {"trend_high", "trend_mid", "trend_low"} else trend_bucket
    momentum_group = "mom_tradeable" if momentum_bucket in {"mom_high", "mom_mid", "mom_recover"} else momentum_bucket
    return f"target_activity|{trend_group}|{momentum_group}"


def _opportunity_features(candles: list[Candle], index: int) -> dict[str, float] | None:
    if index < 120 or index + 2 >= len(candles):
        return None
    current = candles[index]
    close = current.close
    recent_20 = candles[index - 20 : index]
    range_20 = (max(candle.high for candle in recent_20) - min(candle.low for candle in recent_20)) / close
    volatility_20 = sum(abs(candles[pos].close / candles[pos - 1].close - 1) for pos in range(index - 19, index + 1))
    avg_volume_20 = sum(candle.volume for candle in recent_20) / len(recent_20)
    return {
        "trend_short": close / candles[index - 20].close - 1,
        "trend_mid": close / candles[index - 60].close - 1,
        "pullback": close / max(candle.high for candle in recent_20) - 1,
        "momentum": close / candles[index - 3].close - 1,
        "range": range_20,
        "volatility": volatility_20,
        "volume_volatility_ratio": current.volume / max(avg_volume_20 * volatility_20, 0.000001),
    }


def _mine_training_opportunities(candles: list[Candle], lookahead_candles: int = OPPORTUNITY_LOOKAHEAD_CANDLES) -> list[dict[str, Any]]:
    opportunities: list[dict[str, Any]] = []
    end = max(0, len(candles) - lookahead_candles)
    for index in range(120, end):
        features = _opportunity_features(candles, index)
        if features is None:
            continue
        entry = candles[index].close
        future = candles[index + 1 : index + lookahead_candles + 1]
        mfe_pct = max(candle.high for candle in future) / entry - 1
        mae_pct = min(candle.low for candle in future) / entry - 1
        fee_roundtrip = candles[index].close * 0.0 + 0.002
        net_move_after_fees = mfe_pct - fee_roundtrip
        if net_move_after_fees >= MIN_OPPORTUNITY_NET_MOVE and abs(mae_pct) <= MAX_OPPORTUNITY_MAE:
            opportunities.append(
                {
                    "index": index,
                    "open_time": candles[index].open_time,
                    "mfe_pct": mfe_pct,
                    "mae_pct": mae_pct,
                    "net_move_after_fees": net_move_after_fees,
                    "features": features,
                }
            )
    return opportunities


def _feature_bucket(value: float, low: float, high: float, prefix: str) -> str:
    if value < low:
        return f"{prefix}_low"
    if value > high:
        return f"{prefix}_high"
    return f"{prefix}_mid"


def _opportunity_cluster_key(candles: list[Candle], index: int) -> str | None:
    features = _opportunity_features(candles, index)
    if features is None:
        return None
    trend = _feature_bucket(features["trend_short"], -0.003, 0.006, "trend")
    momentum = _feature_bucket(features["momentum"], -0.0015, 0.0025, "mom")
    pullback = "pullback_deep" if features["pullback"] <= -0.006 else "pullback_shallow"
    volatility = "vol_active" if features["volatility"] >= 0.018 else "vol_calm"
    return f"opportunity|{trend}|{momentum}|{pullback}|{volatility}"


def _opportunity_cluster_keys_from_mined(candles: list[Candle], opportunities: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for opportunity in opportunities:
        index = int(opportunity["index"])
        key = _opportunity_cluster_key(candles, index)
        if key is not None:
            keys.add(key)
    return keys


def _activity_class(trades_per_day: float) -> str:
    if trades_per_day < 0.5:
        return "low_activity"
    if 1.0 <= trades_per_day < 3.0:
        return "usable_activity"
    if 3.0 <= trades_per_day < 6.0:
        return "target_activity"
    if 6.0 <= trades_per_day <= 10.0:
        return "high_activity"
    return "transition_activity"


def _target_activity_score(trades_per_day: float) -> float:
    if 3.0 <= trades_per_day <= 6.0:
        return 4.0
    if 1.0 <= trades_per_day < 3.0:
        return 2.5 + trades_per_day / 3.0
    if 6.0 < trades_per_day <= 10.0:
        return 2.0
    return max(0.0, trades_per_day)


def _trade_to_dict(trade: StrategyV1Trade) -> dict[str, Any]:
    return {
        "entry_time": trade.entry_time,
        "exit_time": trade.exit_time,
        "entry_price": trade.entry_price,
        "exit_price": trade.exit_price,
        "gross_pnl": trade.gross_pnl,
        "fees_paid": trade.fees_paid,
        "net_pnl": trade.net_pnl,
        "exit_reason": trade.exit_reason,
        "candidate_name": trade.candidate_name,
    }


def _trade_to_diagnostic_dict(
    trade: StrategyV1Trade,
    trade_id: int,
    candles_by_time: dict[str, int],
    candles: list[Candle],
) -> dict[str, Any]:
    row = _trade_to_dict(trade)
    entry_index = candles_by_time.get(trade.entry_time)
    exit_index = candles_by_time.get(trade.exit_time)
    mfe = None
    mae = None
    hold_minutes = None
    if entry_index is not None and exit_index is not None and exit_index >= entry_index:
        trade_candles = candles[entry_index : exit_index + 1]
        highest = max(candle.high for candle in trade_candles)
        lowest = min(candle.low for candle in trade_candles)
        mfe = (highest - trade.entry_price) * trade.quantity
        mae = (lowest - trade.entry_price) * trade.quantity
        hold_minutes = exit_index - entry_index
    row.update(
        {
            "trade_id": trade_id,
            "cluster_id": _cluster_key(candles, entry_index) if entry_index is not None else None,
            "setup_id": trade.candidate_name,
            "fees": trade.fees_paid,
            "slippage": 0.0,
            "mfe": mfe,
            "mae": mae,
            "hold_minutes": hold_minutes,
            "context_status": "not_used",
            "entry_reason": trade.family,
            "reject_reason": None,
        }
    )
    return row


def _period_distribution(trades: list[StrategyV1Trade], period_length: int) -> list[dict[str, Any]]:
    periods: dict[str, dict[str, Any]] = {}
    for trade in trades:
        period = trade.exit_time[:period_length]
        row = periods.setdefault(
            period,
            {
                "period": period,
                "gross_pnl": 0.0,
                "fees": 0.0,
                "net_pnl": 0.0,
                "trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "neutral_trades": 0,
            },
        )
        row["gross_pnl"] += trade.gross_pnl
        row["fees"] += trade.fees_paid
        row["net_pnl"] += trade.net_pnl
        row["trades"] += 1
        if trade.net_pnl > 0:
            row["winning_trades"] += 1
        elif trade.net_pnl < 0:
            row["losing_trades"] += 1
        else:
            row["neutral_trades"] += 1
    return [periods[key] for key in sorted(periods)]


def _full_months(monthly: list[dict[str, Any]], blindtest_start: str, blindtest_end: str) -> list[dict[str, Any]]:
    start_month = blindtest_start[:7]
    end_month = blindtest_end[:7]
    return [row for row in monthly if row["period"] not in {start_month, end_month}]


def _candidate_with_stake(candidate: StrategyV1Candidate, stake_quote_amount: float) -> StrategyV1Candidate:
    return StrategyV1Candidate(**{**asdict(candidate), "stake_quote_amount": stake_quote_amount})


def _candidate_dedupe_key(candidate: StrategyV1Candidate) -> tuple[Any, ...]:
    return (
        candidate.family,
        candidate.lookback_candles,
        candidate.secondary_lookback_candles,
        candidate.entry_threshold_pct,
        candidate.take_profit_pct,
        candidate.stop_loss_pct,
        candidate.max_hold_candles,
        candidate.cooldown_candles,
        candidate.use_context_filter,
        candidate.trailing_stop_pct,
    )


def _deduplicated_setup_candidates(candidates: tuple[StrategyV1Candidate, ...] = SETUP_CANDIDATES) -> tuple[StrategyV1Candidate, ...]:
    seen: set[tuple[Any, ...]] = set()
    unique: list[StrategyV1Candidate] = []
    for candidate in candidates:
        key = _candidate_dedupe_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return tuple(unique)


def _empty_result(candidate: StrategyV1Candidate, stake_quote_amount: float) -> StrategyV1Result:
    candidate = _candidate_with_stake(candidate, stake_quote_amount)
    return StrategyV1Result(candidate, 100.0, stake_quote_amount, 100.0, 0.0, 0.0, 0.0, 0, 0, 0, 0, 0.0, [])


def _result_for_cluster(
    candles: list[Candle],
    cluster_key: str,
    candidate: StrategyV1Candidate,
    stake_quote_amount: float,
    cluster_key_func: Callable[[list[Candle], int], str | None] = _cluster_key,
) -> StrategyV1Result:
    selected_times = {candle.open_time for index, candle in enumerate(candles) if cluster_key_func(candles, index) == cluster_key}
    if len(selected_times) < 121:
        # Too-small clusters cannot become trade_allowed, but keep the original full candle timeline honest.
        selected_times = set()
    return run_strategy_v1_on_candles(candles, _candidate_with_stake(candidate, stake_quote_amount), allowed_entry_times=selected_times)


def _split_training_validation(candles: list[Candle]) -> tuple[list[Candle], list[Candle]]:
    split_index = max(1, int(len(candles) * (1.0 - VALIDATION_FRACTION)))
    return candles[:split_index], candles[split_index:]


def _split_robustness_blocks(candles: list[Candle], block_count: int = ROBUSTNESS_BLOCK_COUNT) -> list[list[Candle]]:
    if block_count <= 1:
        return [candles]
    block_size = max(1, len(candles) // block_count)
    blocks: list[list[Candle]] = []
    for block_index in range(block_count):
        start = block_index * block_size
        end = len(candles) if block_index == block_count - 1 else (block_index + 1) * block_size
        block = candles[start:end]
        if block:
            blocks.append(block)
    return blocks


def _profit_factor(trades: list[StrategyV1Trade]) -> float | None:
    gross_profit = sum(trade.net_pnl for trade in trades if trade.net_pnl > 0)
    gross_loss = abs(sum(trade.net_pnl for trade in trades if trade.net_pnl < 0))
    if gross_loss == 0:
        return None if gross_profit == 0 else 999.0
    return gross_profit / gross_loss


def _net_per_trade(result: StrategyV1Result) -> float | None:
    if result.trade_count == 0:
        return None
    return result.total_net_pnl / result.trade_count


def _win_rate(result: StrategyV1Result) -> float | None:
    if result.trade_count == 0:
        return None
    return result.winning_trades / result.trade_count


def _active_days(trades: list[StrategyV1Trade]) -> int:
    return len({trade.exit_time[:10] for trade in trades if len(trade.exit_time) >= 10})


def _days_for_candles(candle_count: int) -> float:
    return max(1.0, candle_count / 1440)


def _scaled_trade_count(trades_per_day: float, candle_count: int) -> int:
    return max(1, math.ceil(trades_per_day * _days_for_candles(candle_count)))


def _target_math_for_result(result: StrategyV1Result, stake_quote_amount: float, candle_count: int) -> dict[str, Any]:
    days = _days_for_candles(candle_count)
    net_per_trade = _net_per_trade(result)
    expected_usdc_per_day = result.quote_per_day
    trades_per_day = result.trade_count / days
    required_net_per_trade = TARGET_USDC_PER_DAY / trades_per_day if trades_per_day > 0 else None
    required_trades_per_day_at_current_edge = TARGET_USDC_PER_DAY / net_per_trade if net_per_trade and net_per_trade > 0 else None
    activity_gap = max(0.0, TARGET_MIN_SERIOUS_TRADES_PER_DAY - trades_per_day)
    edge_gap = required_net_per_trade - net_per_trade if required_net_per_trade is not None and net_per_trade is not None else None
    activity_class = _activity_class(trades_per_day)
    active_days_per_year = _active_days(result.trades) / max(1.0, candle_count / 1440) * 365.0
    expected_net_per_trade = net_per_trade
    fee_to_move_ratio = (result.trade_count * stake_quote_amount * 0.002) / max(abs(result.total_net_pnl) + result.trade_count * stake_quote_amount * 0.002, 0.000001)
    target_relevant = (
        trades_per_day >= MIN_TARGET_RELEVANT_TRADES_PER_DAY
        and active_days_per_year >= MIN_TARGET_RELEVANT_ACTIVE_DAYS_PER_YEAR
        and net_per_trade is not None
        and net_per_trade >= MIN_TARGET_RELEVANT_NET_PER_TRADE
        and expected_usdc_per_day > 0
        and fee_to_move_ratio < 0.85
    )
    if expected_usdc_per_day >= TARGET_USDC_PER_DAY:
        status = "target_reached_in_training"
    elif result.trade_count == 0 or trades_per_day <= 0:
        status = "no_training_activity"
    elif required_net_per_trade is not None and required_net_per_trade > stake_quote_amount * MAX_REQUIRED_NET_PER_TRADE_RATIO:
        status = "target_math_not_reachable_current_activity"
    elif net_per_trade is not None and net_per_trade <= 0:
        status = "negative_training_edge"
    else:
        status = "target_edge_or_activity_gap"
    return {
        "trades_per_day": trades_per_day,
        "net_per_trade": net_per_trade,
        "expected_usdc_per_day": expected_usdc_per_day,
        "required_net_per_trade_for_3_usdc_day": required_net_per_trade,
        "required_trades_per_day_at_current_edge": required_trades_per_day_at_current_edge,
        "target_math_status": status,
        "activity_gap": activity_gap,
        "edge_gap": edge_gap,
        "activity_class": activity_class,
        "min_training_trades_per_year": MIN_TARGET_RELEVANT_TRADES_PER_DAY * 365.0,
        "min_training_trades_for_window": _scaled_trade_count(MIN_TARGET_RELEVANT_TRADES_PER_DAY, candle_count),
        "target_activity_min_training_trades_for_window": _scaled_trade_count(TARGET_ACTIVITY_MIN_TRADES_PER_DAY, candle_count),
        "target_activity_max_training_trades_for_window": _scaled_trade_count(TARGET_ACTIVITY_MAX_TRADES_PER_DAY, candle_count),
        "min_active_days_per_year": MIN_TARGET_RELEVANT_ACTIVE_DAYS_PER_YEAR,
        "min_expected_trades_per_day": MIN_TARGET_RELEVANT_TRADES_PER_DAY,
        "expected_net_per_day": expected_usdc_per_day,
        "expected_net_per_trade": expected_net_per_trade,
        "active_days_per_year": active_days_per_year,
        "fee_to_move_ratio": fee_to_move_ratio,
        "target_relevant": target_relevant,
    }


def _target_aware_score(row: dict[str, Any]) -> float:
    if not row.get("trade_allowed"):
        return -1_000_000_000.0
    expected = float(row.get("expected_usdc_per_day") or 0.0)
    validation_expected = float(row.get("validation_expected_usdc_per_day") or 0.0)
    trades_per_day = float(row.get("trades_per_day") or 0.0)
    validation_trades_per_day = float(row.get("validation_trades_per_day") or 0.0)
    activity_gap = float(row.get("activity_gap") or 0.0)
    edge_gap = max(0.0, float(row.get("edge_gap") or 0.0))
    active_days = float(row.get("training_active_days") or 0.0)
    validation_pf = float(row.get("setup_validation_profit_factor") or 0.0)
    activity_score = _target_activity_score(trades_per_day) + min(validation_trades_per_day, 3.0) * 0.5
    robustness_score = float(row.get("robustness_positive_block_count") or 0.0) * 0.25 + min(active_days / 24.0, 1.0)
    fee_penalty = float(row.get("fee_to_move_ratio") or 0.0) * 2.0
    target_bonus = 4.0 if row.get("target_relevant") else 0.0
    return expected * 3.0 + validation_expected * 4.0 + activity_score + robustness_score + validation_pf * 0.1 + target_bonus - activity_gap * 8.0 - edge_gap * 0.05 - fee_penalty


def _candidate_search_score(row: dict[str, Any]) -> float:
    net_per_trade = float(row.get("net_per_trade") or -1.0)
    expected = float(row.get("expected_usdc_per_day") or -999.0)
    if net_per_trade <= 0 or expected <= 0:
        return expected - 10.0 + net_per_trade
    return _target_activity_score(float(row.get("trades_per_day") or 0.0)) * 3.0 + expected * 4.0 + net_per_trade - float(row.get("fee_to_move_ratio") or 0.0) * 2.0


def _block_metric(result: StrategyV1Result, block_number: int) -> dict[str, Any]:
    return {
        "block": block_number,
        "trade_count": result.trade_count,
        "net_pnl": result.total_net_pnl,
        "net_per_trade": _net_per_trade(result),
        "profit_factor": _profit_factor(result.trades),
        "win_rate": _win_rate(result),
    }


def _robustness_summary(block_results: list[StrategyV1Result]) -> dict[str, Any]:
    block_metrics = [_block_metric(result, index + 1) for index, result in enumerate(block_results)]
    active_blocks = [metric for metric in block_metrics if int(metric["trade_count"]) >= MIN_BLOCK_TRADE_COUNT]
    positive_blocks = [metric for metric in active_blocks if float(metric["net_pnl"]) > 0]
    net_per_trade_values = [float(metric["net_per_trade"]) for metric in active_blocks if metric["net_per_trade"] is not None]
    return {
        "blocks": block_metrics,
        "active_block_count": len(active_blocks),
        "positive_block_count": len(positive_blocks),
        "worst_active_block_net_per_trade": min(net_per_trade_values) if net_per_trade_values else None,
    }


def _should_fully_evaluate_after_precheck(result: StrategyV1Result, training_candle_count: int, stake_quote_amount: float) -> bool:
    """Keep optimizer decisions transparent for candidates with either activity or positive net."""
    target_math = _target_math_for_result(result, stake_quote_amount, training_candle_count)
    return result.total_net_pnl > 0 or result.trade_count >= int(target_math["min_training_trades_for_window"])


def _approval_blocker(
    result: StrategyV1Result,
    train_result: StrategyV1Result,
    validation_result: StrategyV1Result,
    profit_factor: float | None,
    training_net_per_trade: float | None,
    setup_train_net_per_trade: float | None,
    validation_profit_factor: float | None,
    validation_net_per_trade: float | None,
    target_math: dict[str, Any],
    validation_target_math: dict[str, Any],
    robustness: dict[str, Any],
    worst_block_net_per_trade: float | None,
) -> str:
    if target_math["target_math_status"] == "target_math_not_reachable_current_activity":
        return "target_math_not_reachable_current_activity"
    if result.trade_count < int(target_math["min_training_trades_for_window"]):
        return "training_activity_floor_not_met"
    if result.total_net_pnl <= MIN_CLUSTER_NET_PNL:
        return "training_net_profit_not_positive"
    if profit_factor is None or profit_factor < MIN_CLUSTER_PROFIT_FACTOR:
        return "training_profit_factor_not_met"
    if training_net_per_trade is None or training_net_per_trade < MIN_TRAIN_NET_PER_TRADE:
        return "training_edge_not_met"
    if train_result.total_net_pnl <= 0 or setup_train_net_per_trade is None or setup_train_net_per_trade < MIN_TRAIN_NET_PER_TRADE:
        return "split_training_edge_not_met"
    if validation_target_math["target_math_status"] == "target_math_not_reachable_current_activity":
        return "validation_target_math_not_reachable_current_activity"
    if validation_result.trade_count < MIN_VALIDATION_TRADES:
        return "validation_activity_floor_not_met"
    if validation_result.total_net_pnl <= 0:
        return "validation_net_profit_not_positive"
    if validation_profit_factor is None or validation_profit_factor < MIN_VALIDATION_PROFIT_FACTOR:
        return "validation_profit_factor_not_met"
    if validation_net_per_trade is None or validation_net_per_trade < MIN_VALIDATION_NET_PER_TRADE:
        return "validation_edge_not_met"
    if robustness["active_block_count"] < MIN_POSITIVE_BLOCKS:
        return "robustness_activity_not_met"
    if robustness["positive_block_count"] < MIN_POSITIVE_BLOCKS:
        return "robustness_positive_blocks_not_met"
    if worst_block_net_per_trade is None or worst_block_net_per_trade < MIN_BLOCK_NET_PER_TRADE:
        return "robustness_worst_block_edge_not_met"
    return "training_validation_or_multiblock_robustness_not_met"


def _candidate_row(
    key: str,
    event_count: int,
    candidate: StrategyV1Candidate,
    result: StrategyV1Result,
    train_result: StrategyV1Result,
    validation_result: StrategyV1Result,
    block_results: list[StrategyV1Result],
    tested_setup_count: int,
    training_candle_count: int,
    validation_candle_count: int,
) -> dict[str, Any]:
    profit_factor = _profit_factor(result.trades)
    validation_profit_factor = _profit_factor(validation_result.trades)
    training_net_per_trade = _net_per_trade(result)
    setup_train_net_per_trade = _net_per_trade(train_result)
    validation_net_per_trade = _net_per_trade(validation_result)
    robustness = _robustness_summary(block_results)
    worst_block_net_per_trade = robustness["worst_active_block_net_per_trade"]
    target_math = _target_math_for_result(result, result.stake_quote_amount, training_candle_count)
    validation_target_math = _target_math_for_result(
        validation_result,
        validation_result.stake_quote_amount,
        validation_candle_count,
    )
    target_math_viable = target_math["target_math_status"] != "target_math_not_reachable_current_activity"
    min_cluster_trades_for_window = max(MIN_CLUSTER_TRADES, int(target_math["min_training_trades_for_window"]))
    min_sparse_trades_for_window = max(MIN_SPARSE_HIGH_EDGE_TRAIN_TRADES, int(target_math["min_training_trades_for_window"]))
    robust_multiblock_allowed = (
        target_math_viable
        and validation_target_math["target_math_status"] != "target_math_not_reachable_current_activity"
        and result.trade_count >= min_cluster_trades_for_window
        and result.total_net_pnl > MIN_CLUSTER_NET_PNL
        and profit_factor is not None
        and profit_factor >= MIN_CLUSTER_PROFIT_FACTOR
        and training_net_per_trade is not None
        and training_net_per_trade >= MIN_TRAIN_NET_PER_TRADE
        and train_result.total_net_pnl > 0
        and setup_train_net_per_trade is not None
        and setup_train_net_per_trade >= MIN_TRAIN_NET_PER_TRADE
        and validation_result.trade_count >= MIN_VALIDATION_TRADES
        and validation_result.total_net_pnl > 0
        and validation_profit_factor is not None
        and validation_profit_factor >= MIN_VALIDATION_PROFIT_FACTOR
        and validation_net_per_trade is not None
        and validation_net_per_trade >= MIN_VALIDATION_NET_PER_TRADE
        and robustness["active_block_count"] >= MIN_POSITIVE_BLOCKS
        and robustness["positive_block_count"] >= MIN_POSITIVE_BLOCKS
        and worst_block_net_per_trade is not None
        and worst_block_net_per_trade >= MIN_BLOCK_NET_PER_TRADE
    )
    sparse_high_edge_allowed = (
        target_math_viable
        and validation_target_math["target_math_status"] != "target_math_not_reachable_current_activity"
        and result.trade_count >= min_sparse_trades_for_window
        and result.total_net_pnl > MIN_CLUSTER_NET_PNL
        and profit_factor is not None
        and profit_factor >= MIN_CLUSTER_PROFIT_FACTOR
        and training_net_per_trade is not None
        and training_net_per_trade >= MIN_SPARSE_HIGH_EDGE_TRAIN_NET_PER_TRADE
        and train_result.total_net_pnl > 0
        and setup_train_net_per_trade is not None
        and setup_train_net_per_trade >= MIN_SPARSE_HIGH_EDGE_SPLIT_NET_PER_TRADE
        and validation_result.trade_count >= MIN_VALIDATION_TRADES
        and validation_result.total_net_pnl > 0
        and validation_profit_factor is not None
        and validation_profit_factor >= MIN_SPARSE_HIGH_EDGE_VALIDATION_PROFIT_FACTOR
        and validation_net_per_trade is not None
        and validation_net_per_trade >= MIN_SPARSE_HIGH_EDGE_VALIDATION_NET_PER_TRADE
        and robustness["active_block_count"] >= MIN_SPARSE_HIGH_EDGE_ACTIVE_BLOCKS
        and robustness["positive_block_count"] == robustness["active_block_count"]
        and worst_block_net_per_trade is not None
        and worst_block_net_per_trade > 0
    )
    allowed = robust_multiblock_allowed or sparse_high_edge_allowed
    approval_mode = None
    if robust_multiblock_allowed:
        approval_mode = "robust_multiblock"
    elif sparse_high_edge_allowed:
        approval_mode = "sparse_high_edge"
    reject_reason = None if allowed else _approval_blocker(
        result,
        train_result,
        validation_result,
        profit_factor,
        training_net_per_trade,
        setup_train_net_per_trade,
        validation_profit_factor,
        validation_net_per_trade,
        target_math,
        validation_target_math,
        robustness,
        worst_block_net_per_trade,
    )
    return {
        "cluster_id": key,
        "search_pass": "primary",
        "opportunity_events": event_count,
        "training_trades": result.trade_count,
        "training_net_pnl": result.total_net_pnl,
        "training_net_per_trade": training_net_per_trade,
        "training_win_rate": _win_rate(result),
        "training_quote_per_day": result.quote_per_day,
        "training_profit_factor": profit_factor,
        "training_active_days": _active_days(result.trades),
        "trades_per_day": target_math["trades_per_day"],
        "net_per_trade": target_math["net_per_trade"],
        "expected_usdc_per_day": target_math["expected_usdc_per_day"],
        "required_net_per_trade_for_3_usdc_day": target_math["required_net_per_trade_for_3_usdc_day"],
        "required_trades_per_day_at_current_edge": target_math["required_trades_per_day_at_current_edge"],
        "target_math_status": target_math["target_math_status"],
        "activity_gap": target_math["activity_gap"],
        "edge_gap": target_math["edge_gap"],
        "activity_class": target_math["activity_class"],
        "min_cluster_trades_for_window": min_cluster_trades_for_window,
        "min_sparse_trades_for_window": min_sparse_trades_for_window,
        "min_training_trades_per_year": target_math["min_training_trades_per_year"],
        "min_training_trades_for_window": target_math["min_training_trades_for_window"],
        "target_activity_min_training_trades_for_window": target_math["target_activity_min_training_trades_for_window"],
        "target_activity_max_training_trades_for_window": target_math["target_activity_max_training_trades_for_window"],
        "min_active_days_per_year": target_math["min_active_days_per_year"],
        "min_expected_trades_per_day": target_math["min_expected_trades_per_day"],
        "expected_net_per_day": target_math["expected_net_per_day"],
        "expected_net_per_trade": target_math["expected_net_per_trade"],
        "active_days_per_year": target_math["active_days_per_year"],
        "fee_to_move_ratio": target_math["fee_to_move_ratio"],
        "target_relevant": target_math["target_relevant"],
        "setup_train_trades": train_result.trade_count,
        "setup_train_net_pnl": train_result.total_net_pnl,
        "setup_train_net_per_trade": setup_train_net_per_trade,
        "setup_train_win_rate": _win_rate(train_result),
        "setup_validation_trades": validation_result.trade_count,
        "setup_validation_net_pnl": validation_result.total_net_pnl,
        "setup_validation_net_per_trade": validation_net_per_trade,
        "setup_validation_win_rate": _win_rate(validation_result),
        "setup_validation_profit_factor": validation_profit_factor,
        "validation_trades_per_day": validation_target_math["trades_per_day"],
        "validation_expected_usdc_per_day": validation_target_math["expected_usdc_per_day"],
        "validation_target_math_status": validation_target_math["target_math_status"],
        "target_math_viable": target_math_viable,
        "robustness_active_block_count": robustness["active_block_count"],
        "robustness_positive_block_count": robustness["positive_block_count"],
        "robustness_worst_active_block_net_per_trade": worst_block_net_per_trade,
        "robustness_blocks": robustness["blocks"],
        "approval_mode": approval_mode,
        "robust_multiblock_allowed": robust_multiblock_allowed,
        "sparse_high_edge_allowed": sparse_high_edge_allowed,
        "setup_name": candidate.name,
        "setup_candidate": asdict(candidate),
        "tested_setup_count": tested_setup_count,
        "trade_allowed": allowed,
        "adoption_allowed": allowed,
        "reject_reason": reject_reason,
    }


def _training_precheck_reject_reason(result: StrategyV1Result, training_candle_count: int, stake_quote_amount: float) -> str | None:
    target_math = _target_math_for_result(result, stake_quote_amount, training_candle_count)
    if target_math["target_math_status"] == "target_math_not_reachable_current_activity":
        return "target_math_not_reachable_current_activity"
    min_training_trades_for_window = int(target_math["min_training_trades_for_window"])
    if result.trade_count < min_training_trades_for_window:
        return "training_activity_floor_not_met"
    if result.total_net_pnl <= MIN_CLUSTER_NET_PNL:
        return "training_net_profit_not_positive"
    profit_factor = _profit_factor(result.trades)
    if profit_factor is None or profit_factor < MIN_CLUSTER_PROFIT_FACTOR:
        return "training_profit_factor_not_met"
    net_per_trade = _net_per_trade(result)
    if net_per_trade is None or net_per_trade < MIN_TRAIN_NET_PER_TRADE:
        return "training_edge_not_met"
    return None


def _precheck_rejected_row(
    key: str,
    event_count: int,
    candidate: StrategyV1Candidate,
    result: StrategyV1Result,
    tested_setup_count: int,
    training_candle_count: int,
    reject_reason: str,
) -> dict[str, Any]:
    empty = _empty_result(candidate, result.stake_quote_amount)
    row = _candidate_row(
        key,
        event_count,
        candidate,
        result,
        empty,
        empty,
        [empty for _ in range(ROBUSTNESS_BLOCK_COUNT)],
        tested_setup_count,
        training_candle_count,
        1,
    )
    row["reject_reason"] = reject_reason
    row["skipped_after_training_precheck"] = True
    return row


def _rejection_summary(rows: list[dict[str, Any]], deduplicated_count: int, raw_candidate_count: int) -> dict[str, Any]:
    reason_counts: dict[str, int] = {}
    pass_summary: dict[str, dict[str, int]] = {}
    for row in rows:
        reason = str(row.get("reject_reason") or "not_rejected")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        pass_name = str(row.get("search_pass") or "unknown")
        pass_row = pass_summary.setdefault(
            pass_name,
            {
                "candidate_count": 0,
                "rejected_by_target_math": 0,
                "rejected_by_activity": 0,
                "rejected_by_profit_factor": 0,
                "rejected_by_training_net": 0,
                "rejected_by_deduplication": 0,
                "rejected_by_other": 0,
            },
        )
        pass_row["candidate_count"] += 1
        if reason in {"target_math_not_reachable_current_activity", "validation_target_math_not_reachable_current_activity"}:
            pass_row["rejected_by_target_math"] += 1
        elif reason in {"training_activity_floor_not_met", "validation_activity_floor_not_met", "robustness_activity_not_met"}:
            pass_row["rejected_by_activity"] += 1
        elif reason in {"training_profit_factor_not_met", "validation_profit_factor_not_met"}:
            pass_row["rejected_by_profit_factor"] += 1
        elif reason in {"training_net_profit_not_positive", "split_training_edge_not_met", "validation_net_profit_not_positive", "validation_edge_not_met", "training_edge_not_met"}:
            pass_row["rejected_by_training_net"] += 1
        elif reason != "not_rejected":
            pass_row["rejected_by_other"] += 1
    best_found = max(rows, key=lambda row: float(row.get("training_quote_per_day") or -999999.0), default=None)
    best_activity = max(rows, key=lambda row: float(row.get("trades_per_day") or -999999.0), default=None)
    best_edge = max(rows, key=lambda row: float(row.get("net_per_trade") or -999999.0), default=None)
    best_balanced = max(
        rows,
        key=lambda row: float(row.get("training_quote_per_day") or 0.0)
        + min(float(row.get("trades_per_day") or 0.0), 1.0)
        + max(float(row.get("net_per_trade") or 0.0), 0.0) * 0.05
        - max(float(row.get("activity_gap") or 0.0), 0.0) * 2.0,
        default=None,
    )
    best_target = max(rows, key=_candidate_search_score, default=None)
    best_fee_survivor = max(
        [row for row in rows if float(row.get("net_per_trade") or -1.0) > 0],
        key=lambda row: (1.0 - float(row.get("fee_to_move_ratio") or 1.0), float(row.get("expected_usdc_per_day") or -999.0)),
        default=None,
    )
    return {
        "rejected_by_target_math": sum(reason_counts.get(reason, 0) for reason in ("target_math_not_reachable_current_activity", "validation_target_math_not_reachable_current_activity")),
        "rejected_by_activity": sum(reason_counts.get(reason, 0) for reason in ("training_activity_floor_not_met", "validation_activity_floor_not_met", "robustness_activity_not_met")),
        "rejected_by_profit_factor": sum(reason_counts.get(reason, 0) for reason in ("training_profit_factor_not_met", "validation_profit_factor_not_met")),
        "rejected_by_training_net": sum(reason_counts.get(reason, 0) for reason in ("training_net_profit_not_positive", "split_training_edge_not_met", "validation_net_profit_not_positive", "validation_edge_not_met", "training_edge_not_met")),
        "rejected_by_deduplication": max(0, raw_candidate_count - deduplicated_count),
        "rejected_by_other": sum(
            count
            for reason, count in reason_counts.items()
            if reason
            not in {
                "target_math_not_reachable_current_activity",
                "validation_target_math_not_reachable_current_activity",
                "training_activity_floor_not_met",
                "validation_activity_floor_not_met",
                "robustness_activity_not_met",
                "training_profit_factor_not_met",
                "validation_profit_factor_not_met",
                "training_net_profit_not_positive",
                "split_training_edge_not_met",
                "validation_net_profit_not_positive",
                "validation_edge_not_met",
                "training_edge_not_met",
                "not_rejected",
            }
        ),
        "search_pass_summary": pass_summary,
        "skipped_after_training_precheck": sum(1 for row in rows if row.get("skipped_after_training_precheck")),
        "best_found_candidate": best_found,
        "best_activity_candidate": best_activity,
        "best_edge_candidate": best_edge,
        "best_balanced_candidate": best_balanced,
        "best_target_candidate": best_target,
        "best_fee_survivor_candidate": best_fee_survivor,
        "top_nearly_valid_candidates": sorted(
            rows,
            key=_candidate_search_score,
            reverse=True,
        )[:10],
    }


def _build_router_pass(
    training_candles: list[Candle],
    stake_quote_amount: float,
    setup_candidates: tuple[StrategyV1Candidate, ...],
    cluster_key_func: Callable[[list[Candle], int], str | None],
    pass_name: str,
    progress_callback: Callable[[dict], None] | None = None,
    allowed_cluster_keys: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    setup_train_candles, setup_validation_candles = _split_training_validation(training_candles)
    robustness_blocks = _split_robustness_blocks(training_candles)
    cluster_counts: dict[str, int] = {}
    for index in range(len(training_candles)):
        key = cluster_key_func(training_candles, index)
        if key is not None and (allowed_cluster_keys is None or key in allowed_cluster_keys):
            cluster_counts[key] = cluster_counts.get(key, 0) + 1
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    sorted_clusters = sorted(cluster_counts.items())
    total_clusters = len(sorted_clusters)
    for cluster_number, (key, event_count) in enumerate(sorted_clusters, start=1):
        if progress_callback is not None:
            progress_callback(
                {
                    "phase": "cluster_router_training",
                    "progress_pct": 89.0 + (cluster_number / max(1, total_clusters)) * 9.0,
                    "detail": f"Cluster-Router Setup-Suche {cluster_number}/{total_clusters}",
                    "current_cluster": cluster_number,
                    "total_clusters": total_clusters,
                    "cluster_id": key,
                    "search_pass": pass_name,
                }
            )
        candidate_rows = []
        for candidate in setup_candidates:
            result = _result_for_cluster(training_candles, key, candidate, stake_quote_amount, cluster_key_func)
            precheck_reject_reason = _training_precheck_reject_reason(result, len(training_candles), stake_quote_amount)
            if precheck_reject_reason is not None and not _should_fully_evaluate_after_precheck(result, len(training_candles), stake_quote_amount):
                candidate_rows.append(
                    {**_precheck_rejected_row(
                        key,
                        event_count,
                        candidate,
                        result,
                        len(setup_candidates),
                        len(training_candles),
                        precheck_reject_reason,
                    ), "search_pass": pass_name}
                )
                continue
            train_result = _result_for_cluster(setup_train_candles, key, candidate, stake_quote_amount, cluster_key_func)
            validation_result = _result_for_cluster(setup_validation_candles, key, candidate, stake_quote_amount, cluster_key_func)
            block_results = [_result_for_cluster(block, key, candidate, stake_quote_amount, cluster_key_func) for block in robustness_blocks]
            candidate_rows.append(
                {**_candidate_row(
                    key,
                    event_count,
                    candidate,
                    result,
                    train_result,
                    validation_result,
                    block_results,
                    len(setup_candidates),
                    len(training_candles),
                    len(setup_validation_candles),
                ), "search_pass": pass_name}
            )
        allowed_rows = [row for row in candidate_rows if row["trade_allowed"]]
        if allowed_rows:
            row = max(allowed_rows, key=_target_aware_score)
        else:
            row = max(candidate_rows, key=lambda item: (float(item.get("setup_validation_net_pnl") or -999999.0), float(item.get("training_net_pnl") or -999999.0)))
        (selected if row["trade_allowed"] else rejected).append(row)
    return selected, rejected, sum(cluster_counts.values())


def _build_router(
    training_candles: list[Candle],
    stake_quote_amount: float,
    progress_callback: Callable[[dict], None] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, dict[str, Any]]:
    first_candidates = _deduplicated_setup_candidates(SETUP_CANDIDATES)
    selected, rejected, opportunity_count = _build_router_pass(
        training_candles,
        stake_quote_amount,
        first_candidates,
        _cluster_key,
        "primary",
        progress_callback,
    )
    second_pass_used = False
    second_rejected: list[dict[str, Any]] = []
    third_pass_used = False
    third_rejected: list[dict[str, Any]] = []
    opportunity_pass_used = False
    opportunity_rejected: list[dict[str, Any]] = []
    mined_opportunities = _mine_training_opportunities(training_candles)
    if not selected:
        second_pass_used = True
        second_candidates = _deduplicated_setup_candidates(SECOND_PASS_SETUP_CANDIDATES)
        selected, second_rejected, second_opportunity_count = _build_router_pass(
            training_candles,
            stake_quote_amount,
            second_candidates,
            _activity_pass_cluster_key,
            "activity_expansion",
            progress_callback,
        )
        opportunity_count += second_opportunity_count
        rejected.extend(second_rejected)
    else:
        second_candidates = tuple()
    if not selected:
        third_pass_used = True
        third_candidates = _deduplicated_setup_candidates(TARGET_ACTIVITY_SETUP_CANDIDATES)
        selected, third_rejected, third_opportunity_count = _build_router_pass(
            training_candles,
            stake_quote_amount,
            third_candidates,
            _target_activity_cluster_key,
            "target_activity",
            progress_callback,
        )
        opportunity_count += third_opportunity_count
        rejected.extend(third_rejected)
    else:
        third_candidates = tuple()
    if not selected:
        opportunity_pass_used = True
        opportunity_candidates = _deduplicated_setup_candidates(OPPORTUNITY_SETUP_CANDIDATES)
        opportunity_cluster_keys = _opportunity_cluster_keys_from_mined(training_candles, mined_opportunities)
        selected, opportunity_rejected, opportunity_opportunity_count = _build_router_pass(
            training_candles,
            stake_quote_amount,
            opportunity_candidates,
            _opportunity_cluster_key,
            "opportunity_mining",
            progress_callback,
            allowed_cluster_keys=opportunity_cluster_keys,
        )
        opportunity_count += opportunity_opportunity_count
        rejected.extend(opportunity_rejected)
    else:
        opportunity_candidates = tuple()
        opportunity_cluster_keys = set()
    summary = _rejection_summary(
        rejected,
        len(first_candidates) + len(second_candidates) + len(third_candidates) + len(opportunity_candidates),
        len(SETUP_CANDIDATES)
        + (len(SECOND_PASS_SETUP_CANDIDATES) if second_pass_used else 0)
        + (len(TARGET_ACTIVITY_SETUP_CANDIDATES) if third_pass_used else 0)
        + (len(OPPORTUNITY_SETUP_CANDIDATES) if opportunity_pass_used else 0),
    )
    summary["second_search_pass_used"] = second_pass_used
    summary["second_search_pass_name"] = "activity_expansion" if second_pass_used else None
    summary["third_search_pass_used"] = third_pass_used
    summary["third_search_pass_name"] = "target_activity" if third_pass_used else None
    summary["opportunity_search_pass_used"] = opportunity_pass_used
    summary["opportunity_search_pass_name"] = "opportunity_mining" if opportunity_pass_used else None
    summary["mined_training_opportunity_count"] = len(mined_opportunities)
    summary["mined_opportunity_cluster_count"] = len(opportunity_cluster_keys)
    summary["optimizer_status"] = "optimizer_search_space_failed" if not selected else "target_relevant_search_space_found"
    summary["primary_rejected_count"] = len(rejected) - len(second_rejected) - len(third_rejected) - len(opportunity_rejected)
    summary["second_pass_rejected_count"] = len(second_rejected)
    summary["third_pass_rejected_count"] = len(third_rejected)
    summary["opportunity_pass_rejected_count"] = len(opportunity_rejected)
    return selected, rejected, opportunity_count, summary


def _run_frozen_router(candles: list[Candle], selected_setups: list[dict[str, Any]], stake_quote_amount: float) -> StrategyV1Result:
    allowed_clusters = {row["cluster_id"] for row in selected_setups}
    def routed_key(index: int) -> str | None:
        primary = _cluster_key(candles, index)
        activity = _activity_pass_cluster_key(candles, index)
        target_activity = _target_activity_cluster_key(candles, index)
        if target_activity in allowed_clusters:
            return target_activity
        if activity in allowed_clusters:
            return activity
        return primary
    routed_times = {candle.open_time for index, candle in enumerate(candles) if routed_key(index) in allowed_clusters}
    setup_by_cluster = {row["cluster_id"]: _candidate_with_stake(StrategyV1Candidate(**dict(row["setup_candidate"])), stake_quote_amount) for row in selected_setups}
    candidate_by_time = {
        candle.open_time: setup_by_cluster[routed_key(index)]
        for index, candle in enumerate(candles)
        if routed_key(index) in setup_by_cluster
    }
    candidate = _candidate_with_stake(BASE_SETUP_CANDIDATE, stake_quote_amount)
    result = run_strategy_v1_on_candles(
        candles,
        candidate,
        allowed_entry_times=routed_times,
        allowed_entry_candidates_by_time=candidate_by_time,
    )
    return StrategyV1Result(
        result.candidate,
        result.start_capital_reference,
        result.stake_quote_amount,
        result.final_capital_reference,
        result.total_net_pnl,
        result.total_net_pnl_pct,
        result.quote_per_day,
        result.trade_count,
        result.winning_trades,
        result.losing_trades,
        result.neutral_trades,
        result.max_drawdown,
        result.trades,
        signal_count=result.signal_count,
        no_trade_count=result.no_trade_count,
        blocked_signal_count=0,
    )


def build_cluster_router_report(
    run_id: str,
    split: TrainBlindSplit,
    start_capital_reference: float = 100.0,
    stake_quote_amount: float = 100.0,
    progress_callback: Callable[[dict], None] | None = None,
) -> ClusterRouterReport:
    """Build a minimal frozen cluster-router from training only and test it on blindtest."""
    get_run_report_dir(run_id)
    selected, rejected, opportunity_count, rejection_summary = _build_router(split.training_candles, stake_quote_amount, progress_callback)
    allowed_clusters = {row["cluster_id"] for row in selected}
    blindtest_result = _run_frozen_router(split.blindtest_candles, selected, stake_quote_amount)
    blindtest_candles_by_time = {candle.open_time: index for index, candle in enumerate(split.blindtest_candles)}
    gross = sum(trade.gross_pnl for trade in blindtest_result.trades)
    fees = sum(trade.fees_paid for trade in blindtest_result.trades)
    daily_distribution = _period_distribution(blindtest_result.trades, 10)
    monthly_distribution = _period_distribution(blindtest_result.trades, 7)
    full_months = _full_months(monthly_distribution, split.blindtest_start, split.blindtest_end)
    best_day = max(daily_distribution, key=lambda row: row["net_pnl"], default=None)
    worst_day = min(daily_distribution, key=lambda row: row["net_pnl"], default=None)
    best_full_month = max(full_months, key=lambda row: row["net_pnl"], default=None)
    worst_full_month = min(full_months, key=lambda row: row["net_pnl"], default=None)
    router_artifact = {
        "frozen": bool(selected),
        "allowed_cluster_ids": sorted(allowed_clusters),
        "selected_setups": selected,
        "setup_candidates": [asdict(candidate) for candidate in SETUP_CANDIDATES],
        "second_pass_setup_candidates": [asdict(candidate) for candidate in SECOND_PASS_SETUP_CANDIDATES],
        "target_activity_setup_candidates": [asdict(candidate) for candidate in TARGET_ACTIVITY_SETUP_CANDIDATES],
        "training_only": True,
        "blindtest_learning_allowed": False,
        "rejection_summary": rejection_summary,
    }
    return ClusterRouterReport(
        run_id=run_id,
        symbol=split.symbol,
        quote_asset="USDC",
        start_capital_reference=start_capital_reference,
        stake_quote_amount=stake_quote_amount,
        training_start=split.training_start,
        training_end=split.training_end,
        blindtest_start=split.blindtest_start,
        blindtest_end=split.blindtest_end,
        opportunity_event_count=opportunity_count,
        situation_cluster_count=len(selected) + len(rejected),
        tested_cluster_count=len(selected) + len(rejected),
        learned_setup_count=len(selected),
        adoption_allowed_setup_count=len(selected),
        trade_allowed_setup_count=len(selected),
        router_frozen=bool(selected),
        router_setup_count=len(selected),
        router_trade_signals=blindtest_result.signal_count,
        blindtest_used_frozen_router=bool(selected),
        blindtest_trade_count=blindtest_result.trade_count,
        blindtest_total_net_pnl=blindtest_result.total_net_pnl,
        blindtest_quote_per_day=blindtest_result.quote_per_day,
        blindtest_gross_pnl=gross,
        blindtest_fees=fees,
        blindtest_no_trade_count=blindtest_result.no_trade_count,
        blindtest_blocked_signal_count=blindtest_result.blocked_signal_count,
        final_capital_reference=start_capital_reference + blindtest_result.total_net_pnl,
        positive_days=sum(1 for row in daily_distribution if row["net_pnl"] > 0),
        negative_days=sum(1 for row in daily_distribution if row["net_pnl"] < 0),
        best_day_pnl=best_day["net_pnl"] if best_day else None,
        worst_day_pnl=worst_day["net_pnl"] if worst_day else None,
        best_day=best_day,
        worst_day=worst_day,
        best_full_month=best_full_month,
        worst_full_month=worst_full_month,
        blindtest_daily_distribution=daily_distribution,
        blindtest_monthly_distribution=monthly_distribution,
        selected_setups=selected,
        rejected_clusters=rejected,
        router_artifact=router_artifact,
        rejection_summary=rejection_summary,
        blindtest_trades=[
            _trade_to_diagnostic_dict(trade, index + 1, blindtest_candles_by_time, split.blindtest_candles)
            for index, trade in enumerate(blindtest_result.trades)
        ],
    )


def save_cluster_router_report(report: ClusterRouterReport) -> Path:
    report_dir = ensure_run_report_dir(report.run_id)
    path = report_dir / CLUSTER_ROUTER_REPORT_FILENAME
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    diagnostics_path = report_dir / CLUSTER_ROUTER_DIAGNOSTICS_FILENAME
    diagnostics_path.write_text(json.dumps(_build_diagnostics(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _build_diagnostics(report: ClusterRouterReport) -> dict[str, Any]:
    by_exit: dict[str, dict[str, Any]] = {}
    by_candidate: dict[str, dict[str, Any]] = {}
    for trade in report.blindtest_trades:
        exit_row = by_exit.setdefault(trade["exit_reason"], {"trades": 0, "net_pnl": 0.0, "gross_pnl": 0.0, "fees": 0.0})
        candidate_row = by_candidate.setdefault(trade["candidate_name"], {"trades": 0, "net_pnl": 0.0, "gross_pnl": 0.0, "fees": 0.0})
        for row in (exit_row, candidate_row):
            row["trades"] += 1
            row["net_pnl"] += trade["net_pnl"]
            row["gross_pnl"] += trade["gross_pnl"]
            row["fees"] += trade["fees_paid"]
    blindtest_days = 365.0
    target_usdc_per_day = 3.0
    target_usdc_per_day_lower = 1.5
    target_total = target_usdc_per_day * blindtest_days
    trades_per_day = report.blindtest_trade_count / blindtest_days
    net_per_trade = report.blindtest_total_net_pnl / report.blindtest_trade_count if report.blindtest_trade_count else None
    required_net_per_trade_for_1 = 1.0 / trades_per_day if trades_per_day > 0 else None
    required_net_per_trade_for_3 = target_usdc_per_day / trades_per_day if trades_per_day > 0 else None
    required_trades_per_day_at_current_edge = target_usdc_per_day / net_per_trade if net_per_trade and net_per_trade > 0 else None
    target_activity_gap = (target_usdc_per_day / max(net_per_trade or 0.0, 0.000001)) - trades_per_day if net_per_trade and net_per_trade > 0 else None
    target_edge_gap = required_net_per_trade_for_3 - net_per_trade if required_net_per_trade_for_3 is not None and net_per_trade is not None else None
    if report.blindtest_quote_per_day >= target_usdc_per_day:
        target_math_status = "target_reached"
    elif report.blindtest_trade_count == 0 and report.rejection_summary.get("optimizer_status") in {
        "optimizer_failed_to_find_target_relevant_search_space",
        "optimizer_search_space_failed",
    }:
        target_math_status = str(report.rejection_summary.get("optimizer_status"))
    elif report.blindtest_trade_count == 0:
        target_math_status = "router_too_inactive"
    elif required_net_per_trade_for_3 is not None and required_net_per_trade_for_3 > report.stake_quote_amount * 0.10:
        target_math_status = "target_math_not_reachable_current_activity"
    elif report.blindtest_total_net_pnl <= 0:
        target_math_status = "router_failed_generalization"
    else:
        target_math_status = "target_edge_or_activity_gap"
    return {
        "run_id": report.run_id,
        "target_usdc_per_day": target_usdc_per_day,
        "target_usdc_per_day_lower": target_usdc_per_day_lower,
        "target_total_usdc": target_total,
        "target_gap_usdc": target_total - report.blindtest_total_net_pnl,
        "target_gap_per_day": target_usdc_per_day - report.blindtest_quote_per_day,
        "trades_per_day": trades_per_day,
        "net_per_trade": net_per_trade,
        "required_net_per_trade_for_1_usdc_day": required_net_per_trade_for_1,
        "required_net_per_trade_for_3_usdc_day": required_net_per_trade_for_3,
        "required_trades_per_day_at_current_net_per_trade": required_trades_per_day_at_current_edge,
        "target_activity_gap": target_activity_gap,
        "target_edge_gap": target_edge_gap,
        "target_math_status": target_math_status,
        "blindtest_trade_count": report.blindtest_trade_count,
        "blindtest_gross_pnl": report.blindtest_gross_pnl,
        "blindtest_fees": report.blindtest_fees,
        "blindtest_net_pnl": report.blindtest_total_net_pnl,
        "fee_to_gross_warning": report.blindtest_fees > max(0.0, report.blindtest_gross_pnl),
        "needed_net_per_trade_at_current_trade_count": target_total / report.blindtest_trade_count if report.blindtest_trade_count else None,
        "selected_setup_count": len(report.selected_setups),
        "rejected_cluster_count": len(report.rejected_clusters),
        "rejection_summary": report.rejection_summary,
        "optimizer_status": report.rejection_summary.get("optimizer_status"),
        "rejected_by_target_math": report.rejection_summary.get("rejected_by_target_math", 0),
        "rejected_by_activity": report.rejection_summary.get("rejected_by_activity", 0),
        "rejected_by_profit_factor": report.rejection_summary.get("rejected_by_profit_factor", 0),
        "rejected_by_training_net": report.rejection_summary.get("rejected_by_training_net", 0),
        "rejected_by_deduplication": report.rejection_summary.get("rejected_by_deduplication", 0),
        "rejected_by_other": report.rejection_summary.get("rejected_by_other", 0),
        "top_nearly_valid_candidates": report.rejection_summary.get("top_nearly_valid_candidates", []),
        "best_found_candidate": report.rejection_summary.get("best_found_candidate"),
        "best_activity_candidate": report.rejection_summary.get("best_activity_candidate"),
        "best_edge_candidate": report.rejection_summary.get("best_edge_candidate"),
        "best_balanced_candidate": report.rejection_summary.get("best_balanced_candidate"),
        "best_target_candidate": report.rejection_summary.get("best_target_candidate"),
        "best_fee_survivor_candidate": report.rejection_summary.get("best_fee_survivor_candidate"),
        "exit_reason_breakdown": by_exit,
        "candidate_breakdown": by_candidate,
        "best_full_month": report.best_full_month,
        "worst_full_month": report.worst_full_month,
        "best_day": report.best_day,
        "worst_day": report.worst_day,
        "top_rejected_by_validation_net_pnl": sorted(
            report.rejected_clusters,
            key=lambda row: float(row.get("setup_validation_net_pnl") or -999999.0),
            reverse=True,
        )[:10],
    }


def load_cluster_router_report(run_id: str) -> ClusterRouterReport:
    raw = json.loads((get_run_report_dir(run_id) / CLUSTER_ROUTER_REPORT_FILENAME).read_text(encoding="utf-8"))
    return ClusterRouterReport(**raw)