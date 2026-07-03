import pandas as pd

import src.data.agg_trade_feature_series as aggtrade_module
import src.data.context_market_features as context_market_module
import src.router as router_module
import src.router.activity_first_router_report as router_report_module
from src.data.candle_csv_io import save_candle_dataset_to_csv
from src.data.candle_dataset import CandleDataset
from src.data.candle_schema import Candle
from src.data.context_market_features import build_closed_context_market_feature_store
from src.data.data_catalog import CandleDataCatalogEntry
from src.data.derived_timeframes import (
    DerivedTimeframeFeatureBuildResult,
    build_closed_timeframe_feature_series,
)
from src.data.kline_orderflow_features import (
    build_closed_kline_orderflow_feature_series,
)
from src.data.train_blind_split import TrainBlindSplit
from src.research.erem_exposure_edge_check import EremThresholds
from src.router import (
    _aggregate_pool_result,
    _build_erem_defensive_router_result,
    _erem_align_window_to_execution,
    _filter_learning_eligible,
    _learn_aggtrade_filter_candidates,
    _learn_context_market_filter_candidates,
    _learn_htf_filter_candidates,
    _learn_orderflow_filter_candidates,
    _long_only_oracle_summary,
    _temporal_validation_stability_rejection,
    _temporal_validation_stability_report,
    _walkforward_all_positive_candidate,
    _walkforward_pool_order_key,
    _walkforward_stability_policy_rejection,
)
from src.router.activity_first_router_report import (
    ActivityFirstCandidate,
    ActivityFirstSimulationResult,
    ActivityFirstTrade,
    _TrainingEvaluation,
    build_activity_first_router_report,
)


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
        "activity_first_v20_all_positive_walkforward_pool"
    )
    assert report.router_artifact["base_candidate_generation_version"] == (
        "activity_first_v11_eth_regime_expanded"
    )
    assert report.router_artifact["selection_validation_guard_used"] is True
    assert report.router_artifact["validation_optimized_pool_used"] is True
    assert report.router_artifact["conservative_regime_pool_used"] is True
    assert report.router_artifact["selection_validation"][
        "selection_validation_used"
    ] is True
    assert report.router_artifact["selection_validation"]["pool_selection"][
        "pool_selection_version"
    ] == "activity_first_v20_all_positive_walkforward_pool"
    assert report.router_artifact["selection_validation"]["pool_selection"][
        "walkforward_stability_pool_selection_used"
    ] is True
    assert report.router_artifact["selection_validation"]["pool_selection"][
        "walkforward_stability_blindtest_learning"
    ] is False
    assert report.router_artifact["selection_validation"][
        "validation_pool_temporal_stability"
    ]["guard_used"] is True
    assert report.router_artifact["target_feasibility_audit"][
        "audit_version"
    ] == "target_feasibility_v16_long_only_oracle"
    assert report.router_artifact["target_feasibility_audit"][
        "changes_trade_selection"
    ] is False
    assert report.rejection_summary["target_feasibility_audit"][
        "scope"
    ] == "diagnostic_only_no_trade_decision"
    assert report.router_artifact["walkforward_regime_research_version"] == (
        "walkforward_regime_research_v17_training_only"
    )
    assert report.router_artifact[
        "walkforward_regime_research_used_for_trade_decision"
    ] is True
    assert report.router_artifact[
        "walkforward_stability_pool_selection_version"
    ] == "activity_first_v20_all_positive_walkforward_pool"
    assert report.router_artifact[
        "walkforward_stability_used_for_pool_selection"
    ] is True
    walkforward_research = report.router_artifact["walkforward_regime_research"]
    assert walkforward_research["scope"] == (
        "training_only_pool_selection_input_plus_diagnostics"
    )
    assert walkforward_research["uses_blindtest"] is False
    assert walkforward_research["uses_blindtest_for_learning"] is False
    assert walkforward_research["changes_trade_selection"] is True
    assert walkforward_research["changes_gates"] is False
    assert walkforward_research["used_for_pool_selection"] is True
    assert walkforward_research["candidate_count"] >= report.setup_test_count
    assert report.rejection_summary[
        "walkforward_regime_research_used_for_trade_decision"
    ] is True
    assert report.router_artifact["selection_validation"]["pool_selection"][
        "walkforward_stability_policy"
    ] == "stable_only_when_stable_candidates_available"
    assert report.router_artifact["selection_validation"]["pool_selection"][
        "walkforward_stability_required_label"
    ] == "training_stable_positive"
    assert report.router_artifact["selection_validation"]["pool_selection"][
        "walkforward_all_positive_policy"
    ] == "all_positive_folds_when_all_positive_candidates_available"
    assert (
        "rejected_by_walkforward_all_positive_policy"
        in report.router_artifact["selection_validation"]["pool_selection"][
            "rejection_counts"
        ]
    )
    assert report.rejection_summary["selection_validation"][
        "learning_scope"
    ] == "selection_train_only"
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


