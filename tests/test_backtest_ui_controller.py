from dataclasses import fields

import src.ui.backtest_ui_controller as controller_module
from src.backtest.preparation_pipeline import PreparationPipelineResult
from src.reports.backtest_summary import BacktestSummary
from src.ui.backtest_ui_controller import BacktestUiResult, run_backtest_for_ui


def _pipeline_result(summary_path: str | None = "summary.json") -> PreparationPipelineResult:
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
    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", _pipeline_result)
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: _summary())

    result = run_backtest_for_ui()

    assert result.success is True


def test_controller_copies_values_from_summary(monkeypatch) -> None:
    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", _pipeline_result)
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: _summary())

    result = run_backtest_for_ui()

    assert result.final_capital == 120.0
    assert result.total_pnl == 20.0
    assert result.trade_count == 1


def test_controller_provides_dashboard_fields(monkeypatch) -> None:
    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", _pipeline_result)
    monkeypatch.setattr(controller_module, "load_backtest_summary", lambda run_id: _summary())

    result = run_backtest_for_ui()

    assert result.symbol == "ETHUSDC"
    assert result.candle_count == 5
    assert result.detected_gaps == 0
    assert result.usable_for_backtest is True
    assert result.report_folder is not None


def test_completed_summary_contains_result_values(monkeypatch) -> None:
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
        "run_backtest_preparation_pipeline",
        lambda: _pipeline_result(summary_path=None),
    )

    result = run_backtest_for_ui()

    assert result.success is False
    assert result.message == "missing summary"
    assert result.report_folder is None


def test_exception_is_caught_as_failure(monkeypatch) -> None:
    def raise_error() -> None:
        raise RuntimeError("missing data_catalog.json")

    monkeypatch.setattr(controller_module, "run_backtest_preparation_pipeline", raise_error)

    result = run_backtest_for_ui()

    assert result.success is False
    assert "data_catalog" in result.message


def test_no_short_futures_margin_or_leverage_fields() -> None:
    field_names = {field.name for field in fields(BacktestUiResult)}

    assert "short" not in field_names
    assert "futures" not in field_names
    assert "margin" not in field_names
    assert "leverage" not in field_names
