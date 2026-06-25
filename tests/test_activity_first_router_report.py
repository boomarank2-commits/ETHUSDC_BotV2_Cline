import src.router.activity_first_router_report as router_report_module
from src.data.derived_timeframes import (
    DerivedTimeframeFeatureBuildResult,
    build_closed_timeframe_feature_series,
)
from src.data.candle_schema import Candle
from src.data.train_blind_split import TrainBlindSplit
from src.router import _learn_htf_filter_candidates
from src.router.activity_first_router_report import (
    ActivityFirstCandidate,
    ActivityFirstSimulationResult,
    ActivityFirstTrade,
    _TrainingEvaluation,
)
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
    htf_analysis = report.rejection_summary["derived_timeframe_training_edge_analysis"]

    assert "best_activity_candidate" in report.rejection_summary
    assert "best_edge_candidate" in report.rejection_summary
    assert "best_balanced_candidate" in report.rejection_summary
    assert "best_target_candidate" in report.rejection_summary
    assert "rejected_by_activity" in rejection_counts
    assert report.target_quote_per_day == 3.0
    assert report.router_artifact["legacy_cluster_router_used"] is False
    assert report.router_artifact["derived_timeframes_available"] is True
    assert report.router_artifact["derived_timeframes_used_by_router"] is True
    assert "5m" in report.router_artifact["used_timeframes"]
    assert report.router_artifact["missing_timeframe_reason"] is None
    assert report.router_artifact["derived_timeframe_usage_mode"] == (
        "candidate_entry_diagnostics_only_no_gate_or_score_change"
    )
    assert report.router_artifact["derived_timeframe_training_edge_analysis_available"] is True
    assert htf_analysis["scope"] == "training_only_candidate_entries"
    assert htf_analysis["changes_trade_gates_or_scores"] is False
    assert report.rejection_summary["htf_filter_integration"][
        "blindtest_learning"
    ] is False
    assert "5m" in htf_analysis["timeframes"]
    assert "close_return" in htf_analysis["timeframes"]["5m"]
    assert report.best_activity_candidate["derived_timeframe_features"][
        "changes_trade_gates_or_scores"
    ] is False


def test_eth_specific_regime_diagnostics_are_reported() -> None:
    report = build_activity_first_router_report("run_test_eth_regime_diagnostics", _split(700))

    diagnostics = report.rejection_summary["eth_regime_diagnostics"]
    pass_names = {row["pass_name"] for row in report.rejection_summary["search_pass_summary"]}

    assert report.router_artifact["eth_specific_strategy_scope"] is True
    assert report.router_artifact["candidate_generation_version"] == (
        "activity_first_v7_htf_training_filter"
    )
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
    assert report.router_artifact["derived_timeframes_available"] is True
    assert report.router_artifact["derived_timeframes_used_by_router"] is False
    assert report.router_artifact["used_timeframes"] == []
    assert report.router_artifact["missing_timeframe_reason"] == (
        "no candidate training entry had a closed higher-timeframe feature"
    )


def test_training_only_htf_filter_rule_is_learned_from_candidate_winners() -> None:
    candidate = ActivityFirstCandidate(
        "eth_candidate",
        "eth_continuation_after_impulse_entry",
        5,
        0.01,
        0.02,
        0.01,
        30,
        1,
        100.0,
        "eth_regime_discovery",
    )
    trades = []
    snapshots = {}
    for index in range(50):
        entry_time = f"2026-01-01T00:{index:02d}:00Z"
        is_winner = index < 25
        trades.append(
            ActivityFirstTrade(
                entry_time,
                entry_time,
                100.0,
                101.0 if is_winner else 99.5,
                100.0,
                1.0,
                1.0 if is_winner else -0.5,
                0.0,
                1.0 if is_winner else -0.5,
                1.0 if is_winner else -0.5,
                "test",
                candidate.family,
                candidate.candidate_id,
            )
        )
        snapshots[entry_time] = {
            "1h": {
                "range_pct": 0.03 if is_winner else 0.01,
                "close_return": 0.0,
                "volume": 1.0,
            }
        }
    simulation = ActivityFirstSimulationResult(
        candidate,
        100.0,
        112.5,
        12.5,
        0.0,
        12.5,
        0.1,
        50,
        0.5,
        25,
        25,
        0,
        2.0,
        50,
        0,
        0,
        trades,
    )
    evaluation = _TrainingEvaluation(
        candidate,
        simulation,
        "low_activity",
        False,
        "rejected_by_fees",
        0.0,
        2.9,
    )
    derived = DerivedTimeframeFeatureBuildResult(
        snapshots=snapshots,
        closed_candle_counts={"1h": 1},
        available_timeframes=["1h"],
        used_timeframes=["1h"],
    )

    learned, rules = _learn_htf_filter_candidates(
        [evaluation],
        derived,
        {"candidate_timeframes_for_future_review": ["1h"]},
    )

    assert len(learned) == 1
    assert learned[0].htf_filter_timeframe == "1h"
    assert learned[0].htf_filter_metric == "range_pct"
    assert learned[0].htf_filter_min_value == 0.02
    assert rules[0]["training_winner_pass_rate"] == 1.0
    assert rules[0]["training_loser_pass_rate"] == 0.0
    assert rules[0]["frozen_before_blindtest"] is True


def test_frozen_htf_filter_uses_only_feature_available_at_entry(
    monkeypatch,
) -> None:
    candles = [_candle(index) for index in range(11)]
    series = build_closed_timeframe_feature_series(candles, "5m")
    candidate = ActivityFirstCandidate(
        "eth_candidate_htf",
        "eth_continuation_after_impulse_entry",
        2,
        0.0,
        0.01,
        0.01,
        5,
        0,
        100.0,
        "eth_regime_discovery_htf_filter",
        htf_filter_timeframe="5m",
        htf_filter_metric="range_pct",
        htf_filter_min_value=0.0,
    )
    monkeypatch.setattr(
        router_report_module,
        "_entry_signal",
        lambda candles, index, candidate, market=None: True,
    )
    monkeypatch.setattr(
        router_report_module,
        "_exit_trade",
        lambda candles, index, candidate, filters: (
            min(index + 1, len(candles) - 1),
            "test",
            candles[min(index + 1, len(candles) - 1)].close,
        ),
    )

    result = router_report_module._run_candidate_on_candles(
        candles,
        candidate,
        100.0,
        None,
        htf_feature_series={"5m": series},
    )

    assert result.feature_filtered_signal_count == 3
    assert result.trades
    assert result.trades[0].entry_time == candles[5].open_time
