from dataclasses import fields
from json import JSONDecodeError

import pytest

import src.ui.backtest_ui_controller as controller_module
from src.backtest.preparation_pipeline import PreparationPipelineResult
from src.data.agg_trade_data_ensure import AggTradeDataEnsureResult
from src.data.backtest_market_data_ensure import BacktestMarketDataEnsureResult
from src.data.candle_data_ensure import CandleDataEnsureResult
from src.data.context_data_ensure import ContextDataEnsureResult
from src.data.exchange_info import ExchangeInfoStatus
from src.data.live_microstructure import LiveMicrostructureStatus
from src.reports.backtest_summary import BacktestSummary
from src.common.runtime_state import RuntimeState
from src.backtest.run_progress import BacktestRunProgress
from src.ui.backtest_ui_controller import (
    BacktestUiResult,
    BacktestUiSettings,
    load_active_backtest_result_for_ui,
    load_latest_completed_backtest_result_for_ui,
    run_backtest_for_ui,
)


@pytest.fixture(autouse=True)
def no_context_download(monkeypatch):
    monkeypatch.setattr(
        controller_module,
        "ensure_all_backtest_market_data_ready",
        lambda progress_callback=None: _market_data_result(),
    )
    monkeypatch.setattr(
        controller_module,
        "ensure_ethusdc_1m_data_ready",
        lambda progress_callback=None: _ensure_result(),
        raising=False,
    )
    monkeypatch.setattr(
        controller_module,
        "ensure_all_context_data_ready",
        lambda progress_callback=None: [],
        raising=False,
    )
    monkeypatch.setattr(
        controller_module,
        "ensure_exchange_info_current",
        lambda: ExchangeInfoStatus("ETHUSDC", "exchange.json", True, False, 1.0, 1, True, True, None),
        raising=False,
    )


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


def _market_data_result(
    success: bool = True,
    candle_count: int = 5,
    message: str | None = None,
) -> BacktestMarketDataEnsureResult:
    primary = _ensure_result(success=success, candle_count=candle_count)
    exchange = ExchangeInfoStatus(
        "ETHUSDC",
        "exchange.json",
        True,
        False,
        1.0,
        1,
        True,
        True,
        None,
    )
    agg_trades = AggTradeDataEnsureResult(
        success=True,
        message="ready",
        partition_count=1,
        first_partition="2026-01",
        last_partition="2026-01",
        latest_complete_date="2026-01-31",
        output_path="data/agg_trades",
        was_updated=False,
        error=None,
    )
    live = LiveMicrostructureStatus(
        success=True,
        message="collector active",
        collector_running=True,
        process_id=1,
        first_sample_time="2026-01-01T00:00:00Z",
        last_sample_time="2026-01-01T00:00:00Z",
        sample_count=1,
        coverage_days=0.0,
        usable_for_backtest=False,
        output_path="data/live_microstructure",
        error=None,
    )
    return BacktestMarketDataEnsureResult(
        success=success,
        message=message or ("ready" if success else primary.message),
        primary_candles=primary,
        context_candles=[],
        exchange_info=exchange,
        agg_trades=agg_trades,
        live_microstructure=live,
        blocking_errors=[] if success else [message or primary.message],
    )


def _pipeline_result(
    summary_path: str | None = "summary.json", **kwargs: object
) -> PreparationPipelineResult:
    return PreparationPipelineResult(
        run_id="run_20260612_220001",
        status="completed" if summary_path else "failed",
        run_type="full_backtest",
        data_preparation_report_path="data.json",
        data_overview_report_path="data_overview.json" if summary_path else None,
        train_blind_split_report_path="split.json",
        activity_first_router_report_path="activity_first_router_report.json" if summary_path else None,
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
        best_training_quote_per_day=0.4,
        target_feasibility_status="target_out_of_reach_current_space",
        target_min_training_ratio=0.2667,
        run_type="full_backtest",
    )


def test_successful_controller_run_returns_success(monkeypatch) -> None:
    monkeypatch.setattr(
        controller_module,
        "ensure_ethusdc_1m_data_ready",
        lambda progress_callback=None: _ensure_result(),
    )
    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", _pipeline_result)
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: _summary())

    result = run_backtest_for_ui()

    assert result.success is True


def test_controller_copies_values_from_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        controller_module,
        "ensure_ethusdc_1m_data_ready",
        lambda progress_callback=None: _ensure_result(),
    )
    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", _pipeline_result)
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: _summary())

    result = run_backtest_for_ui()

    assert result.final_capital == 120.0
    assert result.total_pnl == 20.0
    assert result.trade_count == 1


