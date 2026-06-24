from src.data.candle_schema import Candle
from src.data.train_blind_split import TrainBlindSplit
from src.router.activity_first_router_report import build_activity_first_router_report


def _candle(index: int) -> Candle:
    base = 100.0 + index * 0.08
    if index % 17 == 0:
        base -= 1.2
    if index % 19 == 0:
        base += 1.4
    return Candle(
        open_time=f"2026-01-01T{index // 60:02d}:{index % 60:02d}:00Z",
        open=base,
        high=base + 0.8,
        low=base - 0.8,
        close=base + (0.2 if index % 3 else -0.1),
        volume=10.0 + index,
    )


def _flat_candle(index: int) -> Candle:
    return Candle(
        open_time=f"2026-01-01T{index // 60:02d}:{index % 60:02d}:00Z",
        open=100.0,
        high=100.0,
        low=100.0,
        close=100.0,
        volume=10.0,
    )


def _split(count: int = 420) -> TrainBlindSplit:
    candles = [_candle(index) for index in range(count)]
    training = candles[:300]
    blindtest = candles[300:]
    return TrainBlindSplit(
        symbol="ETHUSDC",
        interval="1m",
        training_candles=training,
        blindtest_candles=blindtest,
        training_start=training[0].open_time,
        training_end=training[-1].open_time,
        blindtest_start=blindtest[0].open_time,
        blindtest_end=blindtest[-1].open_time,
    )


def _flat_split(count: int = 420) -> TrainBlindSplit:
    candles = [_flat_candle(index) for index in range(count)]
    training = candles[:300]
    blindtest = candles[300:]
    return TrainBlindSplit(
        symbol="ETHUSDC",
        interval="1m",
        training_candles=training,
        blindtest_candles=blindtest,
        training_start=training[0].open_time,
        training_end=training[-1].open_time,
        blindtest_start=blindtest[0].open_time,
        blindtest_end=blindtest[-1].open_time,
    )


def test_activity_first_router_builds_required_entry_families() -> None:
    report = build_activity_first_router_report("run_test_activity_first", _split())

    families = {
        candidate["strategy_family"]
        for candidate in (
            report.best_activity_candidate,
            report.best_edge_candidate,
            report.best_balanced_candidate,
            report.best_target_candidate,
        )
        if candidate is not None
    }

    assert report.router_name == "activity_first_router"
    assert report.candidate_count >= 60
    assert report.setup_test_count == report.candidate_count
    assert report.candidate_space_status in {
        "trade_allowed_found",
        "trade_allowed_blocked",
        "edge_after_fees_failed",
        "target_edge_missing",
        "target_activity_missing",
        "no_active_candidates",
    }
    assert families


def test_activity_first_router_report_contains_diagnostics_even_without_target() -> None:
    report = build_activity_first_router_report("run_test_activity_diagnostics", _split())

    rejection_counts = report.rejection_summary["rejection_counts"]

    assert "best_activity_candidate" in report.rejection_summary
    assert "best_edge_candidate" in report.rejection_summary
    assert "best_balanced_candidate" in report.rejection_summary
    assert "best_target_candidate" in report.rejection_summary
    assert "rejected_by_activity" in rejection_counts
    assert report.target_quote_per_day == 3.0
    assert report.router_artifact["legacy_cluster_router_used"] is False


def test_eth_specific_regime_diagnostics_are_reported() -> None:
    report = build_activity_first_router_report("run_test_eth_regime_diagnostics", _split(700))

    diagnostics = report.rejection_summary["eth_regime_diagnostics"]
    pass_names = {row["pass_name"] for row in report.rejection_summary["search_pass_summary"]}

    assert report.router_artifact["eth_specific_strategy_scope"] is True
    assert report.router_artifact["candidate_generation_version"] == "activity_first_v6_multi_candidate_pool"
    assert "eth_regime_discovery" in pass_names
    assert diagnostics["scope"] == "ETHUSDC-only training diagnostics"
    assert diagnostics["trigger_forward_return_diagnostics"]
    assert "historical orderbook depth" in diagnostics["missing_live_context"]


def test_no_trade_allowed_candidate_is_diagnostic_only() -> None:
    report = build_activity_first_router_report("run_test_activity_no_allowed", _flat_split())

    assert report.trade_allowed_setup_count == 0
    assert report.selected_candidate_count == 0
    assert report.selected_setups == []
    assert report.blindtest_trade_count == 0
    assert report.blindtest_total_net_pnl == 0.0
    assert report.blindtest_final_capital_reference == report.start_capital_reference
    assert report.router_artifact["diagnostic_only"] is True
    assert report.router_artifact["blindtest_strategy_executed"] is False
