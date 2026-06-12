import pytest

from src.backtest.run_request import BacktestRunRequest, default_backtest_run_request


def _valid_request(**overrides: object) -> BacktestRunRequest:
    values = {
        "run_id": "run_20260612_140000",
        "symbol": "ETHUSDC",
        "quote_asset": "USDC",
        "exchange": "Binance Spot",
        "start_capital": 100.0,
        "training_days": 730,
        "blindtest_days": 365,
        "time_budget_minutes": None,
        "allow_short": False,
        "allow_futures": False,
        "allow_margin": False,
        "allow_leverage": False,
        "allow_blindtest_learning": False,
        "allow_early_capital_stop": False,
    }
    values.update(overrides)
    return BacktestRunRequest(**values)


def test_default_request_is_valid() -> None:
    request = default_backtest_run_request("run_20260612_140001")

    assert request.run_id == "run_20260612_140001"


def test_default_request_contains_confirmed_market_basis() -> None:
    request = default_backtest_run_request("run_20260612_140002")

    assert request.symbol == "ETHUSDC"
    assert request.quote_asset == "USDC"
    assert request.exchange == "Binance Spot"


def test_default_request_contains_training_and_blindtest_windows() -> None:
    request = default_backtest_run_request("run_20260612_140003")

    assert request.training_days == 730
    assert request.blindtest_days == 365


def test_start_capital_is_positive() -> None:
    request = default_backtest_run_request("run_20260612_140004")

    assert request.start_capital > 0


def test_time_budget_minutes_may_be_none() -> None:
    request = _valid_request(time_budget_minutes=None)

    assert request.time_budget_minutes is None


def test_time_budget_minutes_may_be_positive() -> None:
    request = _valid_request(time_budget_minutes=30)

    assert request.time_budget_minutes == 30


def test_invalid_run_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        _valid_request(run_id="../unsafe")


def test_wrong_symbol_is_rejected() -> None:
    with pytest.raises(ValueError):
        _valid_request(symbol="BTCUSDC")


@pytest.mark.parametrize(
    "field_name",
    ["allow_short", "allow_futures", "allow_margin", "allow_leverage"],
)
def test_short_futures_margin_and_leverage_true_are_rejected(field_name: str) -> None:
    with pytest.raises(ValueError):
        _valid_request(**{field_name: True})


def test_blindtest_learning_true_is_rejected() -> None:
    with pytest.raises(ValueError):
        _valid_request(allow_blindtest_learning=True)


def test_early_capital_stop_true_is_rejected() -> None:
    with pytest.raises(ValueError):
        _valid_request(allow_early_capital_stop=True)
