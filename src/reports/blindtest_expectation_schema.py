"""Schema models for future blindtest expectation reports."""

import re
from dataclasses import dataclass, field
from pathlib import Path

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


def _validate_non_negative_int(value: int, field_name: str) -> None:
    if value < 0:
        msg = f"{field_name} must not be negative"
        raise ValueError(msg)


@dataclass(frozen=True)
class MonthlyBlindtestResult:
    """Monthly result structure for a future blindtest expectation report."""

    month: str
    pnl: float
    trades: int
    winning_trades: int
    losing_trades: int
    no_trade_decisions: int

    def __post_init__(self) -> None:
        _validate_non_negative_int(self.trades, "trades")
        _validate_non_negative_int(self.winning_trades, "winning_trades")
        _validate_non_negative_int(self.losing_trades, "losing_trades")
        _validate_non_negative_int(self.no_trade_decisions, "no_trade_decisions")


@dataclass(frozen=True)
class BlindtestExpectationSummary:
    """Summary structure for a future blindtest expectation report."""

    run_id: str
    training_start: str
    training_end: str
    blindtest_start: str
    blindtest_end: str
    start_capital: float
    final_result: float
    total_pnl: float
    best_month: str | None
    worst_month: str | None
    positive_months: int
    negative_months: int
    neutral_months: int
    expected_monthly_min: float | None
    expected_monthly_max: float | None
    monthly_results: list[MonthlyBlindtestResult] = field(default_factory=list)

    def __post_init__(self) -> None:
        _validate_run_id(self.run_id)
        _validate_non_negative_int(self.positive_months, "positive_months")
        _validate_non_negative_int(self.negative_months, "negative_months")
        _validate_non_negative_int(self.neutral_months, "neutral_months")
