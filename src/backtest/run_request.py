"""Technical schema for a future backtest start request."""

import re
from dataclasses import dataclass
from pathlib import Path

from src.common.config import CONFIG

_SAFE_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


def _validate_run_id(run_id: str) -> None:
    if not run_id:
        msg = "run_id must not be empty"
        raise ValueError(msg)

    if not _SAFE_RUN_ID_PATTERN.fullmatch(run_id):
        msg = "run_id may contain only letters, numbers and underscores"
        raise ValueError(msg)

    run_path = Path(run_id)
    if run_path.name != run_id:
        msg = "run_id must not contain path separators"
        raise ValueError(msg)


def _require_equal(name: str, value: object, expected: object) -> None:
    if value != expected:
        msg = f"{name} must be {expected!r}"
        raise ValueError(msg)


def _require_false(name: str, value: bool) -> None:
    if value is not False:
        msg = f"{name} must be False"
        raise ValueError(msg)


@dataclass(frozen=True)
class BacktestRunRequest:
    """Validated technical request for a later backtest run."""

    run_id: str
    symbol: str
    quote_asset: str
    exchange: str
    start_capital: float
    training_days: int
    blindtest_days: int
    time_budget_minutes: int | None
    allow_short: bool
    allow_futures: bool
    allow_margin: bool
    allow_leverage: bool
    allow_blindtest_learning: bool
    allow_early_capital_stop: bool

    def __post_init__(self) -> None:
        _validate_run_id(self.run_id)
        _require_equal("symbol", self.symbol, CONFIG.symbol)
        _require_equal("quote_asset", self.quote_asset, CONFIG.quote_asset)
        _require_equal("exchange", self.exchange, CONFIG.exchange)
        _require_equal("training_days", self.training_days, CONFIG.training_days)
        _require_equal("blindtest_days", self.blindtest_days, CONFIG.blindtest_days)
        _require_false("allow_short", self.allow_short)
        _require_false("allow_futures", self.allow_futures)
        _require_false("allow_margin", self.allow_margin)
        _require_false("allow_leverage", self.allow_leverage)
        _require_false("allow_blindtest_learning", self.allow_blindtest_learning)
        _require_false("allow_early_capital_stop", self.allow_early_capital_stop)

        if self.start_capital <= 0:
            msg = "start_capital must be positive"
            raise ValueError(msg)

        if self.time_budget_minutes is not None and self.time_budget_minutes <= 0:
            msg = "time_budget_minutes must be None or positive"
            raise ValueError(msg)


def default_backtest_run_request(run_id: str) -> BacktestRunRequest:
    """Create a default backtest run request from confirmed project config."""
    return BacktestRunRequest(
        run_id=run_id,
        symbol=CONFIG.symbol,
        quote_asset=CONFIG.quote_asset,
        exchange=CONFIG.exchange,
        start_capital=100.0,
        training_days=CONFIG.training_days,
        blindtest_days=CONFIG.blindtest_days,
        time_budget_minutes=None,
        allow_short=CONFIG.allow_short,
        allow_futures=CONFIG.allow_futures,
        allow_margin=CONFIG.allow_margin,
        allow_leverage=CONFIG.allow_leverage,
        allow_blindtest_learning=CONFIG.allow_blindtest_learning,
        allow_early_capital_stop=CONFIG.allow_early_capital_stop,
    )
