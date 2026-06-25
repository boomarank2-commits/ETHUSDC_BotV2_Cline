import pytest

import src.data.backtest_market_data_ensure as market_module
from src.data.agg_trade_data_ensure import AggTradeDataEnsureResult
from src.data.candle_data_ensure import CandleDataEnsureResult
from src.data.context_data_ensure import ContextDataEnsureResult
from src.data.exchange_info import ExchangeInfoStatus
from src.data.live_microstructure import LiveMicrostructureStatus


def _primary(success: bool = True) -> CandleDataEnsureResult:
    return CandleDataEnsureResult(
        success,
        "ready" if success else "primary missing",
        "ETHUSDC",
        "1m",
        10 if success else 0,
        10,
        "eth.csv",
        "catalog.json",
        False,
        False,
        False,
        success,
        "2026-06-25T00:00:00Z" if success else None,
        None if success else "missing",
    )


def _agg(success: bool = True) -> AggTradeDataEnsureResult:
    return AggTradeDataEnsureResult(
        success,
        "ready" if success else "agg missing",
        1 if success else 0,
        "2026-06" if success else None,
        "2026-06" if success else None,
        "2026-06-23" if success else None,
        "agg",
        False,
        None if success else "missing",
    )


def _live(success: bool = True) -> LiveMicrostructureStatus:
    return LiveMicrostructureStatus(
        success,
        "active" if success else "collector failed",
        success,
        1 if success else None,
        None,
        None,
        0,
        0.0,
        False,
        "live",
        None if success else "failed",
    )


def _patch_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        market_module,
        "ensure_ethusdc_1m_data_ready",
        lambda progress_callback=None: _primary(),
    )
    monkeypatch.setattr(
        market_module,
        "ensure_all_context_data_ready",
        lambda progress_callback=None: [
            ContextDataEnsureResult(
                "BTCUSDC",
                True,
                "ready",
                10,
                "2026-06-25T00:00:00Z",
                False,
                True,
                "btc.csv",
                None,
            )
        ],
    )
    monkeypatch.setattr(
        market_module,
        "ensure_exchange_info_current",
        lambda: ExchangeInfoStatus(
            "ETHUSDC",
            "exchange.json",
            True,
            False,
            1.0,
            1,
            True,
            True,
            None,
        ),
    )
    monkeypatch.setattr(
        market_module,
        "ensure_ethusdc_agg_trade_features_ready",
        lambda progress_callback=None: _agg(),
    )
    monkeypatch.setattr(
        market_module,
        "ensure_live_microstructure_collection_started",
        lambda: _live(),
    )


def test_shared_market_data_ensure_accepts_complete_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_success(monkeypatch)

    result = market_module.ensure_all_backtest_market_data_ready()

    assert result.success is True
    assert result.blocking_errors == []


def test_shared_market_data_ensure_blocks_when_required_source_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_success(monkeypatch)
    monkeypatch.setattr(
        market_module,
        "ensure_ethusdc_agg_trade_features_ready",
        lambda progress_callback=None: _agg(False),
    )

    result = market_module.ensure_all_backtest_market_data_ready()

    assert result.success is False
    assert any("aggTrades" in error for error in result.blocking_errors)
