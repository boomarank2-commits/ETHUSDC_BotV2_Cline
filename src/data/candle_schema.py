"""Technical candle data contract."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    """Single candle data record."""

    open_time: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float = 0.0
    trade_count: int = 0
    taker_buy_base_volume: float = 0.0
    taker_buy_quote_volume: float = 0.0
    close_time: str | None = None

    def __post_init__(self) -> None:
        if not self.open_time:
            msg = "open_time must not be empty"
            raise ValueError(msg)

        for field_name, value in (
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("close", self.close),
        ):
            if value <= 0:
                msg = f"{field_name} must be positive"
                raise ValueError(msg)

        if self.volume < 0:
            msg = "volume must not be negative"
            raise ValueError(msg)

        for field_name, value in (
            ("quote_volume", self.quote_volume),
            ("taker_buy_base_volume", self.taker_buy_base_volume),
            ("taker_buy_quote_volume", self.taker_buy_quote_volume),
        ):
            if value < 0:
                msg = f"{field_name} must not be negative"
                raise ValueError(msg)

        if self.trade_count < 0:
            msg = "trade_count must not be negative"
            raise ValueError(msg)

        if self.high < max(self.open, self.close, self.low):
            msg = "high must be greater than or equal to open, close and low"
            raise ValueError(msg)

        if self.low > min(self.open, self.close, self.high):
            msg = "low must be less than or equal to open, close and high"
            raise ValueError(msg)
