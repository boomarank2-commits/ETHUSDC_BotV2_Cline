import src.data.data_overview as overview_module
from src.data.candle_quality import CandleQualityReport
from src.data.data_overview import build_data_overview_report, load_data_overview_report, save_data_overview_report
from src.data.exchange_info import ExchangeInfoStatus


def _quality() -> CandleQualityReport:
    return CandleQualityReport(
        symbol="ETHUSDC",
        interval="1m",
        candle_count=10,
        first_open_time="2026-01-01T00:00:00Z",
        last_open_time="2026-01-01T00:09:00Z",
        duplicate_open_times=0,
        sorted_ascending=True,
        detected_gaps=0,
        expected_min_candles=10,
        has_required_lookback=True,
    )


def test_data_overview_marks_ethusdc_candles_as_used(monkeypatch) -> None:
    monkeypatch.setattr(overview_module, "build_local_candle_quality_from_catalog", lambda *args: _quality())
    monkeypatch.setattr(
        overview_module,
        "ensure_exchange_info_current",
        lambda: ExchangeInfoStatus("ETHUSDC", "exchange.json", True, False, 1.0, 1, True, False, None),
    )

    report = build_data_overview_report("run_20260613_080001")

    ethusdc = next(area for area in report.areas if area.data_kind == "ethusdc_klines_1m")
    exchange_info = next(area for area in report.areas if area.data_kind == "exchange_info")
    btc = next(area for area in report.areas if area.data_kind == "btcusdc_klines_1m")
    ethusdt = next(area for area in report.areas if area.data_kind == "ethusdt_klines_1m")
    assert ethusdc.used_in_backtest is True
    assert exchange_info.usable_for_backtest is True
    assert exchange_info.used_in_backtest is True
    assert btc.used_in_backtest is True
    assert ethusdt.usable_for_backtest is True
    assert ethusdt.used_in_backtest is False


def test_data_overview_save_and_load(monkeypatch) -> None:
    monkeypatch.setattr(overview_module, "build_local_candle_quality_from_catalog", lambda *args: _quality())
    monkeypatch.setattr(
        overview_module,
        "ensure_exchange_info_current",
        lambda: ExchangeInfoStatus("ETHUSDC", "exchange.json", True, False, 1.0, 1, True, False, None),
    )
    report = build_data_overview_report("run_20260613_080002")

    save_data_overview_report(report)

    assert load_data_overview_report(report.run_id) == report
