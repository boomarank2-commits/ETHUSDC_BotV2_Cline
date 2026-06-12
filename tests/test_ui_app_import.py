import inspect

import src.ui.app as app_module


def test_ui_app_is_importable_without_starting_window() -> None:
    assert callable(app_module.main)


def test_main_guard_is_present() -> None:
    source = inspect.getsource(app_module)

    assert 'if __name__ == "__main__"' in source
