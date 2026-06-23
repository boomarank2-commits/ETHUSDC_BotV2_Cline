"""Strategy V1 fixed-stake LONG-only Spot backtest engine."""

from dataclasses import dataclass
from typing import Callable

from src.data.candle_schema import Candle
from src.data.exchange_info import load_exchange_info_filters, round_price_to_tick, round_quantity_to_step


@dataclass(frozen=True)
class StrategyV1Candidate:
    """Fixed Strategy V1 candidate without Short/Futures/Margin/Leverage."""

    family: str
    name: str
    lookback_candles: int
    secondary_lookback_candles: int | None
    entry_threshold_pct: float
    take_profit_pct: float
    stop_loss_pct: float
    max_hold_candles: int
    cooldown_candles: int
    fee_bps: float
    stake_quote_amount: float
    profile_set: str = "normal"
    use_context_filter: bool = False
    trailing_stop_pct: float | None = None

    def __post_init__(self) -> None:
        if not self.family or not self.name:
            msg = "family and name must not be empty"
            raise ValueError(msg)
        values = [
            self.lookback_candles,
            self.entry_threshold_pct,
            self.take_profit_pct,
            self.stop_loss_pct,
            self.max_hold_candles,
            self.fee_bps,
            self.stake_quote_amount,
        ]
        if self.secondary_lookback_candles is not None:
            values.append(self.secondary_lookback_candles)
        if self.trailing_stop_pct is not None:
            values.append(self.trailing_stop_pct)
        if self.cooldown_candles < 0 or any(value <= 0 for value in values):
            msg = "candidate values must be positive; cooldown may be zero"
            raise ValueError(msg)


@dataclass(frozen=True)
class StrategyV1Trade:
    """One completed fixed-stake LONG-only Spot trade."""

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
    candidate_name: str


@dataclass(frozen=True)
class StrategyV1Result:
    """Result of one fixed Strategy V1 candidate."""

    candidate: StrategyV1Candidate
    start_capital_reference: float
    stake_quote_amount: float
    final_capital_reference: float
    total_net_pnl: float
    total_net_pnl_pct: float
    quote_per_day: float
    trade_count: int
    winning_trades: int
    losing_trades: int
    neutral_trades: int
    max_drawdown: float
    trades: list[StrategyV1Trade]
    signal_count: int = 0
    no_trade_count: int = 0
    blocked_signal_count: int = 0


@dataclass(frozen=True)
class StrategyV1CandidateEvaluation:
    """Transparent training evaluation for one Strategy V1 candidate."""

    candidate: StrategyV1Candidate
    train_trade_count: int
    train_gross_pnl: float
    train_fees: float
    train_net_pnl: float
    train_pnl_per_day: float
    train_trades_per_month: float
    raw_score: float
    low_activity_penalty: float
    adjusted_score: float
    low_activity_penalty_applied: bool
    train_win_rate: float | None
    score: float
    selected: bool
    reason: str
    training_positive_months: int = 0
    training_negative_months: int = 0
    training_active_months: int = 0
    training_total_months: int = 24
    training_max_drawdown: float = 0.0
    training_best_trade_pnl: float = 0.0
    training_worst_trade_pnl: float = 0.0
    training_top_trade_profit_share: float = 0.0
    training_profit_concentration_warning: bool = False
    stability_penalty: float = 0.0
    drawdown_penalty: float = 0.0
    concentration_penalty: float = 0.0
    adjusted_score_final: float = 0.0
    stability_diagnosis: str = "not available"


TRAINING_DAYS_FOR_ACTIVITY = 730
TRAINING_MONTHS_FOR_ACTIVITY = TRAINING_DAYS_FOR_ACTIVITY / 30.4375
ROBUST_TRADE_FLOOR = 24
LOW_ACTIVITY_PENALTY_PER_MISSING_TRADE = 0.08
LOW_ACTIVITY_EXCLUSION_PENALTY = 2.0
TRAINING_TOTAL_MONTHS = 24
MIN_ACTIVE_TRAINING_MONTHS = 6
INACTIVE_TRAINING_MONTH_PENALTY = 0.05
NEGATIVE_MONTH_DOMINANCE_PENALTY = 0.50
PROFIT_CONCENTRATION_WARNING_SHARE = 0.50
MAX_TRAINING_DRAWDOWN_WITHOUT_PENALTY = 5.0
MIN_ROBUST_FINAL_TRAINING_SCORE = 0.0