def test_filter_learning_can_try_fee_dragged_gross_edge_eth_candidates() -> None:
    candidate = ActivityFirstCandidate(
        "eth_candidate_fee_dragged",
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
    gross_edge_result = ActivityFirstSimulationResult(
        candidate,
        100.0,
        99.0,
        10.0,
        11.0,
        -1.0,
        -0.01,
        50,
        0.5,
        25,
        25,
        0,
        2.0,
        50,
        0,
        0,
        [],
    )
    no_gross_edge_result = ActivityFirstSimulationResult(
        candidate,
        100.0,
        99.0,
        -1.0,
        11.0,
        -12.0,
        -0.12,
        50,
        0.5,
        25,
        25,
        0,
        2.0,
        50,
        0,
        0,
        [],
    )

    assert _filter_learning_eligible(
        _TrainingEvaluation(
            candidate,
            gross_edge_result,
            "low_activity",
            False,
            "rejected_by_fees",
            0.0,
            3.01,
        )
    ) is True
    assert _filter_learning_eligible(
        _TrainingEvaluation(
            candidate,
            no_gross_edge_result,
            "low_activity",
            False,
            "rejected_by_training_net",
            0.0,
            3.12,
        )
    ) is False


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


def test_training_only_orderflow_filter_is_learned_from_eth_candidate_winners() -> None:
    candidate = ActivityFirstCandidate(
        "eth_candidate_orderflow",
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
    candles = []
    for index in range(60):
        quote_volume = 100.0
        if 5 <= index < 30:
            quote_volume = 300.0
        if 30 <= index < 55:
            quote_volume = 25.0
        taker_share = 0.5
        if 5 <= index < 30:
            taker_share = 0.95
        if 30 <= index < 55:
            taker_share = 0.05
        candles.append(
            Candle(
                open_time=f"2026-01-01T00:{index:02d}:00Z",
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=quote_volume / 100.0,
                quote_volume=quote_volume,
                trade_count=int(quote_volume),
                taker_buy_base_volume=quote_volume * taker_share / 100.0,
                taker_buy_quote_volume=quote_volume * taker_share,
            )
        )
    trades = []
    for index in range(5, 55):
        is_winner = index < 30
        trades.append(
            ActivityFirstTrade(
                candles[index].open_time,
                candles[index].open_time,
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

    learned, rules = _learn_orderflow_filter_candidates([evaluation], candles)

    assert len(learned) == 1
    assert learned[0].orderflow_filter_lookback == 5
    assert learned[0].orderflow_filter_metric == "taker_buy_quote_imbalance"
    assert learned[0].orderflow_filter_operator == ">="
    assert rules[0]["training_winner_pass_rate"] > rules[0][
        "training_loser_pass_rate"
    ]
    assert rules[0]["frozen_before_blindtest"] is True


def test_frozen_orderflow_filter_uses_entry_minute_without_future_values(
    monkeypatch,
) -> None:
    candles = []
    for index, quote_volume in enumerate((10.0, 10.0, 5.0, 30.0, 30.0, 30.0)):
        candles.append(
            Candle(
                open_time=f"2026-01-01T00:{index:02d}:00Z",
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=quote_volume / 100.0,
                quote_volume=quote_volume,
                trade_count=int(quote_volume),
                taker_buy_base_volume=quote_volume / 200.0,
                taker_buy_quote_volume=quote_volume / 2.0,
            )
        )
    series = build_closed_kline_orderflow_feature_series(candles, 2)
    candidate = ActivityFirstCandidate(
        "eth_candidate_orderflow_filter",
        "eth_continuation_after_impulse_entry",
        2,
        0.0,
        0.01,
        0.01,
        5,
        0,
        100.0,
        "eth_regime_discovery_orderflow_filter",
        orderflow_filter_lookback=2,
        orderflow_filter_metric="quote_volume_ratio",
        orderflow_filter_operator=">=",
        orderflow_filter_threshold=1.5,
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
        orderflow_feature_series={2: series},
    )

    assert result.feature_filtered_signal_count == 1
    assert result.trades
    assert result.trades[0].entry_time == candles[3].open_time


def test_training_only_aggtrade_filter_is_learned_from_eth_candidate_winners(
    tmp_path,
    monkeypatch,
) -> None:
    candidate = ActivityFirstCandidate(
        "eth_candidate_aggtrade",
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
    rows = [
        "open_time,agg_trade_count,raw_trade_count,base_volume,quote_volume,"
        "taker_buy_base_volume,taker_buy_quote_volume,taker_sell_base_volume,"
        "taker_sell_quote_volume,vwap,max_agg_trade_quote"
    ]
    candles = []
    for index in range(60):
        winner = 5 <= index < 30
        loser = 30 <= index < 55
        buy_quote = 95.0 if winner else (5.0 if loser else 50.0)
        sell_quote = 100.0 - buy_quote
        rows.append(
            f"2026-01-01T00:{index:02d}:00Z,10,20,1,100,"
            f"{buy_quote / 100},{buy_quote},{sell_quote / 100},{sell_quote},100,10"
        )
        candles.append(
            Candle(
                open_time=f"2026-01-01T00:{index:02d}:00Z",
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1.0,
            )
        )
    (tmp_path / "2026-01.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(aggtrade_module, "AGG_TRADE_FEATURE_DIR", tmp_path)

    trades = []
    for index in range(5, 55):
        is_winner = index < 30
        trades.append(
            ActivityFirstTrade(
                candles[index].open_time,
                candles[index].open_time,
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
    simulation = ActivityFirstSimulationResult(
        candidate, 100.0, 112.5, 12.5, 0.0, 12.5, 0.1, 50, 0.5,
        25, 25, 0, 2.0, 50, 0, 0, trades,
    )
    evaluation = _TrainingEvaluation(
        candidate, simulation, "low_activity", False, "rejected_by_fees", 0.0, 2.9,
    )

    learned, rules = _learn_aggtrade_filter_candidates([evaluation], candles)

    assert len(learned) == 1
    assert learned[0].aggtrade_filter_lookback == 5
    assert learned[0].aggtrade_filter_metric == "taker_buy_quote_imbalance"
    assert learned[0].aggtrade_filter_operator == ">="
    assert rules[0]["training_winner_pass_rate"] > rules[0]["training_loser_pass_rate"]
    assert rules[0]["frozen_before_blindtest"] is True


def test_training_only_context_filter_is_learned_from_eth_candidate_winners(
    tmp_path,
    monkeypatch,
) -> None:
    candidate = ActivityFirstCandidate(
        "eth_candidate_context",
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
    candles = [_flat_candle(index) for index in range(60)]
    entries = []
    for symbol in ("BTCUSDC", "ETHBTC", "ETHUSDT", "USDCUSDT"):
        context_candles = []
        for index, candle in enumerate(candles):
            close = 1.0
            if symbol == "BTCUSDC":
                close = 100.0
            elif symbol == "ETHBTC":
                close = 0.02
            elif symbol == "ETHUSDT":
                close = 101.0 if 5 <= index < 30 else (99.0 if 30 <= index < 55 else 100.0)
            context_candles.append(
                Candle(
                    candle.open_time,
                    close,
                    close * 1.01,
                    close * 0.99,
                    close,
                    1.0,
                )
            )
        path = tmp_path / f"{symbol}_1m.csv"
        save_candle_dataset_to_csv(CandleDataset(symbol, "1m", context_candles), path)
        entries.append(CandleDataCatalogEntry(symbol, "1m", str(path)))
    monkeypatch.setattr(context_market_module, "load_data_catalog", lambda: entries)

    trades = []
    for index in range(5, 55):
        is_winner = index < 30
        trades.append(
            ActivityFirstTrade(
                candles[index].open_time,
                candles[index].open_time,
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
    simulation = ActivityFirstSimulationResult(
        candidate, 100.0, 112.5, 12.5, 0.0, 12.5, 0.1, 50, 0.5,
        25, 25, 0, 2.0, 50, 0, 0, trades,
    )
    evaluation = _TrainingEvaluation(
        candidate, simulation, "low_activity", False, "rejected_by_fees", 0.0, 2.9,
    )

    store = build_closed_context_market_feature_store(candles)
    learned, rules = _learn_context_market_filter_candidates(
        [evaluation], candles, store,
    )

    assert len(learned) == 1
    assert learned[0].context_filter_lookback == 5
    assert learned[0].context_filter_metric == "ethusdt_ethusdc_basis"
    assert learned[0].context_filter_operator == ">="
    assert rules[0]["training_winner_pass_rate"] > rules[0]["training_loser_pass_rate"]
    assert rules[0]["frozen_before_blindtest"] is True


def test_pool_aggregation_uses_one_shared_account_and_skips_overlaps(
    monkeypatch,
) -> None:
    candles = [_flat_candle(index) for index in range(60)]
    high_score_candidate = ActivityFirstCandidate(
        "candidate_high_score",
        "eth_test_family",
        5,
        0.01,
        0.02,
        0.01,
        30,
        1,
        100.0,
        "test",
    )
    low_score_candidate = ActivityFirstCandidate(
        "candidate_low_score",
        "eth_test_family",
        5,
        0.01,
        0.02,
        0.01,
        30,
        1,
        100.0,
        "test",
    )
    high_score_trade = ActivityFirstTrade(
        "2026-01-01T00:10:00Z",
        "2026-01-01T00:30:00Z",
        100.0,
        105.0,
        100.0,
        1.0,
        5.0,
        0.0,
        5.0,
        5.0,
        "test",
        high_score_candidate.family,
        high_score_candidate.candidate_id,
    )
    overlapping_trade = ActivityFirstTrade(
        "2026-01-01T00:10:00Z",
        "2026-01-01T00:20:00Z",
        100.0,
        111.0,
        100.0,
        1.0,
        11.0,
        0.0,
        11.0,
        11.0,
        "test",
        low_score_candidate.family,
        low_score_candidate.candidate_id,
    )

    def _result_for(candidate: ActivityFirstCandidate, trade: ActivityFirstTrade):
        return ActivityFirstSimulationResult(
            candidate,
            100.0,
            100.0 + trade.net_pnl,
            trade.gross_pnl,
            trade.fees_paid,
            trade.net_pnl,
            trade.net_pnl,
            1,
            1.0,
            1 if trade.net_pnl > 0 else 0,
            1 if trade.net_pnl < 0 else 0,
            1 if trade.net_pnl == 0 else 0,
            0.0,
            1,
            0,
            0,
            [trade],
        )

    results_by_candidate_id = {
        high_score_candidate.candidate_id: _result_for(
            high_score_candidate,
            high_score_trade,
        ),
        low_score_candidate.candidate_id: _result_for(
            low_score_candidate,
            overlapping_trade,
        ),
    }

    def _fake_run_candidate_on_candles(
        _candles,
        candidate,
        _start_capital,
        _filters,
        _market,
        _feature_series=None,
        _orderflow_feature_series=None,
        _aggtrade_feature_series=None,
        _context_feature_series=None,
    ):
        return results_by_candidate_id[candidate.candidate_id]

    monkeypatch.setattr(
        router_report_module,
        "_run_candidate_on_candles",
        _fake_run_candidate_on_candles,
    )
    selected_pool = [
        _TrainingEvaluation(
            high_score_candidate,
            results_by_candidate_id[high_score_candidate.candidate_id],
            "medium_activity",
            True,
            None,
            2.0,
            0.0,
        ),
        _TrainingEvaluation(
            low_score_candidate,
            results_by_candidate_id[low_score_candidate.candidate_id],
            "medium_activity",
            True,
            None,
            1.0,
            0.0,
        ),
    ]

    result = _aggregate_pool_result(candles, selected_pool, 100.0, None)

    assert result.signal_count == 2
    assert result.trade_count == 1
    assert result.no_trade_count == 1
    assert result.total_net_pnl == 5.0
    assert result.final_capital_reference == 105.0
    assert result.trades == [high_score_trade]


def test_temporal_validation_guard_rejects_material_negative_segment() -> None:
    candidate = ActivityFirstCandidate(
        "candidate_temporal_instability",
        "eth_test_family",
        5,
        0.01,
        0.02,
        0.01,
        30,
        1,
        100.0,
        "test",
    )
    candles = [_flat_candle(index) for index in range(3 * 1440)]
    trades = [
        ActivityFirstTrade(
            candles[10].open_time,
            candles[10].open_time,
            100.0,
            105.0,
            100.0,
            1.0,
            5.0,
            0.0,
            5.0,
            5.0,
            "test",
            candidate.family,
            candidate.candidate_id,
        ),
        ActivityFirstTrade(
            candles[1450].open_time,
            candles[1450].open_time,
            100.0,
            99.0,
            100.0,
            1.0,
            -1.0,
            0.0,
            -1.0,
            -1.0,
            "test",
            candidate.family,
            candidate.candidate_id,
        ),
        ActivityFirstTrade(
            candles[1460].open_time,
            candles[1460].open_time,
            100.0,
            99.0,
            100.0,
            1.0,
            -1.0,
            0.0,
            -1.0,
            -1.0,
            "test",
            candidate.family,
            candidate.candidate_id,
        ),
        ActivityFirstTrade(
            candles[1470].open_time,
            candles[1470].open_time,
            100.0,
            99.0,
            100.0,
            1.0,
            -1.0,
            0.0,
            -1.0,
            -1.0,
            "test",
            candidate.family,
            candidate.candidate_id,
        ),
        ActivityFirstTrade(
            candles[2890].open_time,
            candles[2890].open_time,
            100.0,
            104.0,
            100.0,
            1.0,
            4.0,
            0.0,
            4.0,
            4.0,
            "test",
            candidate.family,
            candidate.candidate_id,
        ),
    ]
    result = ActivityFirstSimulationResult(
        candidate,
        100.0,
        106.0,
        6.0,
        0.0,
        6.0,
        2.0,
        len(trades),
        1.67,
        2,
        3,
        0,
        3.0,
        len(trades),
        0,
        0,
        trades,
    )

    report = _temporal_validation_stability_report(
        result,
        candles,
        segment_days=1,
    )

    assert result.total_net_pnl > 0
    assert report["evaluated"] is True
    assert report["segment_count"] == 3
    assert report["negative_material_segment_count"] == 1
    assert report["rejection_reason"] == (
        "rejected_by_temporal_validation_stability"
    )
    assert _temporal_validation_stability_rejection(
        result,
        candles,
        segment_days=1,
    ) == "rejected_by_temporal_validation_stability"


def test_target_feasibility_oracle_is_diagnostic_only() -> None:
    candles = [
        Candle(
            "2026-01-01T00:00:00Z",
            100.0,
            100.0,
            100.0,
            100.0,
            1.0,
        ),
        Candle(
            "2026-01-01T00:01:00Z",
            100.0,
            105.0,
            100.0,
            104.0,
            1.0,
        ),
        Candle(
            "2026-01-02T00:00:00Z",
            104.0,
            104.0,
            104.0,
            104.0,
            1.0,
        ),
        Candle(
            "2026-01-02T00:01:00Z",
            104.0,
            106.0,
            104.0,
            105.0,
            1.0,
        ),
    ]

    summary = _long_only_oracle_summary(
        candles,
        stake_quote_amount=100.0,
        target_quote_per_day=3.0,
    )

    assert summary["tradeable"] is False
    assert summary["uses_future_high_inside_day"] is True
    assert summary["day_count"] == 2
    assert summary["positive_day_count"] == 2
    assert summary["quote_per_day"] > 0
    assert summary["required_capture_of_oracle_for_target"] is not None


def test_walkforward_stability_pool_key_prefers_stable_candidate() -> None:
    def evaluation(candidate_id: str, quote_per_day: float) -> _TrainingEvaluation:
        candidate = ActivityFirstCandidate(
            candidate_id,
            "eth_continuation_after_impulse_entry",
            30,
            0.0085,
            0.04,
            0.016,
            1440,
            1,
            100.0,
            "eth_regime_expanded",
        )
        result = ActivityFirstSimulationResult(
            candidate,
            100.0,
            100.0 + quote_per_day,
            quote_per_day,
            0.0,
            quote_per_day,
            quote_per_day,
            10,
            0.5,
            6,
            4,
            0,
            2.0,
            10,
            0,
            0,
            [],
        )
        return _TrainingEvaluation(
            candidate,
            result,
            "active",
            True,
            None,
            quote_per_day,
            abs(3.0 - quote_per_day),
        )

    stable = evaluation("stable_candidate", 0.10)
    mixed = evaluation("mixed_candidate", 0.90)
    stability_by_id = {
        "stable_candidate": {
            "stability_label": "training_stable_positive",
            "negative_material_fold_count": 0,
            "positive_active_fold_rate": 1.0,
            "active_fold_count": 9,
            "quote_per_day": 0.10,
        },
        "mixed_candidate": {
            "stability_label": "training_mixed_positive",
            "negative_material_fold_count": 2,
            "positive_active_fold_rate": 0.78,
            "active_fold_count": 9,
            "quote_per_day": 0.90,
        },
    }

    assert _walkforward_pool_order_key(stable, stability_by_id) > (
        _walkforward_pool_order_key(mixed, stability_by_id)
    )


def test_walkforward_stability_policy_rejects_mixed_when_stable_exists() -> None:
    candidate = ActivityFirstCandidate(
        "mixed_candidate",
        "eth_bounce_after_flush_entry",
        120,
        0.011,
        0.055,
        0.022,
        2160,
        1,
        100.0,
        "eth_regime_expanded_context_market_filter",
    )
    result = ActivityFirstSimulationResult(
        candidate,
        100.0,
        110.0,
        12.0,
        2.0,
        10.0,
        0.10,
        20,
        0.2,
        10,
        10,
        0,
        5.0,
        20,
        0,
        0,
        [],
    )
    evaluation = _TrainingEvaluation(
        candidate,
        result,
        "active",
        True,
        None,
        0.10,
        2.90,
    )
    stability_by_id = {
        "mixed_candidate": {
            "stability_label": "training_mixed_positive",
            "negative_material_fold_count": 2,
            "positive_active_fold_rate": 0.78,
            "active_fold_count": 9,
            "quote_per_day": 0.10,
        }
    }

    assert _walkforward_stability_policy_rejection(
        evaluation,
        stability_by_id,
        stable_candidates_available=True,
    ) == "rejected_by_walkforward_stability_policy"
    assert _walkforward_stability_policy_rejection(
        evaluation,
        stability_by_id,
        stable_candidates_available=False,
    ) is None


def test_walkforward_all_positive_policy_rejects_stable_with_negative_fold() -> None:
    candidate = ActivityFirstCandidate(
        "stable_with_negative_fold",
        "eth_continuation_after_impulse_entry",
        120,
        0.011,
        0.055,
        0.022,
        2160,
        1,
        100.0,
        "eth_regime_expanded_htf_filter",
    )
    result = ActivityFirstSimulationResult(
        candidate,
        100.0,
        110.0,
        12.0,
        2.0,
        10.0,
        0.10,
        20,
        0.2,
        10,
        10,
        0,
        5.0,
        20,
        0,
        0,
        [],
    )
    evaluation = _TrainingEvaluation(
        candidate,
        result,
        "active",
        True,
        None,
        0.10,
        2.90,
    )
    stability_by_id = {
        "stable_with_negative_fold": {
            "stability_label": "training_stable_positive",
            "negative_material_fold_count": 0,
            "positive_active_fold_count": 8,
            "positive_active_fold_rate": 0.8888888888888888,
            "active_fold_count": 9,
            "worst_fold_net_pnl": -1.0,
            "quote_per_day": 0.10,
        }
    }
    all_positive_row = {
        "stability_label": "training_stable_positive",
        "negative_material_fold_count": 0,
        "positive_active_fold_count": 9,
        "positive_active_fold_rate": 1.0,
        "active_fold_count": 9,
        "worst_fold_net_pnl": 1.0,
        "quote_per_day": 0.10,
    }

    assert _walkforward_all_positive_candidate(all_positive_row) is True
    assert _walkforward_stability_policy_rejection(
        evaluation,
        stability_by_id,
        stable_candidates_available=True,
        all_positive_candidates_available=True,
    ) == "rejected_by_walkforward_all_positive_policy"


def test_erem_defensive_router_result_uses_fixed_research_variant(monkeypatch) -> None:
    index = pd.date_range(
        "2025-01-01T00:00:00Z",
        periods=70 * 24 + 8,
        freq="h",
        tz="UTC",
    )
    execution = pd.DataFrame(
        {
            "open": [100.0 + offset * 0.01 for offset in range(len(index))],
            "brh_signal_update_bar": [True] * len(index),
            "btc_4h_drawdown_from_20d_high": [-0.01] * len(index),
            "btc_4h_close_vs_ema20": [0.01] * len(index),
        },
        index=index,
    )
    thresholds = EremThresholds(btc_drawdown_threshold=-0.02)

    def fake_metrics(*_args, **_kwargs):
        return {
            "erem_pnl_usdc": 1.0,
            "buy_hold_pnl_usdc": -2.0,
            "erem_usdc_per_day": 0.1,
            "buy_hold_usdc_per_day": -0.2,
            "strategy_minus_buy_hold_usdc_per_day": 0.3,
            "erem_maxdd_usdc": 1.0,
            "buy_hold_maxdd_usdc": 4.0,
            "erem_maxdd_pct": 0.123,
            "buy_hold_maxdd_pct": 0.04,
            "time_in_market_pct": 0.5,
            "switch_count": 2,
            "avoided_loss_blocks": [1.0],
            "top1_avoided_block_share": 1.0,
            "top2_avoided_block_share": 1.0,
        }

    monkeypatch.setattr(
        router_module,
        "_load_erem_execution",
        lambda: (execution, index[0], index[-8], index[-1]),
    )
    monkeypatch.setattr(
        router_module,
        "calibrate_erem_thresholds",
        lambda *_args, **_kwargs: thresholds,
    )
    monkeypatch.setattr(router_module, "simulate_erem_exposure", fake_metrics)
    monkeypatch.setattr(
        router_module,
        "_desired_exposure_changes",
        lambda *_args, **_kwargs: {index[-8]: True, index[-5]: False},
    )
    split = TrainBlindSplit(
        symbol="ETHUSDC",
        interval="1m",
        training_candles=[],
        blindtest_candles=[],
        training_start=index[0].isoformat(),
        training_end=index[-9].isoformat(),
        blindtest_start=index[-8].isoformat(),
        blindtest_end=index[-1].isoformat(),
    )

    result = _build_erem_defensive_router_result(split, 100.0)

    assert result["selected"] is True
    assert result["variant_id"] == "erem_btc_drawdown_q35_or_ema_below0"
    assert result["setup"]["blindtest_learning"] is False
    assert result["result"].candidate.family == "erem_exposure_management"
    assert result["result"].max_drawdown == 12.3
    assert result["result"].trade_count == 1


def test_erem_alignment_accepts_hourly_edge_gap_but_rejects_stale_data() -> None:
    index = pd.date_range(
        "2026-01-01T20:00:00Z",
        periods=4,
        freq="h",
        tz="UTC",
    )
    execution = pd.DataFrame({"open": [100.0, 101.0, 102.0, 103.0]}, index=index)

    aligned = _erem_align_window_to_execution(
        execution,
        pd.Timestamp("2026-01-01T20:04:00Z"),
        pd.Timestamp("2026-01-01T23:03:00Z"),
    )

    assert aligned is not None
    assert aligned["start"] == pd.Timestamp("2026-01-01T21:00:00Z")
    assert aligned["end"] == pd.Timestamp("2026-01-01T23:00:00Z")
    assert round(aligned["leading_gap_hours"], 4) == round(56 / 60, 4)
    assert round(aligned["trailing_gap_hours"], 4) == round(3 / 60, 4)

    stale = _erem_align_window_to_execution(
        execution,
        pd.Timestamp("2026-01-01T20:04:00Z"),
        pd.Timestamp("2026-01-02T02:03:00Z"),
    )

    assert stale is None
