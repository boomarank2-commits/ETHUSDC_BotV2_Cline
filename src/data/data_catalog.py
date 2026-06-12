"""Local data catalog for candle files."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.common.config import CONFIG
from src.common.paths import CONFIGS_DIR

CATALOG_FILENAME = "data_catalog.json"
DEFAULT_ETHUSDC_1M_PATH = "data/candles/ETHUSDC_1m.csv"


@dataclass(frozen=True)
class CandleDataCatalogEntry:
    """Technical reference to one local candle data file."""

    symbol: str
    interval: str
    path: str

    def __post_init__(self) -> None:
        if self.symbol != CONFIG.symbol:
            msg = f"symbol must be {CONFIG.symbol}"
            raise ValueError(msg)
        if self.interval != "1m":
            msg = 'interval must be "1m"'
            raise ValueError(msg)
        if not self.path:
            msg = "path must not be empty"
            raise ValueError(msg)
        path_parts = Path(self.path).parts
        if ".." in path_parts:
            msg = "path must not contain traversal segments"
            raise ValueError(msg)


def default_ethusdc_1m_catalog_entry() -> CandleDataCatalogEntry:
    """Return the default local ETHUSDC 1m candle catalog entry."""
    return CandleDataCatalogEntry(
        symbol=CONFIG.symbol,
        interval="1m",
        path=DEFAULT_ETHUSDC_1M_PATH,
    )


def get_catalog_path() -> Path:
    """Return the technical data catalog path."""
    return CONFIGS_DIR / CATALOG_FILENAME


def save_data_catalog(entries: list[CandleDataCatalogEntry]) -> Path:
    """Save data catalog entries as readable JSON."""
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    catalog_path = get_catalog_path()
    content = json.dumps([asdict(entry) for entry in entries], indent=2, sort_keys=True)
    catalog_path.write_text(f"{content}\n", encoding="utf-8")
    return catalog_path


def load_data_catalog() -> list[CandleDataCatalogEntry]:
    """Load and validate data catalog entries."""
    raw_entries: list[dict[str, Any]] = json.loads(get_catalog_path().read_text(encoding="utf-8"))
    return [CandleDataCatalogEntry(**entry) for entry in raw_entries]
