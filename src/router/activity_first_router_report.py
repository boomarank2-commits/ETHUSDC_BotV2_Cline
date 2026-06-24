import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.common.config import CONFIG
from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.data.candle_schema import Candle
from src.data.exchange_info import ExchangeInfoFilters, load_exchange_info_filters, round_price_to_tick, round_quantity_to_step
from src.data.train_blind_split import TrainBlindSplit

ACTIVITY_FIRST_ROUTER_REPORT_FILENAME = "activity_first_router_report.json"
TARGET_QUOTE_PER_DAY = 3.0
FEE_BPS = 10.0
MIN_PROFIT_FACTOR = 1.03
MAX_FEE_TO_GROSS_RATIO = 0.70
MAX_DRAWDOWN_PCT = 25.0


@dataclass(frozen=True)
class ActivityFirstCandidate:
    candidate_id: str
    family: str
    lookback_candles: int
    entry_threshold_pct: float
    take_profit_pct: float
    stop_loss_pct: float
    max_hold_candles: int
    cooldown_candles: int
    stake_quote_amount: float
    search_pass: str = "activity_first"


@dataclass(frozen=True)
class ActivityFirstTrade:
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
    hold_minutes: int = 0


@dataclass(frozen=True)
class ActivityFirstSimulationResult:
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
    blocked_signal_count: int
    trades: list[ActivityFirstTrade]


@dataclass(frozen=True)
class ActivityFirstRouterReport:
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


def _profit_factor(trades: list[ActivityFirstTrade]) -> float | None:
    wins = sum(t.net_pnl for t in trades if t.net_pnl > 0)
    losses = abs(sum(t.net_pnl for t in trades if t.net_pnl < 0))
    if losses == 0:
        return None if wins == 0 else 999.0
    return wins / losses


def _fee_to_gross_ratio(result: ActivityFirstSimulationResult) -> float | None:
    if abs(result.total_gross_pnl) < 0.000001:
        return None
    return result.total_fees / abs(result.total_gross_pnl)


def _candidate_rejection(result: ActivityFirstSimulationResult) -> str | None:
    if result.trade_count == 0 or result.trades_per_day < 1.0:
        return "rejected_by_activity"
    if result.trades_per_day > 10.0:
        return "rejected_by_overactivity"
    if result.total_net_pnl <= 0:
        if result.total_gross_pnl > 0 and result.total_fees >= result.total_gross_pnl:
            return "rejected_by_fees"
        return "rejected_by_training_net"
    ratio = _fee_to_gross_ratio(result)
    if ratio is not None and ratio > MAX_FEE_TO_GROSS_RATIO:
        return "rejected_by_fees"
    profit_factor = _profit_factor(result.trades)
    if profit_factor is not None and profit_factor < MIN_PROFIT_FACTOR:
        return "rejected_by_profit_factor"
    if result.max_drawdown > MAX_DRAWDOWN_PCT:
        return "rejected_by_drawdown"
    return None


