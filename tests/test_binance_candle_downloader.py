from dataclasses import fields
from pathlib import Path

import pytest

import src.data.binance_candle_downloader as downloader_module
from src.data.binance_candle_downloader import (
    binance_kline_to_candle,
    download_ethusdc_1m_candles,
)
from src.data.binance_kline_client import BinanceKline
from src.data.data_catalog import load_data_catalog


def _kline(open_time_ms: int, close: float = 105.0) -> BinanceKline:
    return BinanceKline(open_time_ms, 100.0, 110.0, 90.0, close, 1.0)


def test_binance_kline_is_converted_to_candle() -> None:
    candle = binance_kline_to_candle(_kline(1_700_000_000_000))

    assert candle.open_time.endswith("Z")
    assert candle.close == 105.0


def test_downloader_paginates_multiple_pages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pages = [[_kline(60_000), _kline(120_000)], [_kline(180_000)]]
    calls = 0

    def fake_fetch(*args: object, **kwargs: object) -> list[BinanceKline]:
        nonlocal calls
        page = pages[calls] if calls < len(pages) else []
        calls += 1
        return page

    monkeypatch.setattr(downloader_module, "fetch_binance_klines", fake_fetch)

    dataset = download_ethusdc_1m_candles(60_000, 180_000, tmp_path / "candles.csv")

    assert calls == 2
    assert len(dataset.candles) == 3


def test_downloader_stops_on_empty_page(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(downloader_module, "fetch_binance_klines", lambda *args, **kwargs: [])

    with pytest.raises(ValueError):
        download_ethusdc_1m_candles(60_000, 120_000, tmp_path / "candles.csv")


def test_csv_is_saved(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        downloader_module,
        "fetch_binance_klines",
        lambda *args, **kwargs: [_kline(60_000)],
    )
    output_path = tmp_path / "candles.csv"

    download_ethusdc_1m_candles(60_000, 60_001, output_path)

    assert output_path.is_file()


def test_data_catalog_is_updated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_path = tmp_path / "candles.csv"
    monkeypatch.setattr(
        downloader_module,
        "fetch_binance_klines",
        lambda *args, **kwargs: [_kline(60_000)],
    )

    download_ethusdc_1m_candles(60_000, 60_001, output_path)

    assert load_data_catalog()[0].path == str(output_path)


def test_infinite_loop_protection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        downloader_module,
        "fetch_binance_klines",
        lambda *args, **kwargs: [_kline(60_000)],
    )

    with pytest.raises(RuntimeError):
        download_ethusdc_1m_candles(60_000, 180_000, tmp_path / "candles.csv")


def test_result_is_valid_candle_dataset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        downloader_module,
        "fetch_binance_klines",
        lambda *args, **kwargs: [_kline(60_000)],
    )

    dataset = download_ethusdc_1m_candles(60_000, 60_001, tmp_path / "candles.csv")

    assert dataset.symbol == "ETHUSDC"
    assert dataset.interval == "1m"


def test_no_trading_mode_fields_are_introduced() -> None:
    field_names = {field.name for field in fields(BinanceKline)}

    assert "short" not in field_names
    assert "futures" not in field_names
    assert "margin" not in field_names
    assert "leverage" not in field_names
