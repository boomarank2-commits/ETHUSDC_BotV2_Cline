import pytest
import src.backtest.run_progress as progress_module

from src.backtest.run_progress import (
    PROGRESS_FILENAME,
    BacktestRunProgress,
    default_run_progress,
    load_run_progress,
    save_run_progress,
)
from src.common.report_paths import get_run_report_dir


def test_default_progress_is_initialized() -> None:
    progress = default_run_progress("run_20260612_170001")

    assert progress.status == "initialized"
    assert progress.stage == "initialized"
    assert progress.progress_pct == 0.0


def test_progress_json_is_saved_in_run_report_dir() -> None:
    progress = default_run_progress("run_20260612_170002")

    progress_path = save_run_progress(progress)

    assert progress_path == get_run_report_dir(progress.run_id) / PROGRESS_FILENAME
    assert progress_path.is_file()
    assert not list(progress_path.parent.glob(f"{PROGRESS_FILENAME}.*.tmp"))


def test_progress_save_retries_transient_windows_replace_lock(monkeypatch) -> None:
    progress = default_run_progress("run_20260612_170020")
    original_replace = progress_module.Path.replace
    calls = 0

    def flaky_replace(self, target):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PermissionError("locked by UI refresh")
        return original_replace(self, target)

    monkeypatch.setattr(progress_module, "sleep", lambda _: None)
    monkeypatch.setattr(progress_module.Path, "replace", flaky_replace)

    progress_path = save_run_progress(progress)

    assert calls == 2
    assert progress_path.is_file()
    assert load_run_progress(progress.run_id) == progress


def test_load_run_progress_loads_same_object() -> None:
    progress = default_run_progress("run_20260612_170003")

    save_run_progress(progress)

    assert load_run_progress(progress.run_id) == progress


@pytest.mark.parametrize("progress_pct", [0.0, 100.0])
def test_progress_pct_zero_and_100_are_allowed(progress_pct: float) -> None:
    progress = BacktestRunProgress(
        run_id="run_20260612_170004",
        status="running",
        stage="technical",
        progress_pct=progress_pct,
        message=None,
        error=None,
    )

    assert progress.progress_pct == progress_pct


def test_progress_pct_below_zero_is_rejected() -> None:
    with pytest.raises(ValueError):
        BacktestRunProgress("run_20260612_170005", "running", "technical", -0.1, None, None)


def test_progress_pct_above_100_is_rejected() -> None:
    with pytest.raises(ValueError):
        BacktestRunProgress("run_20260612_170006", "running", "technical", 100.1, None, None)


def test_invalid_run_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        default_run_progress("../unsafe")


def test_invalid_status_is_rejected() -> None:
    with pytest.raises(ValueError):
        BacktestRunProgress("run_20260612_170007", "unknown", "technical", 0.0, None, None)


def test_missing_file_is_file_not_found_error() -> None:
    with pytest.raises(FileNotFoundError):
        load_run_progress("run_20260612_179999")
