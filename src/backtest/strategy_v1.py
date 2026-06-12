"""Strategy V1 fixed-stake LONG-only Spot backtest engine."""

from dataclasses import dataclass
from typing import Callable

from src.data.candle_schema import Candle


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


def default_strategy_v1_candidates() -> list[StrategyV1Candidate]:
    """Return 24 fixed V1 candidates across four simple LONG-only families."""
    families = ("momentum_breakout", "mean_reversion_bounce", "trend_pullback", "range_breakout")
    lookbacks = (30, 120, 360)
    profiles = ((0.004, 0.008, 0.006, 120), (0.010, 0.015, 0.010, 360))
    candidates: list[StrategyV1Candidate] = []
    for family in families:
        for lookback in lookbacks:
            for threshold, take_profit, stop_loss, max_hold in profiles:
                secondary = lookback * 3 if family == "trend_pullback" else None
                candidates.append(
                    StrategyV1Candidate(
                        family=family,
                        name=f"{family}_lb{lookback}_th{threshold}_tp{take_profit}",
                        lookback_candles=lookback,
                        secondary_lookback_candles=secondary,
                        entry_threshold_pct=threshold,
                        take_profit_pct=take_profit,
                        stop_loss_pct=stop_loss,
                        max_hold_candles=max_hold,
                        cooldown_candles=max(1, lookback // 10),
                        fee_bps=10.0,
                        stake_quote_amount=100.0,
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
            previous.close > long_previous.close
            and prior.close < previous.close
            and current.close > prior.close
        )
    if candidate.family == "range_breakout":
        recent_high = max(
            candle.high for candle in candles[index - candidate.lookback_candles : index]
        )
        return current.close > recent_high * (1 + threshold)
    msg = f"unsupported strategy family: {candidate.family}"
    raise ValueError(msg)


def _exit_reason(close: float, entry_price: float, candidate: StrategyV1Candidate) -> str | None:
    if close >= entry_price * (1 + candidate.take_profit_pct):
        return "take_profit"
    if close <= entry_price * (1 - candidate.stop_loss_pct):
        return "stop_loss"
    return None


def _validate_start_capital(start_capital_reference: float) -> None:
    if start_capital_reference <= 0:
        msg = "start_capital_reference must be positive"
        raise ValueError(msg)


def run_strategy_v1_on_candles(
    candles: list[Candle],
    candidate: StrategyV1Candidate,
    start_capital_reference: float = 100.0,
) -> StrategyV1Result:
    """Run a fixed-stake LONG-only Strategy V1 candidate using every input candle."""
    _validate_start_capital(start_capital_reference)
    fee_rate = candidate.fee_bps / 10_000
    trades: list[StrategyV1Trade] = []
    cumulative_pnl = 0.0
    peak_reference = start_capital_reference
    max_drawdown = 0.0
    index = _required_lookback(candidate)
    while index < len(candles) - 1:
        if not _has_entry(candles, index, candidate):
            index += 1
            continue

        entry = candles[index]
        quantity = candidate.stake_quote_amount / entry.close
        max_exit_index = min(index + candidate.max_hold_candles, len(candles) - 1)
        exit_index = max_exit_index
        exit_reason = "max_hold"
        for candidate_exit_index in range(index + 1, max_exit_index + 1):
            reason = _exit_reason(candles[candidate_exit_index].close, entry.close, candidate)
            if reason is not None:
                exit_index = candidate_exit_index
                exit_reason = reason
                break

        exit_candle = candles[exit_index]
        gross_pnl = quantity * (exit_candle.close - entry.close)
        fees_paid = (
            candidate.stake_quote_amount * fee_rate + quantity * exit_candle.close * fee_rate
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
                entry_price=entry.close,
                exit_price=exit_candle.close,
                stake_quote_amount=candidate.stake_quote_amount,
                quantity=quantity,
                gross_pnl=gross_pnl,
                fees_paid=fees_paid,
                net_pnl=net_pnl,
                net_pnl_pct=net_pnl / candidate.stake_quote_amount * 100,
                exit_reason=exit_reason,
                family=candidate.family,
                candidate_name=candidate.name,
            )
        )
        index = exit_index + 1 + candidate.cooldown_candles

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
    )


def _training_score(result: StrategyV1Result, all_zero_trades: bool) -> tuple[float, float, int]:
    if result.trade_count == 0 and not all_zero_trades:
        return (-1_000_000_000.0, result.quote_per_day, 0)
    trade_penalty = 0.0 if result.trade_count >= 3 else (3 - result.trade_count) * 0.01
    return (result.total_net_pnl - trade_penalty, result.quote_per_day, result.trade_count)


def select_best_strategy_v1(
    training_candles: list[Candle],
    start_capital_reference: float = 100.0,
    progress_callback: Callable[[dict], None] | None = None,
) -> StrategyV1Result:
    """Select the best V1 candidate on training candles only."""
    _validate_start_capital(start_capital_reference)
    candidates = default_strategy_v1_candidates()
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
            run_strategy_v1_on_candles(training_candles, candidate, start_capital_reference)
        )
    all_zero_trades = all(result.trade_count == 0 for result in results)
    return max(results, key=lambda result: _training_score(result, all_zero_trades))
