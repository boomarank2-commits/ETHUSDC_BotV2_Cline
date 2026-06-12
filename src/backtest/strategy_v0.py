"""Strategy V0 LONG-only Spot training and blindtest engine."""

from dataclasses import dataclass

from src.data.candle_schema import Candle


@dataclass(frozen=True)
class StrategyV0Candidate:
    """Fixed LONG-only momentum/breakout candidate."""

    name: str
    lookback_candles: int
    entry_threshold_pct: float
    take_profit_pct: float
    stop_loss_pct: float
    max_hold_candles: int
    fee_bps: float

    def __post_init__(self) -> None:
        if not self.name:
            msg = "name must not be empty"
            raise ValueError(msg)
        for value in (
            self.lookback_candles,
            self.entry_threshold_pct,
            self.take_profit_pct,
            self.stop_loss_pct,
            self.max_hold_candles,
            self.fee_bps,
        ):
            if value <= 0:
                msg = "candidate values must be positive"
                raise ValueError(msg)


@dataclass(frozen=True)
class StrategyV0Trade:
    """One completed LONG-only Spot strategy trade."""

    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    exit_reason: str


@dataclass(frozen=True)
class StrategyV0Result:
    """Result of running one fixed Strategy V0 candidate."""

    candidate: StrategyV0Candidate
    start_capital: float
    final_capital: float
    total_pnl: float
    total_pnl_pct: float
    trade_count: int
    winning_trades: int
    losing_trades: int
    max_drawdown: float
    trades: list[StrategyV0Trade]


def default_strategy_v0_candidates() -> list[StrategyV0Candidate]:
    """Return a small fixed candidate set for V0 training comparison."""
    candidates: list[StrategyV0Candidate] = []
    threshold_sets = [
        (0.002, 0.004, 0.003, 60),
        (0.006, 0.008, 0.006, 240),
        (0.012, 0.015, 0.012, 720),
    ]
    for lookback in (30, 120, 360):
        for threshold, take_profit, stop_loss, max_hold in threshold_sets:
            for fee_bps in (10.0,):
                candidates.append(
                    StrategyV0Candidate(
                        name=(
                            f"v0_lb{lookback}_th{threshold}_tp{take_profit}_"
                            f"sl{stop_loss}_mh{max_hold}"
                        ),
                        lookback_candles=lookback,
                        entry_threshold_pct=threshold,
                        take_profit_pct=take_profit,
                        stop_loss_pct=stop_loss,
                        max_hold_candles=max_hold,
                        fee_bps=fee_bps,
                    )
                )
    return candidates


def _validate_start_capital(start_capital: float) -> None:
    if start_capital <= 0:
        msg = "start_capital must be positive"
        raise ValueError(msg)


def _exit_reason(close: float, entry_price: float, candidate: StrategyV0Candidate) -> str | None:
    if close >= entry_price * (1 + candidate.take_profit_pct):
        return "take_profit"
    if close <= entry_price * (1 - candidate.stop_loss_pct):
        return "stop_loss"
    return None


def run_strategy_v0_on_candles(
    candles: list[Candle],
    candidate: StrategyV0Candidate,
    start_capital: float,
) -> StrategyV0Result:
    """Run one fixed LONG-only Spot Strategy V0 candidate on candles."""
    _validate_start_capital(start_capital)
    capital = start_capital
    peak_capital = start_capital
    max_drawdown = 0.0
    trades: list[StrategyV0Trade] = []
    fee_rate = candidate.fee_bps / 10_000
    index = candidate.lookback_candles
    while index < len(candles) - 1:
        current = candles[index]
        previous = candles[index - candidate.lookback_candles]
        if current.close <= previous.close * (1 + candidate.entry_threshold_pct):
            index += 1
            continue

        entry_price = current.close
        entry_capital = capital
        quantity = entry_capital * (1 - fee_rate) / entry_price
        max_exit_index = min(index + candidate.max_hold_candles, len(candles) - 1)
        exit_index = max_exit_index
        exit_reason = "max_hold"
        for candidate_exit_index in range(index + 1, max_exit_index + 1):
            reason = _exit_reason(candles[candidate_exit_index].close, entry_price, candidate)
            if reason is not None:
                exit_index = candidate_exit_index
                exit_reason = reason
                break

        exit_candle = candles[exit_index]
        exit_capital = quantity * exit_candle.close * (1 - fee_rate)
        pnl = exit_capital - entry_capital
        pnl_pct = pnl / entry_capital * 100
        capital = exit_capital
        peak_capital = max(peak_capital, capital)
        if peak_capital > 0:
            max_drawdown = max(max_drawdown, (peak_capital - capital) / peak_capital * 100)
        trades.append(
            StrategyV0Trade(
                entry_time=current.open_time,
                exit_time=exit_candle.open_time,
                entry_price=entry_price,
                exit_price=exit_candle.close,
                quantity=quantity,
                pnl=pnl,
                pnl_pct=pnl_pct,
                exit_reason=exit_reason,
            )
        )
        index = exit_index + 1

    total_pnl = capital - start_capital
    return StrategyV0Result(
        candidate=candidate,
        start_capital=start_capital,
        final_capital=capital,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl / start_capital * 100,
        trade_count=len(trades),
        winning_trades=sum(1 for trade in trades if trade.pnl > 0),
        losing_trades=sum(1 for trade in trades if trade.pnl < 0),
        max_drawdown=max_drawdown,
        trades=trades,
    )


def select_best_strategy_v0(
    training_candles: list[Candle],
    start_capital: float,
) -> StrategyV0Result:
    """Select the best Strategy V0 candidate on training candles only."""
    _validate_start_capital(start_capital)
    results = [
        run_strategy_v0_on_candles(training_candles, candidate, start_capital)
        for candidate in default_strategy_v0_candidates()
    ]
    return max(results, key=lambda result: (result.final_capital, result.trade_count))
