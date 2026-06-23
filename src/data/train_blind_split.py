"""Technical train/blindtest candle window splitter."""

from dataclasses import dataclass

from src.common.config import CONFIG
from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle

TRAINING_DAYS = 730
BLINDTEST_DAYS = 365
CANDLES_PER_DAY_1M = 24 * 60
TRAINING_CANDLE_COUNT = TRAINING_DAYS * CANDLES_PER_DAY_1M
BLINDTEST_CANDLE_COUNT = BLINDTEST_DAYS * CANDLES_PER_DAY_1M
REQUIRED_CANDLE_COUNT = TRAINING_CANDLE_COUNT + BLINDTEST_CANDLE_COUNT


@dataclass(frozen=True)
class TrainBlindSplit:
    """Technical split of candles into training and blindtest windows."""

    symbol: str
    interval: str
    training_candles: list[Candle]
    blindtest_candles: list[Candle]
    training_start: str
    training_end: str
    blindtest_start: str
    blindtest_end: str


def build_train_blind_split(
    dataset: CandleDataset,
    training_days: int | None = None,
    blindtest_days: int | None = None,
) -> TrainBlindSplit:
    """Split the latest required candles into training and blindtest windows."""
    if dataset.symbol != CONFIG.symbol:
        msg = f"symbol must be {CONFIG.symbol}"
        raise ValueError(msg)
    if dataset.interval != "1m":
        msg = 'interval must be "1m"'
        raise ValueError(msg)
    training_candle_count = TRAINING_CANDLE_COUNT if training_days is None else training_days * CANDLES_PER_DAY_1M
    blindtest_candle_count = BLINDTEST_CANDLE_COUNT if blindtest_days is None else blindtest_days * CANDLES_PER_DAY_1M
    required_candle_count = training_candle_count + blindtest_candle_count
    if training_candle_count <= 0 or blindtest_candle_count <= 0:
        msg = "training_days and blindtest_days must produce positive candle counts"
        raise ValueError(msg)
    if len(dataset.candles) < required_candle_count:
        msg = "dataset does not contain enough candles for train/blind split"
        raise ValueError(msg)

    selected_candles = dataset.candles[-required_candle_count:]
    training_candles = selected_candles[:training_candle_count]
    blindtest_candles = selected_candles[training_candle_count:]

    if training_candles[-1].open_time >= blindtest_candles[0].open_time:
        msg = "training window must end before blindtest window starts"
        raise ValueError(msg)

    if set(training_candles).intersection(blindtest_candles):
        msg = "training and blindtest candles must not overlap"
        raise ValueError(msg)

    return TrainBlindSplit(
        symbol=dataset.symbol,
        interval=dataset.interval,
        training_candles=training_candles,
        blindtest_candles=blindtest_candles,
        training_start=training_candles[0].open_time,
        training_end=training_candles[-1].open_time,
        blindtest_start=blindtest_candles[0].open_time,
        blindtest_end=blindtest_candles[-1].open_time,
    )