def _add_candidates(candidates, families, lookbacks, setups, stake, search_pass, cooldown_divisor):
    seen = {c.candidate_id for c in candidates}
    for family in families:
        for lookback in lookbacks:
            for threshold, tp, sl, hold in setups:
                cid = f"{search_pass}_{family}_lb{lookback}_th{threshold}_tp{tp}_sl{sl}_hold{hold}"
                if cid in seen:
                    continue
                seen.add(cid)
                candidates.append(
                    ActivityFirstCandidate(
                        cid,
                        family,
                        lookback,
                        threshold,
                        tp,
                        sl,
                        hold,
                        max(1, lookback // cooldown_divisor),
                        stake,
                        search_pass,
                    )
                )


def _generate_activity_first_candidates(stake_quote_amount: float, profile: str) -> list[ActivityFirstCandidate]:
    families = (
        "momentum_entry",
        "pullback_entry",
        "range_breakout_entry",
        "volatility_expansion_entry",
        "mean_reversion_entry",
        "trend_continuation_entry",
    )
    candidates: list[ActivityFirstCandidate] = []
    if profile == "conservative":
        activity_lookbacks = (10, 20, 30, 60, 120)
        activity_setups = ((0.0015, 0.004, 0.003, 60), (0.0025, 0.006, 0.004, 120), (0.0035, 0.010, 0.006, 240))
        edge_lookbacks = (30, 60, 120, 240)
        edge_setups = ((0.004, 0.0125, 0.0075, 360), (0.006, 0.018, 0.010, 600))
    elif profile == "aggressive":
        activity_lookbacks = (5, 10, 15, 30, 60, 90, 120)
        activity_setups = ((0.0005, 0.003, 0.003, 30), (0.0010, 0.004, 0.003, 60), (0.0015, 0.006, 0.004, 120), (0.0025, 0.008, 0.006, 180))
        edge_lookbacks = (10, 20, 30, 60, 120, 240)
        edge_setups = ((0.0025, 0.010, 0.006, 240), (0.0035, 0.0125, 0.0075, 360), (0.0050, 0.016, 0.010, 480), (0.0075, 0.022, 0.012, 720))
    else:
        activity_lookbacks = (5, 10, 15, 30, 60)
        activity_setups = ((0.00075, 0.0035, 0.003, 45), (0.00125, 0.0050, 0.004, 90), (0.00200, 0.0075, 0.005, 150))
        edge_lookbacks = (10, 20, 30, 60, 120, 240)
        edge_setups = ((0.0025, 0.010, 0.006, 240), (0.0035, 0.0125, 0.0075, 360), (0.0050, 0.015, 0.010, 480), (0.0075, 0.020, 0.012, 720))
    _add_candidates(candidates, families, activity_lookbacks, activity_setups, stake_quote_amount, "activity_first", 5)
    edge_families = ("momentum_entry", "pullback_entry", "range_breakout_entry", "mean_reversion_entry", "trend_continuation_entry")
    _add_candidates(candidates, edge_families, edge_lookbacks, edge_setups, stake_quote_amount, "edge_expansion", 4)
    fee_families = ("pullback_entry", "range_breakout_entry", "mean_reversion_entry", "trend_continuation_entry")
    fee_setups = ((0.004, 0.018, 0.008, 720), (0.006, 0.024, 0.010, 900))
    _add_candidates(candidates, fee_families, (30, 60, 120, 240), fee_setups, stake_quote_amount, "fee_rescue", 3)

    eth_families = (
        "eth_us_impulse_entry",
        "eth_liquidity_sweep_reclaim_entry",
        "eth_range_compression_breakout_entry",
        "eth_bounce_after_flush_entry",
        "eth_continuation_after_impulse_entry",
        "eth_opening_range_reclaim_entry",
    )
    eth_setups = (
        (0.0015, 0.006, 0.004, 90),
        (0.0025, 0.010, 0.006, 180),
        (0.0035, 0.014, 0.008, 360),
        (0.0050, 0.020, 0.010, 720),
        (0.0075, 0.030, 0.014, 1080),
    )
    _add_candidates(candidates, eth_families, (15, 30, 60, 120, 240), eth_setups, stake_quote_amount, "eth_regime_discovery", 3)
    return candidates


def _utc_hour(open_time: str) -> int | None:
    try:
        return int(open_time[11:13])
    except (TypeError, ValueError):
        return None


def _session_label(open_time: str) -> str:
    hour = _utc_hour(open_time)
    if hour is None:
        return "unknown"
    if 12 <= hour <= 15:
        return "us_macro_open_window"
    if 16 <= hour <= 21:
        return "us_session_window"
    if 7 <= hour <= 11:
        return "europe_session_window"
    if 0 <= hour <= 6:
        return "asia_session_window"
    return "late_us_afterhours_window"


def _eth_context(candles: list[Candle], index: int, lookback: int) -> dict[str, Any]:
    current = candles[index]
    prior = candles[index - 1]
    window = candles[index - lookback : index]
    closes = [c.close for c in window]
    volumes = [c.volume for c in window]
    recent_high = max(c.high for c in window)
    recent_low = min(c.low for c in window)
    avg_volume = sum(volumes) / len(volumes) if volumes else 0.0
    avg_range = sum((c.high - c.low) / c.close for c in window if c.close > 0) / len(window)
    current_range = (current.high - current.low) / current.close if current.close > 0 else 0.0
    close_pos = 0.5 if current.high == current.low else (current.close - current.low) / (current.high - current.low)
    return {
        "session": _session_label(current.open_time),
        "close_pos": close_pos,
        "volume_ratio": current.volume / avg_volume if avg_volume > 0 else 1.0,
        "range_ratio": current_range / avg_range if avg_range > 0 else 1.0,
        "lookback_return": (current.close / candles[index - lookback].close - 1.0) if candles[index - lookback].close > 0 else 0.0,
        "short_return": (current.close / candles[index - max(2, lookback // 3)].close - 1.0) if candles[index - max(2, lookback // 3)].close > 0 else 0.0,
        "recent_high": recent_high,
        "recent_low": recent_low,
        "prior_close": prior.close,
    }


def _entry_signal(candles: list[Candle], index: int, candidate: ActivityFirstCandidate) -> bool:
    current = candles[index]
    prior = candles[index - 1]
    lookback = candidate.lookback_candles
    previous = candles[index - lookback]
    threshold = candidate.entry_threshold_pct
    window = candles[index - lookback : index]
    closes = [c.close for c in window]
    recent_high = max(c.high for c in window)
    recent_low = min(c.low for c in window)
    recent_range = (recent_high - recent_low) / current.close
    mean_close = sum(closes) / len(closes)
    short_index = index - max(2, lookback // 2)
    context = _eth_context(candles, index, lookback)

    if candidate.family == "momentum_entry":
        return current.close > previous.close * (1 + threshold) and current.close > prior.close
    if candidate.family == "pullback_entry":
        trend_ok = mean_close > previous.close * (1 + threshold / 2)
        pullback_seen = prior.close < max(closes) * (1 - threshold)
        rebound_ok = current.close > prior.close * (1 + threshold / 3)
        return trend_ok and pullback_seen and rebound_ok
    if candidate.family == "range_breakout_entry":
        return current.close > recent_high * (1 + threshold / 2)
    if candidate.family == "volatility_expansion_entry":
        return recent_range > threshold * 3 and current.close > prior.close * (1 + threshold / 2)
    if candidate.family == "mean_reversion_entry":
        near_low = prior.close <= recent_low * (1 + threshold * 2)
        reclaim = current.close > prior.close * (1 + threshold / 2)
        return near_low and reclaim and current.close <= mean_close * (1 + threshold)
    if candidate.family == "trend_continuation_entry":
        short_trend = current.close > candles[short_index].close * (1 + threshold / 3)
        long_trend = current.close > previous.close * (1 + threshold)
        return short_trend and long_trend and current.close > prior.close

    is_us_window = context["session"] in {"us_macro_open_window", "us_session_window"}
    volume_spike = context["volume_ratio"] >= 1.25
    range_spike = context["range_ratio"] >= 1.20
    close_strong = context["close_pos"] >= 0.65
    close_reclaim = current.close > prior.close * (1 + threshold / 3)
    compression = recent_range <= max(0.0035, threshold * 2.5)
    prior_flush = previous.close > 0 and (prior.close / previous.close - 1.0) <= -threshold * 2.0

    if candidate.family == "eth_us_impulse_entry":
        return is_us_window and volume_spike and range_spike and close_strong and current.close > prior.close * (1 + threshold / 2)
    if candidate.family == "eth_liquidity_sweep_reclaim_entry":
        swept_low = current.low < recent_low * (1 - threshold / 3)
        reclaimed = current.close > recent_low * (1 + threshold / 2) and close_strong
        return swept_low and reclaimed and volume_spike
    if candidate.family == "eth_range_compression_breakout_entry":
        return compression and current.close > recent_high * (1 + threshold / 3) and volume_spike and close_strong
    if candidate.family == "eth_bounce_after_flush_entry":
        return prior_flush and close_reclaim and close_strong and context["range_ratio"] >= 1.0
    if candidate.family == "eth_continuation_after_impulse_entry":
        impulse = context["lookback_return"] >= threshold * 2.0
        shallow_pullback = prior.close >= mean_close * (1 - threshold)
        return impulse and shallow_pullback and close_reclaim and close_strong
    if candidate.family == "eth_opening_range_reclaim_entry":
        return is_us_window and current.close > mean_close * (1 + threshold / 2) and close_reclaim and volume_spike
    raise ValueError(f"unsupported activity-first family: {candidate.family}")


def _exit_trade(candles: list[Candle], entry_index: int, candidate: ActivityFirstCandidate, filters: ExchangeInfoFilters | None) -> tuple[int, str, float]:
    entry_price = candles[entry_index].close
    tick = filters.price_tick_size if filters else None
    take_profit_price = round_price_to_tick(entry_price * (1 + candidate.take_profit_pct), tick)
    stop_loss_price = round_price_to_tick(entry_price * (1 - candidate.stop_loss_pct), tick)
    max_exit_index = min(entry_index + candidate.max_hold_candles, len(candles) - 1)
    for exit_index in range(entry_index + 1, max_exit_index + 1):
        candle = candles[exit_index]
        if candle.low <= stop_loss_price:
            return exit_index, "stop_loss", stop_loss_price
        if candle.high >= take_profit_price:
            return exit_index, "take_profit", take_profit_price
    return max_exit_index, "max_hold", candles[max_exit_index].close


def _quantity_for_entry(candidate: ActivityFirstCandidate, entry_price: float, filters: ExchangeInfoFilters | None) -> float | None:
    quantity = candidate.stake_quote_amount / entry_price
    if filters is not None:
        quantity = round_quantity_to_step(quantity, filters.lot_step_size)
        if filters.lot_min_qty is not None and quantity < filters.lot_min_qty:
            return None
        if filters.min_notional is not None and quantity * entry_price < filters.min_notional:
            return None
    return quantity if quantity > 0 else None


def _run_candidate_on_candles(candles: list[Candle], candidate: ActivityFirstCandidate, start_capital_reference: float, filters: ExchangeInfoFilters | None) -> ActivityFirstSimulationResult:
    trades: list[ActivityFirstTrade] = []
    signal_count = no_trade_count = blocked_signal_count = 0
    cumulative_net = cumulative_gross = cumulative_fees = 0.0
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
        tick = filters.price_tick_size if filters else None
        entry_price = round_price_to_tick(entry.close, tick)
        quantity = _quantity_for_entry(candidate, entry_price, filters)
        if quantity is None:
            blocked_signal_count += 1
            index += 1
            continue
        exit_index, exit_reason, exit_price = _exit_trade(candles, index, candidate, filters)
        gross_pnl = quantity * (exit_price - entry_price)
        fees_paid = quantity * entry_price * fee_rate + quantity * exit_price * fee_rate
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
                entry.open_time,
                candles[exit_index].open_time,
                entry_price,
                exit_price,
                candidate.stake_quote_amount,
                quantity,
                gross_pnl,
                fees_paid,
                net_pnl,
                net_pnl / candidate.stake_quote_amount * 100,
                exit_reason,
                candidate.family,
                candidate.candidate_id,
                exit_index - index,
            )
        )
        index = exit_index + 1 + candidate.cooldown_candles
    days = max(1.0, len(candles) / 1440)
    return ActivityFirstSimulationResult(
        candidate,
        start_capital_reference,
        start_capital_reference + cumulative_net,
        cumulative_gross,
        cumulative_fees,
        cumulative_net,
        cumulative_net / days,
        len(trades),
        len(trades) / days,
        sum(1 for t in trades if t.net_pnl > 0),
        sum(1 for t in trades if t.net_pnl < 0),
        sum(1 for t in trades if t.net_pnl == 0),
        max_drawdown,
        signal_count,
        no_trade_count,
        blocked_signal_count,
        trades,
    )


def _empty_simulation_result(candidate: ActivityFirstCandidate, start_capital_reference: float) -> ActivityFirstSimulationResult:
    return ActivityFirstSimulationResult(candidate, start_capital_reference, start_capital_reference, 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0, 0, 0, 0.0, 0, 0, 0, [])


def _daily_pnls(trades: list[ActivityFirstTrade]) -> dict[str, float]:
    daily: dict[str, float] = {}
    for trade in trades:
        day = trade.exit_time[:10]
        daily[day] = daily.get(day, 0.0) + trade.net_pnl
    return daily


def _forward_return(candles: list[Candle], index: int, minutes: int) -> float | None:
    target = index + minutes
    if target >= len(candles) or candles[index].close <= 0:
        return None
    return candles[target].close / candles[index].close - 1.0


def _trigger_diagnostics(candles: list[Candle], trigger_name: str, lookback: int = 60) -> dict[str, Any]:
    returns_60: list[float] = []
    returns_240: list[float] = []
    session_counts: dict[str, int] = {}
    max_index = len(candles) - 241
    for index in range(max(lookback, 2), max_index):
        candidate = ActivityFirstCandidate("diagnostic", trigger_name, lookback, 0.0025, 0.0, 0.0, 0, 0, 100.0, "diagnostic")
        if not _entry_signal(candles, index, candidate):
            continue
        session = _session_label(candles[index].open_time)
        session_counts[session] = session_counts.get(session, 0) + 1
        r60 = _forward_return(candles, index, 60)
        r240 = _forward_return(candles, index, 240)
        if r60 is not None:
            returns_60.append(r60)
        if r240 is not None:
            returns_240.append(r240)
    def _summary(values: list[float]) -> dict[str, float | int | None]:
        if not values:
            return {"count": 0, "avg_return_pct": None, "best_return_pct": None, "worst_return_pct": None, "positive_rate": None}
        return {
            "count": len(values),
            "avg_return_pct": sum(values) / len(values) * 100,
            "best_return_pct": max(values) * 100,
            "worst_return_pct": min(values) * 100,
            "positive_rate": sum(1 for value in values if value > 0) / len(values),
        }
    return {
        "trigger_name": trigger_name,
        "sample_count": len(returns_60),
        "session_counts": session_counts,
        "forward_60m": _summary(returns_60),
        "forward_240m": _summary(returns_240),
    }


def _eth_regime_diagnostics(candles: list[Candle]) -> dict[str, Any]:
    session_counts: dict[str, int] = {}
    range_spike_count = 0
    volume_spike_count = 0
    for index in range(60, len(candles)):
        context = _eth_context(candles, index, 60)
        session = str(context["session"])
        session_counts[session] = session_counts.get(session, 0) + 1
        if context["range_ratio"] >= 1.5:
            range_spike_count += 1
        if context["volume_ratio"] >= 1.5:
            volume_spike_count += 1
    trigger_names = (
        "eth_us_impulse_entry",
        "eth_liquidity_sweep_reclaim_entry",
        "eth_range_compression_breakout_entry",
        "eth_bounce_after_flush_entry",
        "eth_continuation_after_impulse_entry",
        "eth_opening_range_reclaim_entry",
    )
    return {
        "scope": "ETHUSDC-only training diagnostics",
        "purpose": "find repeated ETH-specific market signatures before allowing any strategy mix",
        "session_counts": session_counts,
        "range_spike_minutes": range_spike_count,
        "volume_spike_minutes": volume_spike_count,
        "trigger_forward_return_diagnostics": [_trigger_diagnostics(candles, name) for name in trigger_names],
        "missing_live_context": ["historical orderbook depth", "historical bookTicker spread", "news/economic-calendar labels"],
        "interpretation_rule": "These diagnostics may guide candidate generation, but they do not by themselves allow live trading or blindtest execution.",
    }


def _candidate_summary(evaluation: _TrainingEvaluation) -> dict[str, Any]:
    r = evaluation.result
    c = evaluation.candidate
    avg_trade = r.total_net_pnl / r.trade_count if r.trade_count else None
    return {
        "candidate_id": c.candidate_id,
        "strategy_family": c.family,
        "search_pass": c.search_pass,
        "activity_class": evaluation.activity_class,
        "trades_per_day": r.trades_per_day,
        "active_days": len(_daily_pnls(r.trades)),
        "training_trade_count": r.trade_count,
        "training_signal_count": r.signal_count,
        "training_blocked_signal_count": r.blocked_signal_count,
        "training_gross_pnl": r.total_gross_pnl,
        "training_fees": r.total_fees,
        "training_net_pnl": r.total_net_pnl,
        "training_quote_per_day": r.quote_per_day,
        "training_average_trade_pnl": avg_trade,
        "training_fee_to_gross_ratio": _fee_to_gross_ratio(r),
        "training_win_rate": r.winning_trades / r.trade_count if r.trade_count else None,
        "training_profit_factor": _profit_factor(r.trades),
        "max_drawdown": r.max_drawdown,
        "average_hold_minutes": sum(t.hold_minutes for t in r.trades) / r.trade_count if r.trade_count else None,
        "tp": c.take_profit_pct,
        "sl": c.stop_loss_pct,
        "max_hold": c.max_hold_candles,
        "trailing_stop": None,
        "context_filters": [c.search_pass] if c.search_pass.startswith("eth_") else [],
        "rejection_reason": evaluation.rejection_reason,
        "distance_to_target": evaluation.target_distance,
        "balanced_score": evaluation.balanced_score,
    }


def _evaluate_training_candidates(candidates: list[ActivityFirstCandidate], candles: list[Candle], start_capital_reference: float, filters: ExchangeInfoFilters | None) -> list[_TrainingEvaluation]:
    evaluations: list[_TrainingEvaluation] = []
    for candidate in candidates:
        result = _run_candidate_on_candles(candles, candidate, start_capital_reference, filters)
        rejection = _candidate_rejection(result)
        activity = _activity_class(result.trades_per_day)
        target_distance = abs(TARGET_QUOTE_PER_DAY - result.quote_per_day)
        pf = _profit_factor(result.trades) or 0.0
        score = result.quote_per_day + min(result.trades_per_day, 6.0) * 0.05 + min(pf, 2.0) * 0.03 - result.max_drawdown * 0.01 - target_distance * 0.03
        evaluations.append(_TrainingEvaluation(candidate, result, activity, rejection is None, rejection, score, target_distance))
    return evaluations


def _rejection_counts(evaluations: list[_TrainingEvaluation]) -> dict[str, int]:
    counts = {"rejected_by_precheck": 0, "rejected_by_activity": 0, "rejected_by_target_math": 0, "rejected_by_training_net": 0, "rejected_by_fees": 0, "rejected_by_profit_factor": 0, "rejected_by_robustness": 0, "rejected_by_drawdown": 0, "rejected_by_deduplication": 0, "rejected_by_context_filter": 0, "rejected_by_overactivity": 0, "rejected_by_other": 0}
    for evaluation in evaluations:
        key = evaluation.rejection_reason
        if key is not None:
            counts[key if key in counts else "rejected_by_other"] += 1
    return counts


def _search_pass_summary(evaluations: list[_TrainingEvaluation]) -> list[dict[str, Any]]:
    result = []
    for search_pass in sorted({e.candidate.search_pass for e in evaluations}):
        rows = [e for e in evaluations if e.candidate.search_pass == search_pass]
        best = max(rows, key=lambda e: e.result.quote_per_day, default=None)
        result.append({"pass_name": search_pass, "candidates_generated": len(rows), "setup_tests_run": len(rows), "candidates_positive_net": sum(1 for e in rows if e.result.total_net_pnl > 0), "candidates_active_enough": sum(1 for e in rows if e.result.trades_per_day >= 1.0), "candidates_trade_allowed": sum(1 for e in rows if e.trade_allowed), "best_candidate": _candidate_summary(best) if best else None})
    return result


def _candidate_space_status(evaluations: list[_TrainingEvaluation]) -> tuple[str, str]:
    if not evaluations:
        return "activity_search_failed", "no activity-first candidates were generated"
    if any(e.trade_allowed for e in evaluations):
        return "trade_allowed_found", "at least one active after-fee positive setup exists"
    if any(e.result.total_net_pnl > 0 for e in evaluations):
        return "trade_allowed_blocked", "positive candidates exist but failed robustness/activity filters"
    if any(e.result.total_gross_pnl > 0 for e in evaluations):
        return "edge_after_fees_failed", "gross-positive candidates exist, but fees removed the edge"
    if any(e.result.trades_per_day >= 1.0 for e in evaluations):
        return "target_edge_missing", "active candidates exist, but no gross edge was found"
    if any(e.result.trade_count > 0 for e in evaluations):
        return "target_activity_missing", "signals exist, but activity is below 1 trade per day"
    return "no_active_candidates", "no candidate produced training trades"


def _diagnostic_placeholder_candidate(stake: float) -> ActivityFirstCandidate:
    return ActivityFirstCandidate("no_trade_allowed_candidate", "activity_first_router", 5, 0.0, 0.0, 0.0, 0, 0, stake, "diagnostic_only")


def build_activity_first_router_report(run_id: str, split: TrainBlindSplit, stake_quote_amount: float = 100.0, profile: str = "normal") -> ActivityFirstRouterReport:
    if split.symbol != CONFIG.symbol:
        raise ValueError(f"symbol must be {CONFIG.symbol}")
    start_capital = float(stake_quote_amount)
    filters = load_exchange_info_filters()
    candidates = _generate_activity_first_candidates(stake_quote_amount, profile)
    evaluations = _evaluate_training_candidates(candidates, split.training_candles, start_capital, filters)
    allowed = [e for e in evaluations if e.trade_allowed]
    best_activity = max(evaluations, key=lambda e: e.result.trades_per_day, default=None)
    best_edge = max(evaluations, key=lambda e: e.result.quote_per_day, default=None)
    best_balanced = max(evaluations, key=lambda e: e.balanced_score, default=None)
    fee_survivors = [e for e in evaluations if e.result.total_net_pnl > 0]
    best_fee_survivor = max(fee_survivors, key=lambda e: e.result.quote_per_day, default=None)
    best_target = min(evaluations, key=lambda e: e.target_distance, default=None)
    selected = max(allowed, key=lambda e: e.balanced_score, default=None)
    status, reason = _candidate_space_status(evaluations)
    if selected is None:
        selected_result = _empty_simulation_result(_diagnostic_placeholder_candidate(stake_quote_amount), start_capital)
        selected_setups = []
        selection_reason = "diagnostic_only_no_trade_allowed_candidate; best candidates are reported but not executed on blindtest as selected strategy"
    else:
        selected_result = _run_candidate_on_candles(split.blindtest_candles, selected.candidate, start_capital, filters)
        selected_setups = [_candidate_summary(selected)]
        selection_reason = "trade_allowed_candidate_executed_on_blindtest"
    daily = _daily_pnls(selected_result.trades)
    best_training_quote_per_day = max((e.result.quote_per_day for e in evaluations), default=0.0)
    target_ratio = selected_result.quote_per_day / TARGET_QUOTE_PER_DAY
    target_status = "blindtest_target_reached" if selected is not None and selected_result.quote_per_day >= TARGET_QUOTE_PER_DAY else "target_not_reached"
    eth_diagnostics = _eth_regime_diagnostics(split.training_candles)
    rejection_summary = {
        "router_name": "activity_first_router",
        "candidate_space_status": status,
        "candidate_space_reason": reason,
        "rejection_counts": _rejection_counts(evaluations),
        "search_pass_summary": _search_pass_summary(evaluations),
        "eth_regime_diagnostics": eth_diagnostics,
        "best_activity_candidate": _candidate_summary(best_activity) if best_activity else None,
        "best_edge_candidate": _candidate_summary(best_edge) if best_edge else None,
        "best_balanced_candidate": _candidate_summary(best_balanced) if best_balanced else None,
        "best_fee_survivor_candidate": _candidate_summary(best_fee_survivor) if best_fee_survivor else None,
        "best_target_candidate": _candidate_summary(best_target) if best_target else None,
        "selected_trade_allowed_candidate": _candidate_summary(selected) if selected else None,
        "target_feasibility_status": target_status,
        "best_training_quote_per_day": best_training_quote_per_day,
        "diagnostic_only": selected is None,
        "selection_reason": selection_reason,
    }
    return ActivityFirstRouterReport(
        run_id,
        "activity_first_router",
        CONFIG.symbol,
        CONFIG.quote_asset,
        start_capital,
        stake_quote_amount,
        profile,
        split.training_start,
        split.training_end,
        split.blindtest_start,
        split.blindtest_end,
        status,
        reason,
        len(candidates),
        len(evaluations),
        len(allowed),
        1 if selected else 0,
        sum(1 for e in evaluations if e.rejection_reason),
        selected_setups,
        rejection_summary,
        _candidate_summary(best_activity) if best_activity else None,
        _candidate_summary(best_edge) if best_edge else None,
        _candidate_summary(best_balanced) if best_balanced else None,
        _candidate_summary(best_fee_survivor) if best_fee_survivor else None,
        _candidate_summary(best_target) if best_target else None,
        selected_result.final_capital_reference,
        selected_result.total_gross_pnl,
        selected_result.total_fees,
        selected_result.total_net_pnl,
        selected_result.total_net_pnl / start_capital * 100 if start_capital else 0.0,
        selected_result.quote_per_day,
        selected_result.trade_count,
        selected_result.winning_trades,
        selected_result.losing_trades,
        selected_result.neutral_trades,
        selected_result.max_drawdown,
        sum(1 for v in daily.values() if v > 0),
        sum(1 for v in daily.values() if v < 0),
        sum(1 for v in daily.values() if v == 0),
        max(daily.values(), default=0.0),
        min(daily.values(), default=0.0),
        best_training_quote_per_day,
        TARGET_QUOTE_PER_DAY,
        target_ratio,
        target_status,
        {
            "run_type": "unknown",
            "smoke_test_not_performance_proof": False,
            "live_release_allowed": False,
            "legacy_cluster_router_used": False,
            "diagnostic_only": selected is None,
            "trade_allowed": selected is not None,
            "blindtest_strategy_executed": selected is not None,
            "selection_policy": "only_trade_allowed_candidates_may_run_blindtest",
            "selection_reason": selection_reason,
            "exchange_info_filters_used": filters is not None,
            "candidate_generation_version": "activity_first_v3_eth_regime_discovery",
            "eth_specific_strategy_scope": True,
            "historical_news_labels_used": False,
            "historical_orderbook_used": False,
        },
        [asdict(t) for t in selected_result.trades[:250]],
    )


def save_activity_first_router_report(report: ActivityFirstRouterReport) -> Path:
    report_dir = ensure_run_report_dir(report.run_id)
    path = report_dir / ACTIVITY_FIRST_ROUTER_REPORT_FILENAME
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_activity_first_router_report(run_id: str) -> ActivityFirstRouterReport:
    raw: dict[str, Any] = json.loads(_get_activity_first_router_report_path(run_id).read_text(encoding="utf-8"))
    return ActivityFirstRouterReport(**raw)
