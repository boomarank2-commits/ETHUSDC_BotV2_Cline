import inspect

import src.ui.app as app_module


def test_ui_app_is_importable_without_starting_window() -> None:
    assert callable(app_module.main)


def test_main_guard_is_present() -> None:
    source = inspect.getsource(app_module)

    assert 'if __name__ == "__main__"' in source


def test_ui_contains_data_check_button_and_settings() -> None:
    source = inspect.getsource(app_module)

    assert "Daten prüfen/aktualisieren" in source
    assert "100" in source
    assert "200" in source
    assert "500" in source
    assert "1000" in source
    assert "vorsichtig" in source
    assert "aggressiv" in source
