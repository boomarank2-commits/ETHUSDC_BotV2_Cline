from dataclasses import fields
from pathlib import Path

import pytest

import src.data.binance_candle_downloader as downloader_module
from src.data.binance_candle_downloader import (
    binance_kline_to_candle,
    download_ethusdc_1m_candles,
    update_ethusdc_1m_candles,
)
from src.data.binance_kline_client import BinanceKline
from src.data.candle_csv_io import load_candle_dataset_from_csv, save_candle_dataset_to_csv
from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle
from src.data.data_catalog import load_data_catalog


def _kline(open_time_ms: int, close: float = 105.0) -> BinanceKline:
    return BinanceKline(open_time_ms, 100.0, 110.0, 90.0, close, 1.0)


def _dataset(open_times: list[str]) -> CandleDataset:
    return CandleDataset(
        "ETHUSDC",
        "1m",
        [Candle(open_time, 100.0, 110.0, 90.0, 105.0, 1.0) for open_time in open_times],
    )


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


def test_progress_callback_is_called_on_paginated_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pages = [[_kline(60_000), _kline(120_000)], [_kline(180_000)]]
    calls = 0
    progress_events: list[dict] = []

    def fake_fetch(*args: object, **kwargs: object) -> list[BinanceKline]:
        nonlocal calls
        page = pages[calls] if calls < len(pages) else []
        calls += 1
        return page

    monkeypatch.setattr(downloader_module, "fetch_binance_klines", fake_fetch)

    download_ethusdc_1m_candles(
        60_000,
        180_000,
        tmp_path / "candles.csv",
        progress_callback=progress_events.append,
    )

    assert len(progress_events) == 2
    assert progress_events[0]["retry_attempt"] == 0
    assert progress_events[0]["max_retries"] == downloader_module.MAX_RETRIES
    assert "message" in progress_events[0]


def test_progress_pct_is_between_zero_and_100(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    progress_events: list[dict] = []
    monkeypatch.setattr(
        downloader_module,
        "fetch_binance_klines",
        lambda *args, **kwargs: [_kline(60_000)],
    )

    download_ethusdc_1m_candles(
        60_000,
        60_001,
        tmp_path / "candles.csv",
        progress_callback=progress_events.append,
    )

    assert 0 <= progress_events[0]["progress_pct"] <= 100


def test_loaded_candles_increase_in_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pages = [[_kline(60_000)], [_kline(120_000)]]
    calls = 0
    progress_events: list[dict] = []

    def fake_fetch(*args: object, **kwargs: object) -> list[BinanceKline]:
        nonlocal calls
        page = pages[calls] if calls < len(pages) else []
        calls += 1
        return page

    monkeypatch.setattr(downloader_module, "fetch_binance_klines", fake_fetch)

    download_ethusdc_1m_candles(
        60_000,
        120_000,
        tmp_path / "candles.csv",
        progress_callback=progress_events.append,
    )

    assert progress_events[1]["loaded_candles"] > progress_events[0]["loaded_candles"]


def test_without_progress_callback_behavior_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        downloader_module,
        "fetch_binance_klines",
        lambda *args, **kwargs: [_kline(60_000)],
    )

    dataset = download_ethusdc_1m_candles(60_000, 60_001, tmp_path / "candles.csv")

    assert len(dataset.candles) == 1


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


def test_missing_csv_triggers_full_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    progress_events: list[dict] = []
    monkeypatch.setattr(downloader_module, "_utc_now_ms", lambda: 120_000)
    monkeypatch.setattr(
        downloader_module,
        "fetch_binance_klines",
        lambda *args, **kwargs: [_kline(60_000), _kline(120_000)],
    )

    dataset = update_ethusdc_1m_candles(
        tmp_path / "candles.csv",
        required_candles=1,
        safety_days=0,
        progress_callback=progress_events.append,
    )

    assert len(dataset.candles) == 2
    assert progress_events[0]["mode"] == "full_download"


