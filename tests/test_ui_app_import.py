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


def test_ui_loads_active_run_and_shows_concise_data_quality_fields() -> None:
    source = inspect.getsource(app_module)

    assert "load_active_backtest_result_for_ui" in source
    assert "Letzten Lauf laden" in source
    assert "DATENQUALITÄT" in source
    assert "ETHUSDC Candles:" in source
    assert "Datenbereiche:" in source


def test_ui_result_section_is_decision_oriented_and_not_buy_hold() -> None:
    source = inspect.getsource(app_module)

    assert "BACKTEST-ENTSCHEIDUNG" in source
    assert "KERNERGEBNIS" in source
    assert "STABILITÄT" in source
    assert "STRATEGIE-FREIGABE" in source
    assert "D) Buy-&-Hold Benchmark" not in source


def test_ui_result_section_keeps_only_decision_metrics() -> None:
    source = inspect.getsource(app_module)

    assert "Gewinn/Tag:" in source
    assert "Trades:" in source
    assert "Bester Monat:" in source
    assert "Schlechtester Monat:" in source
    assert "NICHT ÜBERNEHMEN" in source
    assert "ZIEL ERREICHT" in source
    assert "Datenart:" not in source
    assert "Datenstatus:" not in source
