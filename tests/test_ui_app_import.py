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
    assert "Einsatz pro Trade (USDC):" in source
    assert "Stake Preset" not in source
    assert "stake_preset" not in source
    assert "stake_combo" not in source
    assert "vorsichtig" in source
    assert "conservative" in source
    assert "aggressiv" in source
    assert "aggressive" in source


def test_ui_contains_smoke_test_button_and_duration_choices() -> None:
    source = inspect.getsource(app_module)

    assert "Smoke-Test starten" in source
    assert "1 Tag Blindtest" in source
    assert "7 Tage Blindtest" in source
    assert "14 Tage Blindtest" in source
    assert "30 Tage Blindtest" in source


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


def test_ui_loads_active_run_and_shows_data_status_fields() -> None:
    source = inspect.getsource(app_module)

    assert "load_active_backtest_result_for_ui" in source
    assert "Letzten Lauf laden" in source
    assert "Datenart:" in source
    assert "Datenstatus:" in source
    assert "Datenalter:" in source


def test_ui_result_section_is_not_mislabeled_as_buy_hold() -> None:
    source = inspect.getsource(app_module)

    assert "Backtest-Ergebnis (aktuell bevorzugter Report)" in source
    assert "D) Buy-&-Hold Benchmark" not in source


def test_ui_contains_clean_button_and_double_warning() -> None:
    source = inspect.getsource(app_module)

    assert "Alle Daten löschen / Bot clean machen" in source
    assert "Achtung: Hiermit werden alle heruntergeladenen Markt-/Backtestdaten" in source
    assert "Sind Sie 100% sicher?" in source
    assert source.count("messagebox.askyesno") >= 2
    assert "Clean-Zustand: Beim nächsten Backtest werden Daten neu geladen." in source or "result.message" in source
