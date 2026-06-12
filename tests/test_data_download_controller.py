from dataclasses import fields

import src.ui.data_download_controller as controller_module
from src.data.candle_data_ensure import CandleDataEnsureResult
from src.ui.data_download_controller import (
    DataDownloadUiResult,
    download_required_ethusdc_1m_data_for_ui,
)


def _ensure_result(**overrides: object) -> CandleDataEnsureResult:
    values = {
        "success": True,
        "message": "ok",
        "symbol": "ETHUSDC",
        "interval": "1m",
        "candle_count": 10,
        "required_candles": 5,
        "output_path": "data/candles/ETHUSDC_1m.csv",
        "catalog_path": "configs/data_catalog.json",
        "was_updated": False,
        "full_download": False,
        "incremental_update": False,
        "already_current": True,
        "last_open_time": "2026-01-01T00:00:00Z",
        "error": None,
    }
    values.update(overrides)
    return CandleDataEnsureResult(**values)


def test_controller_uses_central_ensure(monkeypatch) -> None:
    called = False

    def fake_ensure(progress_callback=None):
        nonlocal called
        called = True
        return _ensure_result()

    monkeypatch.setattr(controller_module, "ensure_ethusdc_1m_data_ready", fake_ensure)

    result = download_required_ethusdc_1m_data_for_ui()

    assert called is True
    assert result.success is True


def test_current_data_returns_current_message(monkeypatch) -> None:
    monkeypatch.setattr(
        controller_module,
        "ensure_ethusdc_1m_data_ready",
        lambda progress_callback=None: _ensure_result(),
    )

    result = download_required_ethusdc_1m_data_for_ui()

    assert "bereits aktuell" in result.message


def test_full_download_returns_full_message(monkeypatch) -> None:
    monkeypatch.setattr(
        controller_module,
        "ensure_ethusdc_1m_data_ready",
        lambda progress_callback=None: _ensure_result(
            full_download=True, already_current=False, was_updated=True
        ),
    )

    result = download_required_ethusdc_1m_data_for_ui()

    assert "vollständig neu geladen" in result.message


def test_incremental_update_returns_incremental_message(monkeypatch) -> None:
    monkeypatch.setattr(
        controller_module,
        "ensure_ethusdc_1m_data_ready",
        lambda progress_callback=None: _ensure_result(
            incremental_update=True, already_current=False, was_updated=True
        ),
    )

    result = download_required_ethusdc_1m_data_for_ui()

    assert "inkrementell aktualisiert" in result.message


def test_failed_ensure_returns_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        controller_module,
        "ensure_ethusdc_1m_data_ready",
        lambda progress_callback=None: _ensure_result(
            success=False, message="zu wenig Daten", error="zu wenig Daten"
        ),
    )

    result = download_required_ethusdc_1m_data_for_ui()

    assert result.success is False
    assert "zu wenig Daten" in result.message


def test_no_trading_mode_fields_are_introduced() -> None:
    field_names = {field.name for field in fields(DataDownloadUiResult)}

    assert "trading" not in field_names
    assert "orders" not in field_names
    assert "short" not in field_names
    assert "futures" not in field_names
    assert "margin" not in field_names
    assert "leverage" not in field_names
