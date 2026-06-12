import re

import pytest

from src.common.paths import REPORTS_DIR
from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.common.run_identity import create_run_id


def test_run_id_starts_with_run_prefix() -> None:
    run_id = create_run_id()

    assert run_id.startswith("run_")


def test_run_id_contains_no_spaces() -> None:
    run_id = create_run_id()

    assert " " not in run_id


def test_run_id_contains_only_letters_numbers_and_underscores() -> None:
    run_id = create_run_id()

    assert re.fullmatch(r"[A-Za-z0-9_]+", run_id)


def test_report_path_is_under_backtest_reports_dir() -> None:
    run_id = "run_20260612_120000"

    report_dir = get_run_report_dir(run_id)

    assert report_dir == REPORTS_DIR / "backtests" / run_id


def test_ensure_run_report_dir_creates_directory() -> None:
    run_id = "run_20260612_120001"

    report_dir = ensure_run_report_dir(run_id)

    assert report_dir.is_dir()


def test_invalid_run_id_with_path_traversal_is_rejected() -> None:
    with pytest.raises(ValueError):
        get_run_report_dir("../unsafe")
