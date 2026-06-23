import json
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from src.common.paths import CONFIGS_DIR
from src.common.runtime_state import (
    RUNTIME_STATE_PATH,
    RuntimeState,
    default_runtime_state,
    load_runtime_state,
    save_runtime_state,
)


@contextmanager
def _preserved_runtime_state_file() -> Iterator[None]:
    previous_content = RUNTIME_STATE_PATH.read_text(encoding="utf-8") if RUNTIME_STATE_PATH.exists() else None
    try:
        yield
    finally:
        if previous_content is None:
            if RUNTIME_STATE_PATH.exists():
                RUNTIME_STATE_PATH.unlink()
        else:
            RUNTIME_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            RUNTIME_STATE_PATH.write_text(previous_content, encoding="utf-8")


def test_default_runtime_state_is_idle() -> None:
    state = default_runtime_state()

    assert state.active_run_id is None
    assert state.status == "idle"
    assert state.last_error is None


def test_save_and_load_runtime_state() -> None:
    with _preserved_runtime_state_file():
        state = RuntimeState(
            active_run_id="run_20260612_120000",
            status="running",
            last_error=None,
        )

        save_runtime_state(state)

        assert load_runtime_state() == state


def test_runtime_state_json_is_under_configs_dir() -> None:
    assert RUNTIME_STATE_PATH == CONFIGS_DIR / "runtime_state.json"


def test_saved_runtime_state_json_is_readable() -> None:
    with _preserved_runtime_state_file():
        state = RuntimeState(active_run_id=None, status="completed", last_error=None)

        save_runtime_state(state)
        raw_state = json.loads(RUNTIME_STATE_PATH.read_text(encoding="utf-8"))

        assert raw_state == {
            "active_run_id": None,
            "last_error": None,
            "status": "completed",
        }


def test_invalid_status_is_rejected() -> None:
    with pytest.raises(ValueError):
        RuntimeState(active_run_id=None, status="unknown", last_error=None)


def test_active_run_id_may_be_none_or_valid_run_id() -> None:
    RuntimeState(active_run_id=None, status="idle", last_error=None)
    RuntimeState(active_run_id="run_20260612_120000", status="running", last_error=None)


def test_active_run_id_with_path_traversal_is_rejected() -> None:
    with pytest.raises(ValueError):
        RuntimeState(active_run_id="../unsafe", status="running", last_error=None)