def test_controller_provides_dashboard_fields(monkeypatch) -> None:
    monkeypatch.setattr(
        controller_module,
        "ensure_ethusdc_1m_data_ready",
        lambda progress_callback=None: _ensure_result(),
    )
    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", _pipeline_result)
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: _summary())

    result = run_backtest_for_ui()

    assert result.symbol == "ETHUSDC"
    assert result.candle_count == 5
    assert result.detected_gaps == 0
    assert result.usable_for_backtest is True
    assert result.report_folder is not None
    assert result.best_training_quote_per_day == 0.4
    assert result.target_feasibility_status == "target_out_of_reach_current_space"


def test_completed_summary_contains_result_values(monkeypatch) -> None:
    monkeypatch.setattr(
        controller_module,
        "ensure_ethusdc_1m_data_ready",
        lambda progress_callback=None: _ensure_result(),
    )
    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", _pipeline_result)
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: _summary())

    result = run_backtest_for_ui()

    assert result.status == "completed"
    assert result.start_capital == 100.0
    assert result.final_capital == 120.0
    assert result.total_pnl_pct == 20.0


def test_failed_pipeline_without_summary_returns_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        controller_module,
        "ensure_ethusdc_1m_data_ready",
        lambda progress_callback=None: _ensure_result(),
    )
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
    monkeypatch.setattr(
        controller_module,
        "ensure_ethusdc_1m_data_ready",
        lambda progress_callback=None: _ensure_result(),
    )

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
        controller_module,
        "ensure_all_backtest_market_data_ready",
        lambda progress_callback=None: _market_data_result(False, 1),
    )
    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", fake_pipeline)

    result = run_backtest_for_ui()

    assert result.success is False
    assert result.candle_count == 1
    assert pipeline_called is False


def test_controller_does_not_start_pipeline_when_context_is_incomplete(monkeypatch) -> None:
    pipeline_called = False

    def fake_pipeline(**kwargs):
        nonlocal pipeline_called
        pipeline_called = True
        return _pipeline_result()

    context = ContextDataEnsureResult(
        "BTCUSDC",
        False,
        "not_enough_data",
        1,
        None,
        False,
        False,
        "btc.csv",
        "not_enough_data",
    )
    market_data = _market_data_result(
        False,
        message="Kontextdaten fehlen: BTCUSDC",
    )
    market_data = BacktestMarketDataEnsureResult(
        **{
            **market_data.__dict__,
            "context_candles": [context],
        }
    )
    monkeypatch.setattr(
        controller_module,
        "ensure_all_backtest_market_data_ready",
        lambda progress_callback=None: market_data,
    )
    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", fake_pipeline)

    result = run_backtest_for_ui()

    assert result.success is False
    assert "Kontextdaten fehlen" in result.message
    assert pipeline_called is False


def test_valid_stakes_are_accepted() -> None:
    for stake in (5.0, 100.0, 1005.0, 100000.0):
        assert BacktestUiSettings(stake_quote_amount=stake).stake_quote_amount == stake


def test_invalid_stake_is_rejected() -> None:
    try:
        BacktestUiSettings(stake_quote_amount=0.0)
    except ValueError as error:
        assert "stake_quote_amount" in str(error)
    else:
        raise AssertionError("invalid stake must fail")


def test_negative_stake_is_rejected() -> None:
    try:
        BacktestUiSettings(stake_quote_amount=-1.0)
    except ValueError as error:
        assert "stake_quote_amount" in str(error)
    else:
        raise AssertionError("negative stake must fail")


def test_non_numeric_stake_is_rejected() -> None:
    try:
        BacktestUiSettings(stake_quote_amount="abc")
    except ValueError as error:
        assert "stake_quote_amount" in str(error)
    else:
        raise AssertionError("non numeric stake must fail")


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
    monkeypatch.setattr(
        controller_module,
        "ensure_ethusdc_1m_data_ready",
        lambda progress_callback=None: _ensure_result(),
    )

    def fake_pipeline(**kwargs):
        captured.update(kwargs)
        return _pipeline_result()

    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", fake_pipeline)
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: _summary())

    run_backtest_for_ui(BacktestUiSettings(stake_quote_amount=500.0, profile="aggressive"))

    assert captured["stake_quote_amount"] == 500.0
    assert captured["profile"] == "aggressive"
    assert captured["run_type"] == "full_backtest"


def test_smoke_settings_forward_short_window_to_same_pipeline(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        controller_module,
        "ensure_ethusdc_1m_data_ready",
        lambda progress_callback=None: _ensure_result(),
    )

    def fake_pipeline(**kwargs):
        captured.update(kwargs)
        return _pipeline_result()

    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", fake_pipeline)
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: BacktestSummary(**{**_summary().__dict__, "run_type": "smoke_test"}))

    result = run_backtest_for_ui(BacktestUiSettings(run_type="smoke_test", blindtest_days=7))

    assert captured["run_type"] == "smoke_test"
    assert captured["blindtest_days"] == 7
    assert captured["training_days"] == 14
    assert result.run_type == "smoke_test"


