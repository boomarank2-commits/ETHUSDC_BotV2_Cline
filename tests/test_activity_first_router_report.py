import src.router.activity_first_router_report as router_report_module
import src.data.agg_trade_feature_series as aggtrade_module
import src.data.context_market_features as context_market_module
from src.data.candle_csv_io import save_candle_dataset_to_csv
from src.data.candle_dataset import CandleDataset
from src.data.data_catalog import CandleDataCatalogEntry
from src.data.derived_timeframes import (
    DerivedTimeframeFeatureBuildResult,
    build_closed_timeframe_feature_series,
)
from src.data.kline_orderflow_features import (
    build_closed_kline_orderflow_feature_series,
)
from src.data.candle_schema import Candle
from src.data.train_blind_split import TrainBlindSplit
from src.router import (
    _filter_learning_eligible,
    _learn_aggtrade_filter_candidates,
    _learn_context_market_filter_candidates,
    _learn_htf_filter_candidates,
    _learn_orderflow_filter_candidates,
)
from src.data.context_market_features import build_closed_context_market_feature_store
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
        "activity_first_v14_conservative_regime_pool"
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
    ] == "activity_first_v14_conservative_regime_pool"
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
