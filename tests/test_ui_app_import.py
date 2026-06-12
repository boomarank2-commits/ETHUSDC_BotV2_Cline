import inspect

import src.ui.app as app_module


def test_ui_app_is_importable_without_starting_window() -> None:
    assert callable(app_module.main)


def test_main_guard_is_present() -> None:
    source = inspect.getsource(app_module)

    assert 'if __name__ == "__main__"' in source


def test_ui_has_central_backtest_workflow_without_prominent_data_button() -> None:
    source = inspect.getsource(app_module)

    assert "Daten prüfen/aktualisieren" not in source
    assert "download_button" not in source
    assert "Backtest starten" in source


def test_ui_contains_stake_and_profile_settings() -> None:
    source = inspect.getsource(app_module)

    assert "100" in source
    assert "Einsatz pro Trade (USDT):" in source
    assert "Stake Preset" not in source
    assert "stake_preset" not in source
    assert "stake_combo" not in source
    assert "vorsichtig" in source
    assert "conservative" in source
    assert "aggressiv" in source
    assert "aggressive" in source


def test_ui_contains_clear_invalid_stake_message() -> None:
    source = inspect.getsource(app_module)

    assert "muss eine positive Zahl sein" in source
    assert "muss größer als 0 sein" in source


def test_ui_contains_progress_status_fields() -> None:
    source = inspect.getsource(app_module)

    assert "Phase:" in source
    assert "Fortschritt:" in source
    assert "Detail:" in source
    assert "Candles:" in source
