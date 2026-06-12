from src.backtest.run_initializer import initialize_backtest_run
from src.backtest.run_request_io import RUN_REQUEST_FILENAME, load_backtest_run_request
from src.common.report_paths import get_run_report_dir
from src.common.runtime_state import load_runtime_state


def test_initialize_backtest_run_creates_valid_request() -> None:
    request = initialize_backtest_run()

    assert request.symbol == "ETHUSDC"
    assert request.quote_asset == "USDC"
    assert request.exchange == "Binance Spot"
    assert request.training_days == 730
    assert request.blindtest_days == 365


def test_initialized_run_id_starts_with_run_prefix() -> None:
    request = initialize_backtest_run()

    assert request.run_id.startswith("run_")


def test_initialize_backtest_run_creates_run_report_dir() -> None:
    request = initialize_backtest_run()

    assert get_run_report_dir(request.run_id).is_dir()


def test_initialize_backtest_run_writes_run_request_json() -> None:
    request = initialize_backtest_run()

    assert (get_run_report_dir(request.run_id) / RUN_REQUEST_FILENAME).is_file()


def test_initialize_backtest_run_can_load_same_request() -> None:
    request = initialize_backtest_run()

    assert load_backtest_run_request(request.run_id) == request


def test_initialize_backtest_run_sets_runtime_state_to_running() -> None:
    request = initialize_backtest_run()

    runtime_state = load_runtime_state()

    assert runtime_state.active_run_id == request.run_id
    assert runtime_state.status == "running"
    assert runtime_state.last_error is None


def test_initialize_backtest_run_time_budget_can_be_none() -> None:
    request = initialize_backtest_run()

    assert request.time_budget_minutes is None


def test_initialize_backtest_run_time_budget_can_be_positive() -> None:
    request = initialize_backtest_run(time_budget_minutes=30)

    assert request.time_budget_minutes == 30


def test_initialize_backtest_run_forbids_blindtest_learning() -> None:
    request = initialize_backtest_run()

    assert request.allow_blindtest_learning is False


def test_initialize_backtest_run_forbids_early_capital_stop() -> None:
    request = initialize_backtest_run()

    assert request.allow_early_capital_stop is False
