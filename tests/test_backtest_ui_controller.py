from dataclasses import fields

import src.ui.backtest_ui_controller as controller_module
from src.backtest.preparation_pipeline import PreparationPipelineResult
from src.data.candle_data_ensure import CandleDataEnsureResult
from src.reports.backtest_summary import BacktestSummary
from src.ui.backtest_ui_controller import BacktestUiResult, BacktestUiSettings, run_backtest_for_ui


def _ensure_result(success: bool = True, candle_count: int = 5) -> CandleDataEnsureResult:
    return CandleDataEnsureResult(
        success=success,
        message="ready" if success else "Nicht genug ETHUSDC 1m Candles vorhanden",
        symbol="ETHUSDC",
        interval="1m",
        candle_count=candle_count,
        required_candles=5,
        output_path="data/candles/ETHUSDC_1m.csv",
        catalog_path="configs/data_catalog.json",
        was_updated=False,
        full_download=False,
        incremental_update=False,
        already_current=success,
        last_open_time="2026-01-01T00:00:00Z",
        error=None if success else "too few",
    )


def _pipeline_result(
    summary_path: str | None = "summary.json", **kwargs: object
) -> PreparationPipelineResult:
    return PreparationPipelineResult(
        run_id="run_20260612_220001",
        status="completed" if summary_path else "failed",
        data_preparation_report_path="data.json",
        train_blind_split_report_path="split.json",
        buy_hold_benchmark_report_path="benchmark.json" if summary_path else None,
        strategy_v0_report_path="strategy.json" if summary_path else None,
        strategy_v1_report_path="strategy_v1.json" if summary_path else None,
        backtest_summary_path=summary_path,
        progress_path="progress.json",
        error=None if summary_path else "missing summary",
    )


def _summary() -> BacktestSummary:
    return BacktestSummary(
        run_id="run_20260612_220001",
        status="completed",
        symbol="ETHUSDC",
        quote_asset="USDC",
        start_capital=100.0,
        final_capital=120.0,
        total_pnl=20.0,
        total_pnl_pct=20.0,
        trade_count=1,
        training_start="2026-01-01T00:00:00",
        training_end="2026-01-01T00:02:00",
        blindtest_start="2026-01-01T00:03:00",
        blindtest_end="2026-01-01T00:04:00",
        candle_count=5,
        detected_gaps=0,
        usable_for_backtest=True,
        message="completed",
    )


def test_successful_controller_run_returns_success(monkeypatch) -> None:
    monkeypatch.setattr(controller_module, "ensure_ethusdc_1m_data_ready", lambda: _ensure_result())
    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", _pipeline_result)
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: _summary())

    result = run_backtest_for_ui()

    assert result.success is True


def test_controller_copies_values_from_summary(monkeypatch) -> None:
    monkeypatch.setattr(controller_module, "ensure_ethusdc_1m_data_ready", lambda: _ensure_result())
    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", _pipeline_result)
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: _summary())

    result = run_backtest_for_ui()

    assert result.final_capital == 120.0
    assert result.total_pnl == 20.0
    assert result.trade_count == 1


def test_controller_provides_dashboard_fields(monkeypatch) -> None:
    monkeypatch.setattr(controller_module, "ensure_ethusdc_1m_data_ready", lambda: _ensure_result())
    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", _pipeline_result)
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: _summary())

    result = run_backtest_for_ui()

    assert result.symbol == "ETHUSDC"
    assert result.candle_count == 5
    assert result.detected_gaps == 0
    assert result.usable_for_backtest is True
    assert result.report_folder is not None


def test_completed_summary_contains_result_values(monkeypatch) -> None:
    monkeypatch.setattr(controller_module, "ensure_ethusdc_1m_data_ready", lambda: _ensure_result())
    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", _pipeline_result)
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: _summary())

    result = run_backtest_for_ui()

    assert result.status == "completed"
    assert result.start_capital == 100.0
    assert result.final_capital == 120.0
    assert result.total_pnl_pct == 20.0


def test_failed_pipeline_without_summary_returns_failure(monkeypatch) -> None:
    monkeypatch.setattr(controller_module, "ensure_ethusdc_1m_data_ready", lambda: _ensure_result())
    monkeypatch.setattr(
        controller_module,
        "run_backtest_preparation_pipeline",
        lambda **kwargs: _pipeline_result(summary_path=None),
    )

    result = run_backtest_for_ui()

    assert result.success is False
    assert result.message == "missing summary"
    assert result.report_folder is None


def test_exception_is_caught_as_failure(monkeypatch) -> None:
    def raise_error(**kwargs) -> None:
        raise RuntimeError("missing data_catalog.json")

    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", raise_error)
    monkeypatch.setattr(controller_module, "ensure_ethusdc_1m_data_ready", lambda: _ensure_result())

    result = run_backtest_for_ui()

    assert result.success is False
    assert "data_catalog" in result.message


def test_controller_does_not_start_pipeline_when_ensure_has_one_candle(monkeypatch) -> None:
    pipeline_called = False

    def fake_pipeline(**kwargs):
        nonlocal pipeline_called
        pipeline_called = True
        return _pipeline_result()

    monkeypatch.setattr(
        controller_module, "ensure_ethusdc_1m_data_ready", lambda: _ensure_result(False, 1)
    )
    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", fake_pipeline)

    result = run_backtest_for_ui()

    assert result.success is False
    assert result.candle_count == 1
    assert pipeline_called is False


def test_valid_stakes_are_accepted() -> None:
    for stake in (100.0, 200.0, 500.0, 1000.0):
        assert BacktestUiSettings(stake_usdt=stake).stake_usdt == stake


def test_invalid_stake_is_rejected() -> None:
    try:
        BacktestUiSettings(stake_usdt=300.0)
    except ValueError as error:
        assert "stake_usdt" in str(error)
    else:
        raise AssertionError("invalid stake must fail")


def test_valid_profiles_are_accepted() -> None:
    for profile in ("conservative", "normal", "aggressive"):
        assert BacktestUiSettings(profile=profile).profile == profile


def test_invalid_profile_is_rejected() -> None:
    try:
        BacktestUiSettings(profile="wild")
    except ValueError as error:
        assert "profile" in str(error)
    else:
        raise AssertionError("invalid profile must fail")


def test_settings_are_forwarded_to_pipeline(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(controller_module, "ensure_ethusdc_1m_data_ready", lambda: _ensure_result())

    def fake_pipeline(**kwargs):
        captured.update(kwargs)
        return _pipeline_result()

    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", fake_pipeline)
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: _summary())

    run_backtest_for_ui(BacktestUiSettings(stake_usdt=500.0, profile="aggressive"))

    assert captured["stake_usdt"] == 500.0
    assert captured["profile"] == "aggressive"


def test_no_short_futures_margin_or_leverage_fields() -> None:
    field_names = {field.name for field in fields(BacktestUiResult)}

    assert "short" not in field_names
    assert "futures" not in field_names
    assert "margin" not in field_names
    assert "leverage" not in field_names
