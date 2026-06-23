"""Technical candle dataset contract."""

from dataclasses import dataclass

from src.common.config import CONFIG
from src.data.candle_schema import Candle

ALLOWED_CANDLE_SYMBOLS = (CONFIG.symbol, "BTCUSDC", "ETHBTC")


@dataclass(frozen=True)
class CandleDataset:
    """Validated collection of candles for one symbol and interval."""

    symbol: str
    interval: str
    candles: list[Candle]

    def __post_init__(self) -> None:
        if self.symbol not in ALLOWED_CANDLE_SYMBOLS:
            msg = f"symbol must be one of: {', '.join(ALLOWED_CANDLE_SYMBOLS)}"
            raise ValueError(msg)

        if self.interval != "1m":
            msg = 'interval must be "1m"'
            raise ValueError(msg)

        if not self.candles:
            msg = "candles must not be empty"
            raise ValueError(msg)

        open_times = [candle.open_time for candle in self.candles]
        if len(open_times) != len(set(open_times)):
            msg = "open_time values must be unique"
            raise ValueError(msg)

        if open_times != sorted(open_times):
            msg = "open_time values must be sorted ascending"
            raise ValueError(msg)
