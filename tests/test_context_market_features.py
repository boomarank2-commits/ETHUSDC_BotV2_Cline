import src.data.context_market_features as context_module
import pytest

from src.data.candle_csv_io import save_candle_dataset_to_csv
from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle
from src.data.context_market_features import build_closed_context_market_feature_store
from src.data.data_catalog import CandleDataCatalogEntry


def _candles(closes: list[float]) -> list[Candle]:
    return [
        Candle(
            open_time=f"2026-01-01T00:{index:02d}:00Z",
            open=close,
            high=close * 1.01,
            low=close * 0.99,
            close=close,
            volume=1.0,
        )
        for index, close in enumerate(closes)
    ]


def _context_entries(tmp_path, values_by_symbol: dict[str, list[float]]):
    entries = []
    for symbol, closes in values_by_symbol.items():
        path = tmp_path / f"{symbol}_1m.csv"
        save_candle_dataset_to_csv(CandleDataset(symbol, "1m", _candles(closes)), path)
        entries.append(CandleDataCatalogEntry(symbol, "1m", str(path)))
    return entries


def test_context_market_features_align_closed_context_minutes(tmp_path, monkeypatch) -> None:
    entries = _context_entries(
        tmp_path,
        {
            "BTCUSDC": [100.0, 110.0, 120.0],
            "ETHBTC": [0.02, 0.02, 0.03],
            "ETHUSDT": [100.0, 100.0, 102.0],
            "USDCUSDT": [1.0, 1.0, 1.001],
        },
    )
    monkeypatch.setattr(context_module, "load_data_catalog", lambda: entries)

    store = build_closed_context_market_feature_store(_candles([100.0, 100.0, 101.0]))
    series = store.series_for_lookback(2)

    assert store.available_sources == ["BTCUSDC", "ETHBTC", "ETHUSDT", "USDCUSDT"]
    assert series.value_at("btcusdc_return", 2) == pytest.approx(0.2)
    assert series.value_at("ethbtc_return", 2) == pytest.approx(0.5)
    assert series.value_at("ethusdt_ethusdc_basis", 2) == pytest.approx(102 / 101 - 1)
    assert series.value_at("usdcusdt_deviation", 2) == pytest.approx(0.001)


def test_context_market_feature_at_entry_is_unchanged_by_future_minutes(
    tmp_path,
    monkeypatch,
) -> None:
    initial = {
        "BTCUSDC": [100.0, 110.0, 120.0],
        "ETHBTC": [0.02, 0.02, 0.03],
        "ETHUSDT": [100.0, 100.0, 102.0],
        "USDCUSDT": [1.0, 1.0, 1.001],
    }
    entries = _context_entries(tmp_path, initial)
    monkeypatch.setattr(context_module, "load_data_catalog", lambda: entries)
    before = build_closed_context_market_feature_store(
        _candles([100.0, 100.0, 101.0])
    ).series_for_lookback(2)

    future_entries = _context_entries(
        tmp_path,
        {
            symbol: values + [value * 10]
            for (symbol, values), value in zip(initial.items(), (1000.0, 0.3, 1000.0, 1.2), strict=True)
        },
    )
    monkeypatch.setattr(context_module, "load_data_catalog", lambda: future_entries)
    after = build_closed_context_market_feature_store(
        _candles([100.0, 100.0, 101.0, 1000.0])
    ).series_for_lookback(2)

    for metric in context_module.CONTEXT_MARKET_METRICS:
        assert after.value_at(metric, 2) == before.value_at(metric, 2)