def test_progress_callback_receives_phases(monkeypatch) -> None:
    events: list[dict] = []

    def fake_ensure(progress_callback=None):
        progress_callback({"phase": "data_ensure", "mode": "already_current"})
        return _market_data_result()

    def fake_pipeline(**kwargs):
        kwargs["progress_callback"]({"phase": "completed", "progress_pct": 100.0})
        return _pipeline_result()

    monkeypatch.setattr(
        controller_module,
        "ensure_all_backtest_market_data_ready",
        fake_ensure,
    )
    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", fake_pipeline)
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: _summary())

    run_backtest_for_ui(progress_callback=events.append)

    phases = [event.get("phase") for event in events]
    assert "data_check_started" in phases
    assert "data_ensure" in phases
    assert "completed" in phases


def test_load_active_backtest_result_uses_runtime_state(monkeypatch) -> None:
    monkeypatch.setattr(
        controller_module,
        "load_runtime_state",
        lambda: RuntimeState(
            active_run_id="run_20260612_220001", status="completed", last_error=None
        ),
    )
    monkeypatch.setattr(
        controller_module,
        "get_run_report_dir",
        lambda run_id: type(
            "FakePath",
            (),
            {
                "__truediv__": lambda self, name: type(
                    "FakeSummaryPath", (), {"exists": lambda self: True, "__str__": lambda self: name}
                )()
            },
        )(),
    )
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: _summary())

    result = load_active_backtest_result_for_ui()

    assert result is not None
    assert result.run_id == "run_20260612_220001"
    assert result.status == "completed"


def test_load_active_backtest_result_falls_back_to_latest_summary_run(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        controller_module,
        "load_runtime_state",
        lambda: RuntimeState(
            active_run_id="run_20260612_230003", status="running", last_error=None
        ),
    )
    reports_dir = tmp_path / "reports" / "backtests"
    (reports_dir / "run_20260612_230001").mkdir(parents=True)
    (reports_dir / "run_20260612_230001" / "backtest_summary.json").write_text("{}", encoding="utf-8")
    (reports_dir / "run_20260612_230002").mkdir()
    (reports_dir / "run_20260612_230002" / "backtest_summary.json").write_text("{}", encoding="utf-8")
    (reports_dir / "run_20260612_230003").mkdir()
    monkeypatch.setattr(controller_module, "BACKTEST_REPORTS_DIR", reports_dir)
    monkeypatch.setattr(controller_module, "get_run_report_dir", lambda run_id: reports_dir / run_id)
    monkeypatch.setattr(
        controller_module,
        "load_backtest_summary",
        lambda run_id: BacktestSummary(**{**_summary().__dict__, "run_id": run_id}),
    )

    result = load_active_backtest_result_for_ui()

    assert result is not None
    assert result.run_id == "run_20260612_230002"
    assert result.status == "completed"


def test_load_latest_completed_backtest_result_ignores_running_active_run(monkeypatch, tmp_path) -> None:
    reports_dir = tmp_path / "reports" / "backtests"
    (reports_dir / "run_20260612_230010").mkdir(parents=True)
    (reports_dir / "run_20260612_230010" / "backtest_summary.json").write_text("{}", encoding="utf-8")
    (reports_dir / "run_20260612_230011").mkdir()
    monkeypatch.setattr(controller_module, "BACKTEST_REPORTS_DIR", reports_dir)
    monkeypatch.setattr(controller_module, "get_run_report_dir", lambda run_id: reports_dir / run_id)
    monkeypatch.setattr(
        controller_module,
        "load_backtest_summary",
        lambda run_id: BacktestSummary(**{**_summary().__dict__, "run_id": run_id}),
    )

    result = load_latest_completed_backtest_result_for_ui()

    assert result is not None
    assert result.run_id == "run_20260612_230010"
    assert result.status == "completed"


