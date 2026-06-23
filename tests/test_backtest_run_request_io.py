import json

import pytest

from src.backtest.run_request import default_backtest_run_request
from src.backtest.run_request_io import (
    RUN_REQUEST_FILENAME,
    load_backtest_run_request,
    save_backtest_run_request,
)
from src.common.report_paths import get_run_report_dir


def test_save_backtest_run_request_creates_json_in_run_report_dir() -> None:
    request = default_backtest_run_request("run_20260612_150001")

    report_path = save_backtest_run_request(request)

    assert report_path == get_run_report_dir(request.run_id) / RUN_REQUEST_FILENAME
    assert report_path.is_file()


def test_load_backtest_run_request_loads_same_request() -> None:
    request = default_backtest_run_request("run_20260612_150002")

    save_backtest_run_request(request)

    loaded_request = load_backtest_run_request(request.run_id)

    assert loaded_request == request


def test_saved_json_contains_confirmed_request_values() -> None:
    request = default_backtest_run_request("run_20260612_150003")

    report_path = save_backtest_run_request(request)
    raw_request = json.loads(report_path.read_text(encoding="utf-8"))

    assert raw_request["run_id"] == request.run_id
    assert raw_request["symbol"] == "ETHUSDC"
    assert raw_request["quote_asset"] == "USDC"
    assert raw_request["training_days"] == 730
    assert raw_request["blindtest_days"] == 365
    assert raw_request["run_type"] == "full_backtest"


def test_forbidden_trading_modes_remain_false() -> None:
    request = default_backtest_run_request("run_20260612_150004")

    save_backtest_run_request(request)
    loaded_request = load_backtest_run_request(request.run_id)

    assert loaded_request.allow_short is False
    assert loaded_request.allow_futures is False
    assert loaded_request.allow_margin is False
    assert loaded_request.allow_leverage is False


def test_blindtest_learning_remains_false() -> None:
    request = default_backtest_run_request("run_20260612_150005")

    save_backtest_run_request(request)
    loaded_request = load_backtest_run_request(request.run_id)

    assert loaded_request.allow_blindtest_learning is False


def test_early_capital_stop_remains_false() -> None:
    request = default_backtest_run_request("run_20260612_150006")

    save_backtest_run_request(request)
    loaded_request = load_backtest_run_request(request.run_id)

    assert loaded_request.allow_early_capital_stop is False


def test_invalid_run_id_with_path_traversal_is_rejected() -> None:
    with pytest.raises(ValueError):
        load_backtest_run_request("../unsafe")


def test_missing_file_is_handled_as_file_not_found_error() -> None:
    with pytest.raises(FileNotFoundError):
        load_backtest_run_request("run_20260612_159999")