def test_current_csv_does_not_download(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_path = tmp_path / "candles.csv"
    save_candle_dataset_to_csv(_dataset(["1970-01-01T00:01:00Z"]), output_path)
    monkeypatch.setattr(downloader_module, "_utc_now_ms", lambda: 60_000)

    def fail_fetch(*args: object, **kwargs: object) -> list[BinanceKline]:
        raise AssertionError("download should not be called")

    monkeypatch.setattr(downloader_module, "fetch_binance_klines", fail_fetch)

    dataset = update_ethusdc_1m_candles(output_path, required_candles=1, safety_days=0)

    assert len(dataset.candles) == 1


def test_outdated_csv_downloads_only_missing_candles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "candles.csv"
    save_candle_dataset_to_csv(_dataset(["1970-01-01T00:01:00Z"]), output_path)
    captured_start_times: list[int] = []
    monkeypatch.setattr(downloader_module, "_utc_now_ms", lambda: 180_000)

    def fake_fetch(*args: object, **kwargs: object) -> list[BinanceKline]:
        captured_start_times.append(kwargs["start_time_ms"])
        return [_kline(120_000), _kline(180_000)]

    monkeypatch.setattr(downloader_module, "fetch_binance_klines", fake_fetch)

    dataset = update_ethusdc_1m_candles(output_path, required_candles=1, safety_days=0)

    assert captured_start_times == [120_000]
    assert len(dataset.candles) == 3


def test_update_prevents_duplicate_open_time(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "candles.csv"
    save_candle_dataset_to_csv(_dataset(["1970-01-01T00:01:00Z"]), output_path)
    monkeypatch.setattr(downloader_module, "_utc_now_ms", lambda: 120_000)
    monkeypatch.setattr(
        downloader_module,
        "fetch_binance_klines",
        lambda *args, **kwargs: [_kline(60_000), _kline(120_000)],
    )

    dataset = update_ethusdc_1m_candles(output_path, required_candles=1, safety_days=0)
    open_times = [candle.open_time for candle in dataset.candles]

    assert len(open_times) == len(set(open_times))


def test_update_result_remains_sorted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_path = tmp_path / "candles.csv"
    save_candle_dataset_to_csv(_dataset(["1970-01-01T00:01:00Z"]), output_path)
    monkeypatch.setattr(downloader_module, "_utc_now_ms", lambda: 180_000)
    monkeypatch.setattr(
        downloader_module,
        "fetch_binance_klines",
        lambda *args, **kwargs: [_kline(180_000), _kline(120_000)],
    )

    dataset = update_ethusdc_1m_candles(output_path, required_candles=1, safety_days=0)
    open_times = [candle.open_time for candle in dataset.candles]

    assert open_times == sorted(open_times)


def test_update_catalog_is_updated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_path = tmp_path / "candles.csv"
    save_candle_dataset_to_csv(_dataset(["1970-01-01T00:01:00Z"]), output_path)
    monkeypatch.setattr(downloader_module, "_utc_now_ms", lambda: 60_000)

    update_ethusdc_1m_candles(output_path, required_candles=1, safety_days=0)

    assert load_data_catalog()[0].path == str(output_path)


def test_update_progress_contains_incremental_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "candles.csv"
    save_candle_dataset_to_csv(_dataset(["1970-01-01T00:01:00Z"]), output_path)
    progress_events: list[dict] = []
    monkeypatch.setattr(downloader_module, "_utc_now_ms", lambda: 120_000)
    monkeypatch.setattr(
        downloader_module,
        "fetch_binance_klines",
        lambda *args, **kwargs: [_kline(120_000)],
    )

    update_ethusdc_1m_candles(
        output_path,
        required_candles=1,
        safety_days=0,
        progress_callback=progress_events.append,
    )

    assert progress_events[0]["mode"] == "incremental_update"


def test_retry_succeeds_after_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_path = tmp_path / "candles.csv"
    calls = 0
    progress_events: list[dict] = []

    def fake_fetch(*args: object, **kwargs: object) -> list[BinanceKline]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("Binance request error: timeout")
        return [_kline(60_000)]

    monkeypatch.setattr(downloader_module, "fetch_binance_klines", fake_fetch)

    dataset = download_ethusdc_1m_candles(
        60_000,
        60_001,
        output_path,
        progress_callback=progress_events.append,
    )

    assert calls == 2
    assert len(dataset.candles) == 1
    assert any(event["retry_attempt"] == 1 for event in progress_events)


def test_retry_failure_keeps_saved_candles(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_path = tmp_path / "candles.csv"
    calls = 0

    def fake_fetch(*args: object, **kwargs: object) -> list[BinanceKline]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return [_kline(60_000)]
        raise RuntimeError("Binance request error: timeout")

    monkeypatch.setattr(downloader_module, "fetch_binance_klines", fake_fetch)

    with pytest.raises(RuntimeError, match="timeout"):
        download_ethusdc_1m_candles(60_000, 120_000, output_path)

    saved = load_candle_dataset_from_csv(output_path)
    assert len(saved.candles) == 1


def test_resume_partial_download_starts_after_existing_last_candle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "candles.csv"
    save_candle_dataset_to_csv(_dataset(["1970-01-01T00:01:00Z"]), output_path)
    captured_starts: list[int] = []
    progress_events: list[dict] = []

    def fake_fetch(*args: object, **kwargs: object) -> list[BinanceKline]:
        captured_starts.append(kwargs["start_time_ms"])
        return [_kline(120_000)]

    monkeypatch.setattr(downloader_module, "fetch_binance_klines", fake_fetch)

    dataset = download_ethusdc_1m_candles(
        60_000,
        120_000,
        output_path,
        progress_callback=progress_events.append,
    )

    assert captured_starts == [120_000]
    assert len(dataset.candles) == 2
    assert progress_events[-1]["mode"] == "resume_partial_download"