def test_load_active_backtest_result_shows_running_run_without_summary(monkeypatch, tmp_path) -> None:
    run_id = "run_20260612_230004"
    reports_dir = tmp_path / "reports" / "backtests"
    run_dir = reports_dir / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "progress.json").write_text(
        '{"run_id":"run_20260612_230004","status":"running","stage":"activity_first_router","progress_pct":75.0,"message":null,"error":null}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        controller_module,
        "load_runtime_state",
        lambda: RuntimeState(active_run_id=run_id, status="running", last_error=None),
    )
    monkeypatch.setattr(controller_module, "BACKTEST_REPORTS_DIR", reports_dir)
    monkeypatch.setattr(controller_module, "get_run_report_dir", lambda active_run_id: reports_dir / active_run_id)
    monkeypatch.setattr(
        controller_module,
        "load_run_progress",
        lambda active_run_id: BacktestRunProgress(active_run_id, "running", "activity_first_router", 75.0, None, None, 300.0, 100.0),
    )
    monkeypatch.setattr(controller_module, "time", lambda: (run_dir / "run_request.json").stat().st_mtime + 300.0)
    (run_dir / "run_request.json").write_text("{}", encoding="utf-8")

    result = load_active_backtest_result_for_ui()

    assert result is not None
    assert result.run_id == run_id
    assert result.status == "running"
    assert "Backtest läuft" in result.message
    assert result.progress_pct == 75.0
    assert result.progress_stage == "activity_first_router"
    assert result.elapsed_seconds == 300.0
    assert result.estimated_remaining_seconds == 100.0
    assert "Rest geschätzt" in result.message


def test_running_progress_json_race_is_ignored_until_next_ui_refresh(monkeypatch) -> None:
    run_id = "run_20260612_230011"
    monkeypatch.setattr(
        controller_module,
        "load_runtime_state",
        lambda: RuntimeState(active_run_id=run_id, status="running", last_error=None),
    )
    monkeypatch.setattr(controller_module, "_load_run_result_if_summary_exists", lambda _: None)
    monkeypatch.setattr(
        controller_module,
        "load_run_progress",
        lambda _: (_ for _ in ()).throw(JSONDecodeError("partial", "", 0)),
    )
    monkeypatch.setattr(controller_module, "load_latest_completed_backtest_result_for_ui", lambda: None)

    assert load_active_backtest_result_for_ui() is None


def test_running_progress_windows_file_lock_is_ignored_until_next_ui_refresh(monkeypatch) -> None:
    run_id = "run_20260612_230012"
    monkeypatch.setattr(
        controller_module,
        "load_runtime_state",
        lambda: RuntimeState(active_run_id=run_id, status="running", last_error=None),
    )
    monkeypatch.setattr(controller_module, "_load_run_result_if_summary_exists", lambda _: None)
    monkeypatch.setattr(
        controller_module,
        "load_run_progress",
        lambda _: (_ for _ in ()).throw(PermissionError("temporarily locked")),
    )
    monkeypatch.setattr(controller_module, "load_latest_completed_backtest_result_for_ui", lambda: None)

    assert load_active_backtest_result_for_ui() is None


def test_load_active_backtest_result_returns_none_without_active_run_or_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        controller_module,
        "load_runtime_state",
        lambda: RuntimeState(active_run_id=None, status="idle", last_error=None),
    )
    monkeypatch.setattr(controller_module, "BACKTEST_REPORTS_DIR", tmp_path / "missing_backtests")

    assert load_active_backtest_result_for_ui() is None


def test_network_error_is_mapped_to_clear_ui_message(monkeypatch) -> None:
    network_error_result = CandleDataEnsureResult(
        success=False,
        message="Binance request error: [WinError 10060] timeout",
        symbol="ETHUSDC",
        interval="1m",
        candle_count=1,
        required_candles=5,
        output_path=None,
        catalog_path=None,
        was_updated=False,
        full_download=False,
        incremental_update=False,
        already_current=False,
        last_open_time=None,
        error="timeout",
    )
    monkeypatch.setattr(
        controller_module,
        "ensure_all_backtest_market_data_ready",
        lambda progress_callback=None: BacktestMarketDataEnsureResult(
            success=False,
            message=network_error_result.message,
            primary_candles=network_error_result,
            context_candles=[],
            exchange_info=ExchangeInfoStatus(
                "ETHUSDC",
                "exchange.json",
                False,
                False,
                None,
                0,
                False,
                False,
                "network error",
            ),
            agg_trades=AggTradeDataEnsureResult(
                False,
                "not checked",
                0,
                None,
                None,
                None,
                "data/agg_trades",
                False,
                "not checked",
            ),
            live_microstructure=LiveMicrostructureStatus(
                False,
                "not checked",
                False,
                None,
                None,
                None,
                0,
                0.0,
                False,
                "data/live_microstructure",
                "not checked",
            ),
            blocking_errors=[network_error_result.message],
        ),
    )

    result = run_backtest_for_ui()

    assert result.success is False
    assert "Binance konnte nicht erreicht werden" in result.message


def test_no_short_futures_margin_or_leverage_fields() -> None:
    field_names = {field.name for field in fields(BacktestUiResult)}

    assert "short" not in field_names
    assert "futures" not in field_names
    assert "margin" not in field_names
    assert "leverage" not in field_names
