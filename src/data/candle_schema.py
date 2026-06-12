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

        if self.high < max(self.open, self.close, self.low):
            msg = "high must be greater than or equal to open, close and low"
            raise ValueError(msg)

        if self.low > min(self.open, self.close, self.high):
            msg = "low must be less than or equal to open, close and high"
            raise ValueError(msg)
