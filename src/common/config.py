"""Minimal confirmed project configuration."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectConfig:
    """Confirmed static project settings without secret or exchange handling."""

    symbol: str = "ETHUSDC"
    quote_asset: str = "USDC"
    exchange: str = "Binance Spot"
    long_only: bool = True
    allow_short: bool = False
    allow_futures: bool = False
    allow_margin: bool = False
    allow_leverage: bool = False
    training_days: int = 730
    blindtest_days: int = 365
    allow_blindtest_learning: bool = False
    allow_early_capital_stop: bool = False


CONFIG = ProjectConfig()