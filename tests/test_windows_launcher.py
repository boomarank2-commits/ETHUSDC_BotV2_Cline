from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_PATH = PROJECT_ROOT / "ETHUSDC_BotV2_UI_starten.bat"
README_PATH = PROJECT_ROOT / "README.md"


def test_windows_launcher_exists() -> None:
    assert LAUNCHER_PATH.is_file()


def test_windows_launcher_starts_ui_module() -> None:
    content = LAUNCHER_PATH.read_text(encoding="utf-8")

    assert "python -m src.ui.app" in content


def test_windows_launcher_changes_to_project_folder() -> None:
    content = LAUNCHER_PATH.read_text(encoding="utf-8").lower()

    assert "cd /d" in content
    assert "%~dp0" in content


def test_windows_launcher_keeps_window_open_on_error() -> None:
    content = LAUNCHER_PATH.read_text(encoding="utf-8").lower()

    assert "pause" in content


def test_readme_contains_ui_start_hint() -> None:
    content = README_PATH.read_text(encoding="utf-8")

    assert "UI starten" in content
    assert "ETHUSDC_BotV2_UI_starten.bat" in content
    assert "python -m src.ui.app" in content
