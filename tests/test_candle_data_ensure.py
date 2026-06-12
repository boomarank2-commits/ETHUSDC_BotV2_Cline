from pathlib import Path

import pytest

import src.data.candle_data_ensure as ensure_module
from src.data.candle_csv_io import load_candle_dataset_from_csv, save_candle_dataset_to_csv
from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle


def _candle(index: int) -> Candle:
    return Candle(f"2026-01-01T00:{index:02d}:00Z", 100.0, 101.0, 99.0, 100.0, 1.0)


def _dataset(count: int) -> CandleDataset:
    return CandleDataset("ETHUSDC", "1m", [_candle(index) for index in range(count)])


@pytest.fixture()
def fast_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    target_path = tmp_path / "ETHUSDC_1m.csv"
    monkeypatch.setattr(ensure_module, "DEFAULT_BINANCE_CANDLE_PATH", target_path)
    monkeypatch.setattr(ensure_module, "REQUIRED_CANDLE_COUNT", 5)
    monkeypatch.setattr(ensure_module, "_utc_now_ms", lambda: 1_000_000_000)
    return target_path


def test_missing_csv_triggers_full_download(
    monkeypatch: pytest.MonkeyPatch, fast_paths: Path
) -> None:
    called = False

    def fake_download(**kwargs):
        nonlocal called
        called = True
        save_candle_dataset_to_csv(_dataset(5), kwargs["output_path"])
        return _dataset(5)

    monkeypatch.setattr(ensure_module, "download_ethusdc_1m_candles", fake_download)

    result = ensure_module.ensure_ethusdc_1m_data_ready()

    assert called is True
    assert result.success is True
    assert result.full_download is True


def test_complete_current_csv_does_not_download(
    monkeypatch: pytest.MonkeyPatch, fast_paths: Path
) -> None:
    save_candle_dataset_to_csv(_dataset(5), fast_paths)
    monkeypatch.setattr(ensure_module, "_is_current", lambda last_open_time: True)

    def fail_download(**kwargs):
        raise AssertionError("download must not run")

    monkeypatch.setattr(ensure_module, "download_ethusdc_1m_candles", fail_download)
    monkeypatch.setattr(ensure_module, "update_ethusdc_1m_candles", fail_download)

    result = ensure_module.ensure_ethusdc_1m_data_ready()

    assert result.success is True
    assert result.already_current is True
    assert result.was_updated is False


def test_complete_outdated_csv_triggers_incremental_update(
    monkeypatch: pytest.MonkeyPatch, fast_paths: Path
) -> None:
    save_candle_dataset_to_csv(_dataset(5), fast_paths)
    monkeypatch.setattr(ensure_module, "_is_current", lambda last_open_time: False)
    called = False

    def fake_update(**kwargs):
        nonlocal called
        called = True
        save_candle_dataset_to_csv(_dataset(6), kwargs["output_path"])
        return load_candle_dataset_from_csv(kwargs["output_path"])

    monkeypatch.setattr(ensure_module, "update_ethusdc_1m_candles", fake_update)

    result = ensure_module.ensure_ethusdc_1m_data_ready()

    assert called is True
    assert result.incremental_update is True
    assert result.candle_count == 6


def test_incomplete_csv_rebuilds_instead_of_continuing(
    monkeypatch: pytest.MonkeyPatch, fast_paths: Path
) -> None:
    save_candle_dataset_to_csv(_dataset(1), fast_paths)
    called = False

    def fake_download(**kwargs):
        nonlocal called
        called = True
        save_candle_dataset_to_csv(_dataset(5), kwargs["output_path"])
        return _dataset(5)

    monkeypatch.setattr(ensure_module, "download_ethusdc_1m_candles", fake_download)

    result = ensure_module.ensure_ethusdc_1m_data_ready()

    assert called is True
    assert result.success is True
    assert result.full_download is True
    assert "neu aufgebaut" in result.message


def test_incomplete_csv_failed_rebuild_stays_failed(
    monkeypatch: pytest.MonkeyPatch, fast_paths: Path
) -> None:
    save_candle_dataset_to_csv(_dataset(1), fast_paths)

    def fake_download(**kwargs):
        save_candle_dataset_to_csv(_dataset(1), kwargs["output_path"])
        return _dataset(1)

    monkeypatch.setattr(ensure_module, "download_ethusdc_1m_candles", fake_download)

    result = ensure_module.ensure_ethusdc_1m_data_ready()

    assert result.success is False
    assert result.candle_count == 1
    assert "Backtest wurde nicht gestartet" in result.message
