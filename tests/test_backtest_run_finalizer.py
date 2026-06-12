import pytest

from src.backtest.run_finalizer import mark_backtest_run_completed, mark_backtest_run_failed
from src.common.report_paths import get_run_report_dir
from src.common.runtime_state import load_runtime_state


def test_completed_sets_runtime_state_to_completed() -> None:
    run_id = "run_20260612_160001"

    mark_backtest_run_completed(run_id)
    runtime_state = load_runtime_state()

    assert runtime_state.active_run_id == run_id
    assert runtime_state.status == "completed"


def test_completed_sets_last_error_to_none() -> None:
    run_id = "run_20260612_160002"

    mark_backtest_run_completed(run_id)
    runtime_state = load_runtime_state()

    assert runtime_state.last_error is None


def test_failed_sets_runtime_state_to_failed() -> None:
    run_id = "run_20260612_160003"

    mark_backtest_run_failed(run_id, "technical failure")
    runtime_state = load_runtime_state()

    assert runtime_state.active_run_id == run_id
    assert runtime_state.status == "failed"


def test_failed_saves_last_error() -> None:
    run_id = "run_20260612_160004"

    mark_backtest_run_failed(run_id, "technical failure")
    runtime_state = load_runtime_state()

    assert runtime_state.last_error == "technical failure"


def test_empty_error_message_is_rejected() -> None:
    with pytest.raises(ValueError):
        mark_backtest_run_failed("run_20260612_160005", "")


def test_invalid_run_id_with_path_traversal_is_rejected() -> None:
    with pytest.raises(ValueError):
        mark_backtest_run_completed("../unsafe")


def test_run_report_dir_exists_after_completed() -> None:
    run_id = "run_20260612_160006"

    mark_backtest_run_completed(run_id)

    assert get_run_report_dir(run_id).is_dir()


def test_run_report_dir_exists_after_failed() -> None:
    run_id = "run_20260612_160007"

    mark_backtest_run_failed(run_id, "technical failure")

    assert get_run_report_dir(run_id).is_dir()
