from dataclasses import fields
from datetime import UTC, datetime

import pytest

import src.ui.data_download_controller as controller_module
from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle
from src.data.train_blind_split import REQUIRED_CANDLE_COUNT
from src.ui.data_download_controller import (
    DOWNLOAD_BUFFER_DAYS,
    DataDownloadUiResult,
    _calculate_download_window_ms,
    download_required_ethusdc_1m_data_for_ui,
)


def _dataset() -> CandleDataset:
    return CandleDataset(
        "ETHUSDC",
        "1m",
        [Candle("2026-01-01T00:00:00Z", 100.0, 110.0, 90.0, 105.0, 1.0)],
    )


def test_successful_download_controller_returns_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        controller_module,
        "download_ethusdc_1m_candles",
        lambda **kwargs: _dataset(),
    )

    result = download_required_ethusdc_1m_data_for_ui()

    assert result.success is True
    assert result.candle_count == 1


def test_download_window_contains_required_count_plus_buffer() -> None:
    start_time_ms, end_time_ms = _calculate_download_window_ms(datetime(2026, 1, 1, tzinfo=UTC))

    minutes = (end_time_ms - start_time_ms) // 60_000
    assert minutes >= REQUIRED_CANDLE_COUNT + DOWNLOAD_BUFFER_DAYS * 24 * 60


def test_downloader_is_called_with_default_ethusdc_1m_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_download(**kwargs: object) -> CandleDataset:
        captured.update(kwargs)
        return _dataset()

    monkeypatch.setattr(controller_module, "download_ethusdc_1m_candles", fake_download)

    download_required_ethusdc_1m_data_for_ui()

    assert captured["output_path"] == controller_module.DEFAULT_BINANCE_CANDLE_PATH
    assert captured["end_time_ms"] > captured["start_time_ms"]


def test_downloader_exception_returns_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_download(**kwargs: object) -> None:
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(controller_module, "download_ethusdc_1m_candles", fake_download)

    result = download_required_ethusdc_1m_data_for_ui()

    assert result.success is False
    assert "network unavailable" in result.message


def test_no_trading_mode_fields_are_introduced() -> None:
    field_names = {field.name for field in fields(DataDownloadUiResult)}

    assert "trading" not in field_names
    assert "orders" not in field_names
    assert "short" not in field_names
    assert "futures" not in field_names
    assert "margin" not in field_names
    assert "leverage" not in field_names
