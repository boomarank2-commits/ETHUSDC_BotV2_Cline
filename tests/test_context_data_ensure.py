from pathlib import Path

import pytest

import src.data.context_data_ensure as context_module
from src.data.candle_csv_io import save_candle_dataset_to_csv
from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle
from src.data.data_catalog import load_data_catalog, save_data_catalog


def _dataset(symbol: str, count: int) -> CandleDataset:
    return CandleDataset(
        symbol,
        "1m",
        [Candle(f"2026-01-01T00:{index:02d}:00Z", 100.0, 101.0, 99.0, 100.0, 1.0) for index in range(count)],
    )


def test_existing_complete_context_csv_is_upserted_to_catalog(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    btc_path = tmp_path / "BTCUSDC_1m.csv"
    save_candle_dataset_to_csv(_dataset("BTCUSDC", 5), btc_path)
    save_data_catalog([])
    monkeypatch.setattr(context_module, "REQUIRED_CANDLE_COUNT", 5)
    monkeypatch.setattr(context_module, "_is_current", lambda last_open_time: True)
    monkeypatch.setattr(context_module, "DEFAULT_CONTEXT_CANDLE_PATHS", {"BTCUSDC": btc_path, "ETHBTC": tmp_path / "ETHBTC_1m.csv"})

    result = context_module.ensure_context_1m_data_ready("BTCUSDC")

    assert result.success is True
    entries = load_data_catalog()
    assert [(entry.symbol, entry.interval, entry.path) for entry in entries] == [("BTCUSDC", "1m", str(btc_path))]


def test_legacy_context_csv_is_fully_replaced_before_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    btc_path = tmp_path / "BTCUSDC_1m.csv"
    btc_path.write_text(
        "open_time,open,high,low,close,volume\n"
        "2026-01-01T00:00:00Z,100,101,99,100,1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(context_module, "REQUIRED_CANDLE_COUNT", 1)
    monkeypatch.setattr(context_module, "_is_current", lambda last_open_time: True)
    monkeypatch.setattr(
        context_module,
        "DEFAULT_CONTEXT_CANDLE_PATHS",
        {"BTCUSDC": btc_path},
    )
    replace_existing = False

    def fake_download(**kwargs):
        nonlocal replace_existing
        replace_existing = kwargs["replace_existing"]
        save_candle_dataset_to_csv(_dataset("BTCUSDC", 1), kwargs["output_path"])
        return _dataset("BTCUSDC", 1)

    monkeypatch.setattr(
        context_module,
        "download_ethusdc_1m_candles",
        fake_download,
    )

    result = context_module.ensure_context_1m_data_ready("BTCUSDC")

    assert result.success is True
    assert replace_existing is True
