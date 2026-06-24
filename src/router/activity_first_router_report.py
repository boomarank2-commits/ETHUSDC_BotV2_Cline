"""Activity-first router report for ETHUSDC LONG-only backtests.

This router is intentionally separate from the legacy cluster router. It first creates
many active entry candidates, measures their activity, and only then evaluates edge
after fees, drawdown and target distance.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.common.config import CONFIG
from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.data.candle_schema import Candle
from src.data.train_blind_split import TrainBlindSplit

ACTIVITY_FIRST_ROUTER_REPORT_FILENAME = "activity_first_router_report.json"
TARGET_QUOTE_PER_DAY = 3.0
FEE_BPS = 10.0


@dataclass(frozen=True)
class ActivityFirstCandidate:
    """One deterministic LONG-only activity-first entry/exit setup."""

    candidate_id: str
    family: str
    lookback_candles: int
    entry_threshold_pct: float
    take_profit_pct: float
    stop_loss_pct: float
    max_hold_candles: int
    cooldown_candles: int
    stake_quote_amount: float


@dataclass(frozen=True)
class ActivityFirstTrade:
    """One completed diagnostic LONG-only trade."""

    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    stake_quote_amount: float
    quantity: float
    gross_pnl: float
    fees_paid: float
    net_pnl: float
    net_pnl_pct: float
    exit_reason: str
    family: str
    candidate_id: str


@dataclass(frozen=True)
class ActivityFirstSimulationResult:
    """Result for one activity-first candidate on one candle window."""

    candidate: ActivityFirstCandidate
    start_capital_reference: float
    final_capital_reference: float
    total_gross_pnl: float
    total_fees: float
    total_net_pnl: float
    quote_per_day: float
    trade_count: int
    trades_per_day: float
    winning_trades: int
    losing_trades: int
    neutral_trades: int
    max_drawdown: float
    signal_count: int
    no_trade_count: int
    trades: list[ActivityFirstTrade]


@dataclass(frozen=True)
class ActivityFirstRouterReport:
    """UI/report friendly activity-first router result."""

    run_id: str
    router_name: str
    symbol: str
    quote_asset: str
    start_capital_reference: float
    stake_quote_amount: float
    profile: str
    training_start: str
    training_end: str
    blindtest_start: str
    blindtest_end: str
    candidate_space_status: str
    candidate_space_reason: str
    candidate_count: int
    setup_test_count: int
    trade_allowed_setup_count: int
    selected_candidate_count: int
    rejected_candidate_count: int
    selected_setups: list[dict[str, Any]]
    rejection_summary: dict[str, Any]
    best_activity_candidate: dict[str, Any] | None
    best_edge_candidate: dict[str, Any] | None
    best_balanced_candidate: dict[str, Any] | None
    best_fee_survivor_candidate: dict[str, Any] | None
    best_target_candidate: dict[str, Any] | None
    blindtest_final_capital_reference: float
    blindtest_total_gross_pnl: float
    blindtest_fees: float
    blindtest_total_net_pnl: float
    blindtest_total_net_pnl_pct: float
    blindtest_quote_per_day: float
    blindtest_trade_count: int
    blindtest_winning_trades: int
    blindtest_losing_trades: int
    blindtest_neutral_trades: int
    blindtest_max_drawdown: float
    positive_days: int
    negative_days: int
    neutral_days: int
    best_day_pnl: float
    worst_day_pnl: float
    best_training_quote_per_day: float
    target_quote_per_day: float
    target_ratio_to_3_usdc_day: float
    target_feasibility_status: str
    router_artifact: dict[str, Any] = field(default_factory=dict)
    blindtest_trades: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        get_run_report_dir(self.run_id)


@dataclass(frozen=True)
class _TrainingEvaluation:
    candidate: ActivityFirstCandidate
    result: ActivityFirstSimulationResult
    activity_class: str
    trade_allowed: bool
    rejection_reason: str | None
    balanced_score: float
    target_distance: float


def _get_activity_first_router_report_path(run_id: str) -> Path:
    return get_run_report_dir(run_id) / ACTIVITY_FIRST_ROUTER_REPORT_FILENAME


def _activity_class(trades_per_day: float) -> str:
    if trades_per_day < 0.5:
        return "very_low_activity"
    if trades_per_day < 1.0:
        return "low_activity"
    if trades_per_day < 3.0:
        return "usable_activity"
    if trades_per_day < 6.0:
        return "target_activity"
    if trades_per_day <= 10.0:
        return "high_activity"
    return "overactive"


def _candidate_rejection(result: ActivityFirstSimulationResult) -> str | None:
    trades_per_day = result.trades_per_day
    if trades_per_day < 1.0:
        return "rejected_by_activity"
    if trades_per_day > 10.0:
        return "rejected_by_overactivity"
    if result.total_net_pnl <= 0:
        return "rejected_by_training_net"
    if result.total_fees >= max(0.000001, abs(result.total_gross_pnl)):
        return "rejected_by_fees"
    if result.max_drawdown > 25.0:
        return "rejected_by_drawdown"
    return None


def _generate_activity_first_candidates(
    stake_quote_amount: float,
    profile: str,
) -> list[ActivityFirstCandidate]:
    families = (
        "momentum_entry",
        "pullback_entry",
        "range_breakout_entry",
        "volatility_expansion_entry",
        "mean_reversion_entry",
        "trend_continuation_entry",
    )
    if profile == "conservative":
        lookbacks = (10, 20, 30, 60)
        setups = ((0.0015, 0.004, 0.003, 60), (0.0025, 0.006, 0.004, 120))
    elif profile == "aggressive":
        lookbacks = (5, 10, 15, 30, 60, 120)
        setups = (
            (0.0005, 0.003, 0.003, 30),
            (0.0010, 0.004, 0.003, 60),
            (0.0015, 0.006, 0.004, 120),
            (0.0025, 0.008, 0.006, 180),
        )
    else:
        lookbacks = (5, 10, 15, 30, 60)
        setups = (
            (0.00075, 0.0035, 0.003, 45),
            (0.00125, 0.0050, 0.004, 90),
            (0.00200, 0.0075, 0.005, 150),
        )
    candidates: list[ActivityFirstCandidate] = []
    for family in families:
        for lookback in lookbacks:
            for threshold, tp, sl, hold in setups:
                candidate_id = (
                    f"{family}_lb{lookback}_th{threshold}_tp{tp}_sl{sl}_hold{hold}"
                )
                candidates.append(
                    ActivityFirstCandidate(
                        candidate_id=candidate_id,
                        family=family,
                        lookback_candles=lookback,
                        entry_threshold_pct=threshold,
                        take_profit_pct=tp,
                        stop_loss_pct=sl,
                        max_hold_candles=hold,
                        cooldown_candles=max(1, lookback // 5),
                        stake_quote_amount=stake_quote_amount,
                    )
                )
    return candidates


def _entry_signal(candles: list[Candle], index: int, candidate: ActivityFirstCandidate) -> bool:
    current = candles[index]
    prior = candles[index - 1]
    lookback = candidate.lookback_candles
    previous = candles[index - lookback]
    threshold = candidate.entry_threshold_pct
    window = candles[index - lookback : index]
    recent_high = max(candle.high for candle in window)
    recent_low = min(candle.low for candle in window)
    recent_range = (recent_high - recent_low) / current.close
    if candidate.family == "momentum_entry":
        return current.close > previous.close * (1 + threshold)
    if candidate.family == "pullback_entry":
        trend_ok = current.close > previous.close * (1 + threshold)
        pullback_seen = prior.close < max(candle.close for candle in window) * (1 - threshold)
        return trend_ok and pullback_seen and current.close > prior.close
    if candidate.family == "range_breakout_entry":
        return current.close > recent_high * (1 + threshold / 2)
    if candidate.family == "volatility_expansion_entry":
        return recent_range > threshold * 3 and current.close > prior.close * (1 + threshold / 2)
    if candidate.family == "mean_reversion_entry":
        near_recent_low = prior.close <= recent_low * (1 + threshold * 2)
        return near_recent_low and current.close > prior.close * (1 + threshold / 2)
    if candidate.family == "trend_continuation_entry":
        short_trend = current.close > candles[index - max(2, lookback // 2)].close
        long_trend = current.close > previous.close * (1 + threshold)
        return short_trend and long_trend and current.close > prior.close
    msg = f"unsupported activity-first family: {candidate.family}"
    raise ValueError(msg)


def _exit_trade(
    candles: list[Candle],
    entry_index: int,
    candidate: ActivityFirstCandidate,
) -> tuple[int, str, float]:
    entry_price = candles[entry_index].close
    take_profit_price = entry_price * (1 + candidate.take_profit_pct)
    stop_loss_price = entry_price * (1 - candidate.stop_loss_pct)
    max_exit_index = min(entry_index + candidate.max_hold_candles, len(candles) - 1)
    for exit_index in range(entry_index + 1, max_exit_index + 1):
        candle = candles[exit_index]
        if candle.low <= stop_loss_price:
            return exit_index, "stop_loss", stop_loss_price
        if candle.high >= take_profit_price:
            return exit_index, "take_profit", take_profit_price
    return max_exit_index, "max_hold", candles[max_exit_index].close


def _run_candidate_on_candles(
    candles: list[Candle],
    candidate: ActivityFirstCandidate,
    start_capital_reference: float = 100.0,
) -> ActivityFirstSimulationResult:
    trades: list[ActivityFirstTrade] = []
    signal_count = 0
    no_trade_count = 0
    cumulative_net = 0.0
    cumulative_gross = 0.0
    cumulative_fees = 0.0
    peak_reference = start_capital_reference
    max_drawdown = 0.0
    fee_rate = FEE_BPS / 10_000
    index = max(candidate.lookback_candles, 2)
    while index < len(candles) - 1:
        if not _entry_signal(candles, index, candidate):
            no_trade_count += 1
            index += 1
            continue
        signal_count += 1
        entry = candles[index]
        entry_price = entry.close
        quantity = candidate.stake_quote_amount / entry_price
        exit_index, exit_reason, exit_price = _exit_trade(candles, index, candidate)
        exit_candle = candles[exit_index]
        gross_pnl = quantity * (exit_price - entry_price)
        fees_paid = candidate.stake_quote_amount * fee_rate + quantity * exit_price * fee_rate
        net_pnl = gross_pnl - fees_paid
        cumulative_gross += gross_pnl
        cumulative_fees += fees_paid
        cumulative_net += net_pnl
        equity = start_capital_reference + cumulative_net
        peak_reference = max(peak_reference, equity)
        if peak_reference > 0:
            max_drawdown = max(max_drawdown, (peak_reference - equity) / peak_reference * 100)
        trades.append(
            ActivityFirstTrade(
                entry_time=entry.open_time,
                exit_time=exit_candle.open_time,
                entry_price=entry_price,
                exit_price=exit_price,
                stake_quote_amount=candidate.stake_quote_amount,
                quantity=quantity,
                gross_pnl=gross_pnl,
                fees_paid=fees_paid,
                net_pnl=net_pnl,
                net_pnl_pct=net_pnl / candidate.stake_quote_amount * 100,
                exit_reason=exit_reason,
                family=candidate.family,
                candidate_id=candidate.candidate_id,
            )
        )
        index = exit_index + 1 + candidate.cooldown_candles
    days = max(1.0, len(candles) / 1440)
    final_capital = start_capital_reference + cumulative_net
    return ActivityFirstSimulationResult(
        candidate=candidate,
        start_capital_reference=start_capital_reference,
        final_capital_reference=final_capital,
        total_gross_pnl=cumulative_gross,
        total_fees=cumulative_fees,
        total_net_pnl=cumulative_net,
        quote_per_day=cumulative_net / days,
        trade_count=len(trades),
        trades_per_day=len(trades) / days,
        winning_trades=sum(1 for trade in trades if trade.net_pnl > 0),
        losing_trades=sum(1 for trade in trades if trade.net_pnl < 0),
        neutral_trades=sum(1 for trade in trades if trade.net_pnl == 0),
        max_drawdown=max_drawdown,
        signal_count=signal_count,
        no_trade_count=no_trade_count,
        trades=trades,
    )


def _daily_pnls(trades: list[ActivityFirstTrade]) -> dict[str, float]:
    daily: dict[str, float] = {}
    for trade in trades:
        day = trade.exit_time[:10]
        daily[day] = daily.get(day, 0.0) + trade.net_pnl
    return daily


def _trade_to_dict(trade: ActivityFirstTrade) -> dict[str, Any]:
    return asdict(trade)


def _candidate_summary(evaluation: _TrainingEvaluation) -> dict[str, Any]:
    result = evaluation.result
    candidate = evaluation.candidate
    return {
        "candidate_id": candidate.candidate_id,
        "strategy_family": candidate.family,
        "search_pass": "activity_first",
        "activity_class": evaluation.activity_class,
        "trades_per_day": result.trades_per_day,
        "active_days": len(_daily_pnls(result.trades)),
        "training_trade_count": result.trade_count,
        "training_gross_pnl": result.total_gross_pnl,
        "training_fees": result.total_fees,
        "training_net_pnl": result.total_net_pnl,
        "training_quote_per_day": result.quote_per_day,
        "training_win_rate": result.winning_trades / result.trade_count if result.trade_count else None,
        "training_profit_factor": _profit_factor(result.trades),
        "max_drawdown": result.max_drawdown,
        "average_hold_minutes": _average_hold_minutes(result.trades),
        "tp": candidate.take_profit_pct,
        "sl": candidate.stop_loss_pct,
        "max_hold": candidate.max_hold_candles,
        "trailing_stop": None,
        "context_filters": [],
        "rejection_reason": evaluation.rejection_reason,
        "distance_to_target": evaluation.target_distance,
        "balanced_score": evaluation.balanced_score,
    }


def _profit_factor(trades: list[ActivityFirstTrade]) -> float | None:
    wins = sum(trade.net_pnl for trade in trades if trade.net_pnl > 0)
    losses = abs(sum(trade.net_pnl for trade in trades if trade.net_pnl < 0))
    if losses == 0:
        return None if wins == 0 else 999.0
    return wins / losses


def _average_hold_minutes(trades: list[ActivityFirstTrade]) -> float | None:
    if not trades:
        return None
    # Timestamps are 1m candles; exact parsing is intentionally avoided in this lightweight report.
    return None


def _evaluate_training_candidates(
    candidates: list[ActivityFirstCandidate],
    candles: list[Candle],
) -> list[_TrainingEvaluation]:
    evaluations: list[_TrainingEvaluation] = []
    for candidate in candidates:
        result = _run_candidate_on_candles(candles, candidate)
        rejection = _candidate_rejection(result)
        activity = _activity_class(result.trades_per_day)
        target_distance = abs(TARGET_QUOTE_PER_DAY - result.quote_per_day)
        balanced_score = (
            result.quote_per_day
            + min(result.trades_per_day, 6.0) * 0.05
            - result.max_drawdown * 0.01
            - target_distance * 0.05
        )
        evaluations.append(
            _TrainingEvaluation(
                candidate=candidate,
                result=result,
                activity_class=activity,
                trade_allowed=rejection is None,
                rejection_reason=rejection,
                balanced_score=balanced_score,
                target_distance=target_distance,
            )
        )
    return evaluations


def _rejection_counts(evaluations: list[_TrainingEvaluation]) -> dict[str, int]:
    counts = {
        "rejected_by_precheck": 0,
        "rejected_by_activity": 0,
        "rejected_by_target_math": 0,
        "rejected_by_training_net": 0,
        "rejected_by_fees": 0,
        "rejected_by_profit_factor": 0,
        "rejected_by_robustness": 0,
        "rejected_by_drawdown": 0,
        "rejected_by_deduplication": 0,
        "rejected_by_context_filter": 0,
        "rejected_by_overactivity": 0,
        "rejected_by_other": 0,
    }
    for evaluation in evaluations:
        if evaluation.rejection_reason is None:
            continue
        key = evaluation.rejection_reason
        counts[key if key in counts else "rejected_by_other"] += 1
    return counts


def _candidate_space_status(evaluations: list[_TrainingEvaluation]) -> tuple[str, str]:
    if not evaluations:
        return "activity_search_failed", "no activity-first candidates were generated"
    if any(item.trade_allowed for item in evaluations):
        return "trade_allowed_found", "at least one active after-fee positive setup exists"
    if any(item.result.trades_per_day >= 1.0 for item in evaluations):
        return "edge_after_fees_failed", "active candidates exist, but none survived edge/fee checks"
    if any(item.result.trade_count > 0 for item in evaluations):
        return "target_activity_missing", "signals exist, but activity is below 1 trade per day"
    return "no_active_candidates", "no candidate produced training trades"


def build_activity_first_router_report(
    run_id: str,
    split: TrainBlindSplit,
    stake_quote_amount: float = 100.0,
    profile: str = "normal",
) -> ActivityFirstRouterReport:
    """Build an activity-first training/blindtest report using every split candle."""
    if split.symbol != CONFIG.symbol:
        msg = f"symbol must be {CONFIG.symbol}"
        raise ValueError(msg)
    candidates = _generate_activity_first_candidates(stake_quote_amount, profile)
    evaluations = _evaluate_training_candidates(candidates, split.training_candles)
    allowed = [item for item in evaluations if item.trade_allowed]
    best_activity = max(evaluations, key=lambda item: item.result.trades_per_day, default=None)
    best_edge = max(evaluations, key=lambda item: item.result.quote_per_day, default=None)
    best_balanced = max(evaluations, key=lambda item: item.balanced_score, default=None)
    fee_survivors = [item for item in evaluations if item.result.total_net_pnl > 0]
    best_fee_survivor = max(fee_survivors, key=lambda item: item.result.quote_per_day, default=None)
    best_target = min(evaluations, key=lambda item: item.target_distance, default=None)
    selected = max(
        allowed,
        key=lambda item: item.balanced_score,
        default=best_balanced,
    )
    if selected is None:
        fallback_candidate = ActivityFirstCandidate(
            candidate_id="no_candidate_available",
            family="activity_first_router",
            lookback_candles=5,
            entry_threshold_pct=0.001,
            take_profit_pct=0.004,
            stop_loss_pct=0.003,
            max_hold_candles=60,
            cooldown_candles=1,
            stake_quote_amount=stake_quote_amount,
        )
        selected_result = _run_candidate_on_candles(split.blindtest_candles, fallback_candidate)
        selected_setups: list[dict[str, Any]] = []
    else:
        selected_result = _run_candidate_on_candles(split.blindtest_candles, selected.candidate)
        selected_setups = [_candidate_summary(selected)]
    daily = _daily_pnls(selected_result.trades)
    status, reason = _candidate_space_status(evaluations)
    best_training_quote_per_day = max(
        (item.result.quote_per_day for item in evaluations),
        default=0.0,
    )
    target_ratio = selected_result.quote_per_day / TARGET_QUOTE_PER_DAY
    target_status = (
        "blindtest_target_reached"
        if selected_result.quote_per_day >= TARGET_QUOTE_PER_DAY
        else "target_not_reached"
    )
    rejection_summary = {
        "router_name": "activity_first_router",
        "candidate_space_status": status,
        "candidate_space_reason": reason,
        "rejection_counts": _rejection_counts(evaluations),
        "best_activity_candidate": _candidate_summary(best_activity) if best_activity else None,
        "best_edge_candidate": _candidate_summary(best_edge) if best_edge else None,
        "best_balanced_candidate": _candidate_summary(best_balanced) if best_balanced else None,
        "best_fee_survivor_candidate": (
            _candidate_summary(best_fee_survivor) if best_fee_survivor else None
        ),
        "best_target_candidate": _candidate_summary(best_target) if best_target else None,
        "target_feasibility_status": target_status,
        "best_training_quote_per_day": best_training_quote_per_day,
    }
    return ActivityFirstRouterReport(
        run_id=run_id,
        router_name="activity_first_router",
        symbol=CONFIG.symbol,
        quote_asset=CONFIG.quote_asset,
        start_capital_reference=100.0,
        stake_quote_amount=stake_quote_amount,
        profile=profile,
        training_start=split.training_start,
        training_end=split.training_end,
        blindtest_start=split.blindtest_start,
        blindtest_end=split.blindtest_end,
        candidate_space_status=status,
        candidate_space_reason=reason,
        candidate_count=len(candidates),
        setup_test_count=len(evaluations),
        trade_allowed_setup_count=len(allowed),
        selected_candidate_count=1 if selected is not None else 0,
        rejected_candidate_count=sum(1 for item in evaluations if item.rejection_reason),
        selected_setups=selected_setups,
        rejection_summary=rejection_summary,
        best_activity_candidate=_candidate_summary(best_activity) if best_activity else None,
        best_edge_candidate=_candidate_summary(best_edge) if best_edge else None,
        best_balanced_candidate=_candidate_summary(best_balanced) if best_balanced else None,
        best_fee_survivor_candidate=_candidate_summary(best_fee_survivor)
        if best_fee_survivor
        else None,
        best_target_candidate=_candidate_summary(best_target) if best_target else None,
        blindtest_final_capital_reference=selected_result.final_capital_reference,
        blindtest_total_gross_pnl=selected_result.total_gross_pnl,
        blindtest_fees=selected_result.total_fees,
        blindtest_total_net_pnl=selected_result.total_net_pnl,
        blindtest_total_net_pnl_pct=selected_result.total_net_pnl,
        blindtest_quote_per_day=selected_result.quote_per_day,
        blindtest_trade_count=selected_result.trade_count,
        blindtest_winning_trades=selected_result.winning_trades,
        blindtest_losing_trades=selected_result.losing_trades,
        blindtest_neutral_trades=selected_result.neutral_trades,
        blindtest_max_drawdown=selected_result.max_drawdown,
        positive_days=sum(1 for value in daily.values() if value > 0),
        negative_days=sum(1 for value in daily.values() if value < 0),
        neutral_days=sum(1 for value in daily.values() if value == 0),
        best_day_pnl=max(daily.values(), default=0.0),
        worst_day_pnl=min(daily.values(), default=0.0),
        best_training_quote_per_day=best_training_quote_per_day,
        target_quote_per_day=TARGET_QUOTE_PER_DAY,
        target_ratio_to_3_usdc_day=target_ratio,
        target_feasibility_status=target_status,
        router_artifact={
            "run_type": "unknown",
            "smoke_test_not_performance_proof": False,
            "live_release_allowed": False,
            "legacy_cluster_router_used": False,
        },
        blindtest_trades=[_trade_to_dict(trade) for trade in selected_result.trades[:250]],
    )


def save_activity_first_router_report(report: ActivityFirstRouterReport) -> Path:
    """Save activity-first router report as JSON."""
    report_dir = ensure_run_report_dir(report.run_id)
    path = report_dir / ACTIVITY_FIRST_ROUTER_REPORT_FILENAME
    content = json.dumps(asdict(report), indent=2, sort_keys=True)
    path.write_text(f"{content}\n", encoding="utf-8")
    return path


def load_activity_first_router_report(run_id: str) -> ActivityFirstRouterReport:
    """Load an activity-first router report."""
    raw: dict[str, Any] = json.loads(
        _get_activity_first_router_report_path(run_id).read_text(encoding="utf-8")
    )
    return ActivityFirstRouterReport(**raw)