def default_strategy_v1_candidates(profile: str = "normal") -> list[StrategyV1Candidate]:
    """Return fixed V1 candidates across four simple LONG-only families."""
    families = ("momentum_breakout", "mean_reversion_bounce", "trend_pullback", "range_breakout")
    if profile == "conservative":
        lookbacks = (30, 45, 60, 90, 120, 240, 360)
        profiles = ((0.006, 0.010, 0.006, None, 180), (0.008, 0.014, 0.007, None, 240), (0.010, 0.018, 0.010, 0.008, 360), (0.012, 0.020, 0.010, None, 480))
        context_flags = (True,)
    elif profile == "aggressive":
        lookbacks = (8, 10, 15, 20, 30, 45, 60, 90, 120, 240, 360)
        profiles = ((0.0025, 0.006, 0.005, None, 90), (0.004, 0.008, 0.006, None, 120), (0.006, 0.010, 0.007, None, 180), (0.0075, 0.012, 0.009, None, 240), (0.010, 0.015, 0.010, None, 360), (0.010, 0.020, 0.010, 0.008, 480), (0.012, 0.025, 0.012, 0.010, 720))
        context_flags = (False, True)
    else:
        lookbacks = (10, 15, 20, 30, 45, 60, 90, 120, 240, 360)
        profiles = ((0.004, 0.008, 0.006, None, 120), (0.006, 0.010, 0.007, None, 180), (0.0075, 0.012, 0.009, None, 240), (0.010, 0.015, 0.010, None, 360), (0.010, 0.020, 0.010, 0.008, 480), (0.012, 0.020, 0.010, None, 480), (0.012, 0.025, 0.012, 0.010, 720))
        context_flags = (False, True)
    candidates: list[StrategyV1Candidate] = []
    seen_names: set[str] = set()
    for family in families:
        for lookback in lookbacks:
            for threshold, take_profit, stop_loss, trailing_stop, max_hold in profiles:
                for use_context in context_flags:
                    secondary = lookback * 3 if family == "trend_pullback" else None
                    context_suffix = "_ctx" if use_context else ""
                    trail_suffix = f"_trail{trailing_stop}" if trailing_stop is not None else ""
                    cooldown = max(1, lookback // (8 if profile == "aggressive" else 10))
                    if profile == "conservative":
                        cooldown = max(cooldown, lookback // 6)
                    candidate_name = f"{family}_lb{lookback}_th{threshold}_tp{take_profit}{trail_suffix}{context_suffix}"
                    if candidate_name in seen_names:
                        continue
                    seen_names.add(candidate_name)
                    candidates.append(
                        StrategyV1Candidate(
                            family=family,
                            name=candidate_name,
                            lookback_candles=lookback,
                            secondary_lookback_candles=secondary,
                            entry_threshold_pct=threshold,
                            take_profit_pct=take_profit,
                            stop_loss_pct=stop_loss,
                            trailing_stop_pct=trailing_stop,
                            max_hold_candles=max_hold,
                            cooldown_candles=cooldown,
                            fee_bps=10.0,
                            stake_quote_amount=100.0,
                            profile_set=profile,
                            use_context_filter=use_context,
                        )
                    )
    if profile == "normal":
        targeted_trend_lookbacks = (35, 40, 45, 50, 55)
        targeted_trend_profiles = (
            (0.009, 0.014, 0.009, None, 300),
            (0.010, 0.015, 0.010, None, 360),
            (0.011, 0.016, 0.011, None, 420),
        )
        for lookback in targeted_trend_lookbacks:
            for threshold, take_profit, stop_loss, trailing_stop, max_hold in targeted_trend_profiles:
                for use_context in context_flags:
                    context_suffix = "_ctx" if use_context else ""
                    candidate_name = f"trend_pullback_lb{lookback}_th{threshold}_tp{take_profit}{context_suffix}"
                    if candidate_name in seen_names:
                        continue
                    seen_names.add(candidate_name)
                    candidates.append(
                        StrategyV1Candidate(
                            family="trend_pullback",
                            name=candidate_name,
                            lookback_candles=lookback,
                            secondary_lookback_candles=lookback * 3,
                            entry_threshold_pct=threshold,
                            take_profit_pct=take_profit,
                            stop_loss_pct=stop_loss,
                            trailing_stop_pct=trailing_stop,
                            max_hold_candles=max_hold,
                            cooldown_candles=max(1, lookback // 10),
                            fee_bps=10.0,
                            stake_quote_amount=100.0,
                            profile_set=profile,
                            use_context_filter=use_context,
                        )
                    )
        situation_router_lookbacks = (20, 30, 45, 60)
        situation_router_profiles = (
            (0.006, 0.012, 0.006, None, 240),
            (0.008, 0.014, 0.007, 0.006, 360),
            (0.010, 0.018, 0.008, None, 480),
        )
        for lookback in situation_router_lookbacks:
            for threshold, take_profit, stop_loss, trailing_stop, max_hold in situation_router_profiles:
                for use_context in context_flags:
                    context_suffix = "_ctx" if use_context else ""
                    trail_suffix = f"_trail{trailing_stop}" if trailing_stop is not None else ""
                    candidate_name = f"situation_router_lb{lookback}_th{threshold}_tp{take_profit}{trail_suffix}{context_suffix}"
                    if candidate_name in seen_names:
                        continue
                    seen_names.add(candidate_name)
                    candidates.append(
                        StrategyV1Candidate(
                            family="situation_router",
                            name=candidate_name,
                            lookback_candles=lookback,
                            secondary_lookback_candles=lookback * 6,
                            entry_threshold_pct=threshold,
                            take_profit_pct=take_profit,
                            stop_loss_pct=stop_loss,
                            trailing_stop_pct=trailing_stop,
                            max_hold_candles=max_hold,
                            cooldown_candles=max(2, lookback // 8),
                            fee_bps=10.0,
                            stake_quote_amount=100.0,
                            profile_set=profile,
                            use_context_filter=use_context,
                        )
                    )
    return candidates


def _required_lookback(candidate: StrategyV1Candidate) -> int:
    return max(candidate.lookback_candles, candidate.secondary_lookback_candles or 0)


def _has_entry(candles: list[Candle], index: int, candidate: StrategyV1Candidate) -> bool:
    current = candles[index]
    previous = candles[index - candidate.lookback_candles]
    prior = candles[index - 1]
    threshold = candidate.entry_threshold_pct
    if candidate.family == "momentum_breakout":
        return current.close > previous.close * (1 + threshold)
    if candidate.family == "mean_reversion_bounce":
        return previous.close > prior.close * (1 + threshold) and current.close > prior.close
    if candidate.family == "trend_pullback":
        long_lookback = candidate.secondary_lookback_candles or candidate.lookback_candles
        long_previous = candles[index - long_lookback]
        return (
            previous.close > long_previous.close * (1 + threshold)
            and prior.close < previous.close
            and current.close > prior.close * (1 + threshold / 2)
            and current.close > previous.close * (1 - threshold)
        )
    if candidate.family == "range_breakout":
        recent_high = max(
            candle.high for candle in candles[index - candidate.lookback_candles : index]
        )
        return current.close > recent_high * (1 + threshold)
    if candidate.family == "situation_router":
        long_lookback = candidate.secondary_lookback_candles or candidate.lookback_candles * 6
        long_previous = candles[index - long_lookback]
        recent_window = candles[index - candidate.lookback_candles : index]
        recent_high = max(candle.high for candle in recent_window)
        recent_low = min(candle.low for candle in recent_window)
        short_volatility = (recent_high - recent_low) / current.close
        return (
            current.close > long_previous.close * (1 + threshold * 2)
            and prior.close < recent_high * (1 - threshold / 2)
            and current.close > prior.close * (1 + threshold / 4)
            and current.close > long_previous.close * (1 + threshold)
            and short_volatility <= max(0.015, threshold * 4)
        )
    msg = f"unsupported strategy family: {candidate.family}"
    raise ValueError(msg)


def _context_allows_entry(
    candles: list[Candle],
    index: int,
    candidate: StrategyV1Candidate,
    context_by_symbol: dict[str, dict[str, Candle]] | None,
) -> bool:
    if not candidate.use_context_filter:
        return True
    if not context_by_symbol:
        return False
    current_time = candles[index].open_time
    previous_time = candles[index - candidate.lookback_candles].open_time
    for symbol in ("BTCUSDC", "ETHBTC"):
        context = context_by_symbol.get(symbol)
        if context is None or current_time not in context or previous_time not in context:
            return False
        if context[current_time].close <= context[previous_time].close:
            return False
    return True


def _exit_signal(
    candle: Candle,
    entry_price: float,
    candidate: StrategyV1Candidate,
    highest_price_before_candle: float | None = None,
) -> tuple[str, float] | None:
    """Return conservative intrabar exit signal for one LONG Spot candle.

    Historical 1m candles contain OHLC but no tick order inside the candle. If both stop-loss and take-profit
    are touched in the same candle, assume stop-loss first to avoid optimistic blindtest results.
    """
    take_profit_price = entry_price * (1 + candidate.take_profit_pct)
    stop_loss_price = entry_price * (1 - candidate.stop_loss_pct)
    trailing_stop_price = None
    if candidate.trailing_stop_pct is not None and highest_price_before_candle is not None:
        if highest_price_before_candle > entry_price:
            trailing_stop_price = max(stop_loss_price, highest_price_before_candle * (1 - candidate.trailing_stop_pct))
    if candle.low <= stop_loss_price:
        return "stop_loss", stop_loss_price
    if trailing_stop_price is not None and candle.low <= trailing_stop_price:
        return "trailing_stop", trailing_stop_price
    if candle.high >= take_profit_price:
        return "take_profit", take_profit_price
    return None


def _validate_start_capital(start_capital_reference: float) -> None:
    if start_capital_reference <= 0:
        msg = "start_capital_reference must be positive"
        raise ValueError(msg)


def run_strategy_v1_on_candles(
    candles: list[Candle],
    candidate: StrategyV1Candidate,
    start_capital_reference: float = 100.0,
    context_by_symbol: dict[str, dict[str, Candle]] | None = None,
    allowed_entry_times: set[str] | None = None,
    allowed_entry_candidates_by_time: dict[str, StrategyV1Candidate] | None = None,
) -> StrategyV1Result:
    """Run a fixed-stake LONG-only Strategy V1 candidate using every input candle."""
    _validate_start_capital(start_capital_reference)
    try:
        exchange_filters = load_exchange_info_filters()
    except Exception:  # noqa: BLE001
        exchange_filters = None
    trades: list[StrategyV1Trade] = []
    signal_count = 0
    no_trade_count = 0
    blocked_signal_count = 0
    cumulative_pnl = 0.0
    peak_reference = start_capital_reference
    max_drawdown = 0.0
    index = _required_lookback(candidate)
    if allowed_entry_candidates_by_time:
        index = max(index, max(_required_lookback(entry_candidate) for entry_candidate in allowed_entry_candidates_by_time.values()))
    while index < len(candles) - 1:
        active_candidate = allowed_entry_candidates_by_time.get(candles[index].open_time, candidate) if allowed_entry_candidates_by_time is not None else candidate
        if allowed_entry_times is not None and candles[index].open_time not in allowed_entry_times:
            no_trade_count += 1
            index += 1
            continue
        if not _has_entry(candles, index, active_candidate):
            no_trade_count += 1
            index += 1
            continue
        signal_count += 1
        if not _context_allows_entry(candles, index, active_candidate, context_by_symbol):
            blocked_signal_count += 1
            no_trade_count += 1
            index += 1
            continue

        entry = candles[index]
        fee_rate = active_candidate.fee_bps / 10_000
        entry_price = round_price_to_tick(entry.close, exchange_filters.price_tick_size if exchange_filters else None)
        if exchange_filters and exchange_filters.min_notional and active_candidate.stake_quote_amount < exchange_filters.min_notional:
            blocked_signal_count += 1
            no_trade_count += 1
            index += 1
            continue
        quantity = round_quantity_to_step(
            active_candidate.stake_quote_amount / entry_price,
            exchange_filters.lot_step_size if exchange_filters else None,
        )
        if quantity <= 0 or (exchange_filters and exchange_filters.lot_min_qty and quantity < exchange_filters.lot_min_qty):
            blocked_signal_count += 1
            no_trade_count += 1
            index += 1
            continue
        effective_stake = quantity * entry_price
        if exchange_filters and exchange_filters.min_notional and effective_stake < exchange_filters.min_notional:
            blocked_signal_count += 1
            no_trade_count += 1
            index += 1
            continue
        max_exit_index = min(index + active_candidate.max_hold_candles, len(candles) - 1)
        exit_index = max_exit_index
        exit_reason = "max_hold"
        exit_price = round_price_to_tick(candles[exit_index].close, exchange_filters.price_tick_size if exchange_filters else None)
        highest_price_before_candle = entry.high
        for candidate_exit_index in range(index + 1, max_exit_index + 1):
            signal = _exit_signal(candles[candidate_exit_index], entry_price, active_candidate, highest_price_before_candle)
            if signal is not None:
                reason, signal_price = signal
                exit_index = candidate_exit_index
                exit_reason = reason
                exit_price = round_price_to_tick(signal_price, exchange_filters.price_tick_size if exchange_filters else None)
                break
            highest_price_before_candle = max(highest_price_before_candle, candles[candidate_exit_index].high)

        exit_candle = candles[exit_index]
        gross_pnl = quantity * (exit_price - entry_price)
        fees_paid = (
            effective_stake * fee_rate + quantity * exit_price * fee_rate
        )
        net_pnl = gross_pnl - fees_paid
        cumulative_pnl += net_pnl
        equity = start_capital_reference + cumulative_pnl
        peak_reference = max(peak_reference, equity)
        if peak_reference > 0:
            max_drawdown = max(max_drawdown, (peak_reference - equity) / peak_reference * 100)
        trades.append(
            StrategyV1Trade(
                entry_time=entry.open_time,
                exit_time=exit_candle.open_time,
                entry_price=entry_price,
                exit_price=exit_price,
                stake_quote_amount=active_candidate.stake_quote_amount,
                quantity=quantity,
                gross_pnl=gross_pnl,
                fees_paid=fees_paid,
                net_pnl=net_pnl,
                net_pnl_pct=net_pnl / active_candidate.stake_quote_amount * 100,
                exit_reason=exit_reason,
                family=active_candidate.family,
                candidate_name=active_candidate.name,
            )
        )
        index = exit_index + 1 + active_candidate.cooldown_candles

    days = max(1.0, len(candles) / 1440)
    final_reference = start_capital_reference + cumulative_pnl
    return StrategyV1Result(
        candidate=candidate,
        start_capital_reference=start_capital_reference,
        stake_quote_amount=candidate.stake_quote_amount,
        final_capital_reference=final_reference,
        total_net_pnl=cumulative_pnl,
        total_net_pnl_pct=cumulative_pnl / start_capital_reference * 100,
        quote_per_day=cumulative_pnl / days,
        trade_count=len(trades),
        winning_trades=sum(1 for trade in trades if trade.net_pnl > 0),
        losing_trades=sum(1 for trade in trades if trade.net_pnl < 0),
        neutral_trades=sum(1 for trade in trades if trade.net_pnl == 0),
        max_drawdown=max_drawdown,
        trades=trades,
        signal_count=signal_count,
        no_trade_count=no_trade_count,
        blocked_signal_count=blocked_signal_count,
    )


def _training_score(result: StrategyV1Result, all_zero_trades: bool) -> tuple[float, float, int]:
    if result.trade_count == 0 and not all_zero_trades:
        return (-1_000_000_000.0, result.quote_per_day, 0)
    trade_penalty = _low_activity_penalty(result.trade_count)
    stability = _training_stability_metrics(result)
    final_score = result.total_net_pnl - trade_penalty - stability["stability_penalty"] - stability["drawdown_penalty"] - stability["concentration_penalty"]
    return (final_score, result.quote_per_day, result.trade_count)


def _candidate_score_value(result: StrategyV1Result, all_zero_trades: bool = False) -> float:
    return _training_score(result, all_zero_trades)[0]


def _low_activity_penalty(trade_count: int) -> float:
    missing_trades = max(0, ROBUST_TRADE_FLOOR - trade_count)
    exclusion_penalty = LOW_ACTIVITY_EXCLUSION_PENALTY if missing_trades else 0.0
    return missing_trades * LOW_ACTIVITY_PENALTY_PER_MISSING_TRADE + exclusion_penalty


def _trades_per_month(trade_count: int) -> float:
    return trade_count / TRAINING_MONTHS_FOR_ACTIVITY


def _training_stability_metrics(result: StrategyV1Result) -> dict[str, float | int | bool | str]:
    monthly_pnl: dict[str, float] = {}
    positive_trade_pnls: list[float] = []
    all_trade_pnls: list[float] = []
    for trade in result.trades:
        net_pnl = float(getattr(trade, "net_pnl", 0.0))
        exit_time = str(getattr(trade, "exit_time", ""))
        if len(exit_time) >= 7:
            month = exit_time[:7]
            monthly_pnl[month] = monthly_pnl.get(month, 0.0) + net_pnl
        all_trade_pnls.append(net_pnl)
        if net_pnl > 0:
            positive_trade_pnls.append(net_pnl)
    active_months = len(monthly_pnl)
    positive_months = sum(1 for value in monthly_pnl.values() if value > 0)
    negative_months = sum(1 for value in monthly_pnl.values() if value < 0)
    best_trade = max(all_trade_pnls, default=0.0)
    worst_trade = min(all_trade_pnls, default=0.0)
    total_positive_profit = sum(positive_trade_pnls)
    top_trade_profit_share = max(positive_trade_pnls, default=0.0) / total_positive_profit if total_positive_profit > 0 else 0.0
    concentration_warning = top_trade_profit_share > PROFIT_CONCENTRATION_WARNING_SHARE
    active_month_penalty = max(0, MIN_ACTIVE_TRAINING_MONTHS - active_months) * 0.15
    inactive_month_penalty = max(0, TRAINING_TOTAL_MONTHS - active_months) * INACTIVE_TRAINING_MONTH_PENALTY
    month_balance_penalty = max(0, negative_months - positive_months + 1) * NEGATIVE_MONTH_DOMINANCE_PENALTY if active_months else 0.0
    stability_penalty = active_month_penalty + inactive_month_penalty + month_balance_penalty
    drawdown_penalty = max(0.0, result.max_drawdown - MAX_TRAINING_DRAWDOWN_WITHOUT_PENALTY) * 0.05
    concentration_penalty = (0.25 + (top_trade_profit_share - PROFIT_CONCENTRATION_WARNING_SHARE)) if concentration_warning else 0.0
    diagnosis_parts = []
    if active_month_penalty:
        diagnosis_parts.append("few active training months")
    if inactive_month_penalty:
        diagnosis_parts.append("inactive training months")
    if month_balance_penalty:
        diagnosis_parts.append("negative months dominate")
    if drawdown_penalty:
        diagnosis_parts.append("training drawdown penalty")
    if concentration_warning:
        diagnosis_parts.append("profit concentrated in top trade")
    return {
        "training_positive_months": positive_months,
        "training_negative_months": negative_months,
        "training_active_months": active_months,
        "training_total_months": TRAINING_TOTAL_MONTHS,
        "training_max_drawdown": result.max_drawdown,
        "training_best_trade_pnl": best_trade,
        "training_worst_trade_pnl": worst_trade,
        "training_top_trade_profit_share": top_trade_profit_share,
        "training_profit_concentration_warning": concentration_warning,
        "stability_penalty": stability_penalty,
        "drawdown_penalty": drawdown_penalty,
        "concentration_penalty": concentration_penalty,
        "stability_diagnosis": "; ".join(diagnosis_parts) if diagnosis_parts else "stable enough by current training-only rules",
    }


def _evaluation_from_result(result: StrategyV1Result, score: float, selected: bool) -> StrategyV1CandidateEvaluation:
    gross = sum(trade.gross_pnl for trade in result.trades)
    fees = sum(trade.fees_paid for trade in result.trades)
    win_rate = result.winning_trades / result.trade_count if result.trade_count else None
    low_activity_penalty = _low_activity_penalty(result.trade_count)
    score_before_stability = result.total_net_pnl - low_activity_penalty
    stability = _training_stability_metrics(result)
    return StrategyV1CandidateEvaluation(
        candidate=result.candidate,
        train_trade_count=result.trade_count,
        train_gross_pnl=gross,
        train_fees=fees,
        train_net_pnl=result.total_net_pnl,
        train_pnl_per_day=result.quote_per_day,
        train_trades_per_month=_trades_per_month(result.trade_count),
        raw_score=result.total_net_pnl,
        low_activity_penalty=low_activity_penalty,
        adjusted_score=score_before_stability,
        low_activity_penalty_applied=low_activity_penalty > 0,
        train_win_rate=win_rate,
        score=score,
        selected=selected,
        reason="selected best final training stability score" if selected else "lower final training stability score",
        training_positive_months=int(stability["training_positive_months"]),
        training_negative_months=int(stability["training_negative_months"]),
        training_active_months=int(stability["training_active_months"]),
        training_total_months=int(stability["training_total_months"]),
        training_max_drawdown=float(stability["training_max_drawdown"]),
        training_best_trade_pnl=float(stability["training_best_trade_pnl"]),
        training_worst_trade_pnl=float(stability["training_worst_trade_pnl"]),
        training_top_trade_profit_share=float(stability["training_top_trade_profit_share"]),
        training_profit_concentration_warning=bool(stability["training_profit_concentration_warning"]),
        stability_penalty=float(stability["stability_penalty"]),
        drawdown_penalty=float(stability["drawdown_penalty"]),
        concentration_penalty=float(stability["concentration_penalty"]),
        adjusted_score_final=score,
        stability_diagnosis=str(stability["stability_diagnosis"]),
    )


def _default_candidates_for_profile(profile: str) -> list[StrategyV1Candidate]:
    try:
        return default_strategy_v1_candidates(profile)
    except TypeError:
        return default_strategy_v1_candidates()


def _run_candidate(
    candles: list[Candle],
    candidate: StrategyV1Candidate,
    start_capital_reference: float,
    context_by_symbol: dict[str, dict[str, Candle]] | None,
) -> StrategyV1Result:
    try:
        return run_strategy_v1_on_candles(candles, candidate, start_capital_reference, context_by_symbol)
    except TypeError:
        return run_strategy_v1_on_candles(candles, candidate, start_capital_reference)


def select_best_strategy_v1(
    training_candles: list[Candle],
    start_capital_reference: float = 100.0,
    progress_callback: Callable[[dict], None] | None = None,
    profile: str = "normal",
    context_by_symbol: dict[str, dict[str, Candle]] | None = None,
) -> StrategyV1Result:
    """Select the best V1 candidate on training candles only."""
    _validate_start_capital(start_capital_reference)
    candidates = _default_candidates_for_profile(profile)
    results: list[StrategyV1Result] = []
    total_candidates = len(candidates)
    for index, candidate in enumerate(candidates, start=1):
        if progress_callback is not None:
            progress_callback(
                {
                    "phase": "strategy_v1_training_started",
                    "current_candidate": index,
                    "total_candidates": total_candidates,
                    "progress_pct": 70.0 + (index / total_candidates * 10.0),
                    "detail": f"Strategy V1 Training Kandidat {index}/{total_candidates}",
                }
            )
        results.append(
            _run_candidate(training_candles, candidate, start_capital_reference, context_by_symbol)
        )
    all_zero_trades = all(result.trade_count == 0 for result in results)
    return max(results, key=lambda result: _training_score(result, all_zero_trades))


def evaluate_strategy_v1_candidates(
    training_candles: list[Candle],
    start_capital_reference: float = 100.0,
    profile: str = "normal",
    context_by_symbol: dict[str, dict[str, Candle]] | None = None,
    progress_callback: Callable[[dict], None] | None = None,
) -> tuple[StrategyV1Result, list[StrategyV1CandidateEvaluation]]:
    """Evaluate all V1 candidates on training candles and return selected plus audit rows."""
    _validate_start_capital(start_capital_reference)
    candidates = _default_candidates_for_profile(profile)
    results: list[StrategyV1Result] = []
    total_candidates = len(candidates)
    for index, candidate in enumerate(candidates, start=1):
        if progress_callback is not None:
            progress_callback(
                {
                    "phase": "strategy_v1_training_started",
                    "current_candidate": index,
                    "total_candidates": total_candidates,
                    "progress_pct": 70.0 + (index / total_candidates * 10.0),
                    "detail": f"Strategy V1 Training Kandidat {index}/{total_candidates}",
                }
            )
        results.append(_run_candidate(training_candles, candidate, start_capital_reference, context_by_symbol))
    all_zero_trades = all(result.trade_count == 0 for result in results)
    selected = max(results, key=lambda result: _training_score(result, all_zero_trades))
    evaluations = [
        _evaluation_from_result(result, _candidate_score_value(result, all_zero_trades), result.candidate == selected.candidate)
        for result in results
    ]
    return selected, evaluations
