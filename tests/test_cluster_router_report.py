from pathlib import Path
import json

from src.backtest.strategy_v1 import StrategyV1Candidate, StrategyV1Result
from src.data.candle_schema import Candle
from src.data.train_blind_split import TrainBlindSplit
import src.router.cluster_router_report as router_module
from src.router.cluster_router_report import (
    _activity_class,
    _deduplicated_setup_candidates,
    _mine_training_opportunities,
    _run_frozen_router,
    _target_aware_score,
    _training_precheck_reject_reason,
    build_cluster_router_report,
    load_cluster_router_report,
    save_cluster_router_report,
)


def _candle(index: int, close: float) -> Candle:
    return Candle(f"2026-01-01T{index // 60:02d}:{index % 60:02d}:00Z", close, close * 1.002, close * 0.998, close, 1.0)


def _trend_candles(count: int) -> list[Candle]:
    return [_candle(index, 100.0 + index * 0.05) for index in range(count)]


def _split() -> TrainBlindSplit:
    training = _trend_candles(260)
    blindtest = _trend_candles(180)
    return TrainBlindSplit(
        "ETHUSDC",
        "1m",
        training,
        blindtest,
        training[0].open_time,
        training[-1].open_time,
        blindtest[0].open_time,
        blindtest[-1].open_time,
    )


def test_cluster_router_report_builds_target_chain_fields() -> None:
    report = build_cluster_router_report("run_20260619_180001", _split())

    assert report.opportunity_event_count >= 0
    assert report.situation_cluster_count >= 0
    assert isinstance(report.router_frozen, bool)
    assert report.blindtest_used_frozen_router == report.router_frozen
    assert report.router_artifact["training_only"] is True
    assert report.router_artifact["blindtest_learning_allowed"] is False
    assert all(not row.get("diagnostic_only", False) for row in report.selected_setups)
    assert all(row.get("trade_allowed") is True for row in report.selected_setups)
    assert isinstance(report.blindtest_daily_distribution, list)
    assert isinstance(report.blindtest_monthly_distribution, list)


def test_cluster_router_report_save_and_load() -> None:
    report = build_cluster_router_report("run_20260619_180002", _split())

    path = save_cluster_router_report(report)

    assert Path(path).is_file()
    assert load_cluster_router_report(report.run_id) == report
    diagnostics_path = Path(path).parent / "cluster_router_diagnostics.json"
    assert diagnostics_path.is_file()
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    assert diagnostics["target_usdc_per_day"] == 3.0
    assert "target_math_status" in diagnostics
    assert "required_net_per_trade_for_3_usdc_day" in diagnostics


def test_cluster_router_report_stores_best_and_worst_periods() -> None:
    report = build_cluster_router_report("run_20260619_180003", _split())

    assert report.positive_days is not None
    assert report.negative_days is not None
    if report.blindtest_daily_distribution:
        assert report.best_day is not None
        assert report.worst_day is not None
        assert report.best_day_pnl == report.best_day["net_pnl"]
        assert report.worst_day_pnl == report.worst_day["net_pnl"]


def test_cluster_router_trade_diagnostics_include_mfe_mae_fields() -> None:
    report = build_cluster_router_report("run_20260619_180004", _split())

    for trade in report.blindtest_trades:
        assert "trade_id" in trade
        assert "cluster_id" in trade
        assert "setup_id" in trade
        assert "mfe" in trade
        assert "mae" in trade
        assert "hold_minutes" in trade
        assert trade["slippage"] == 0.0


def test_cluster_router_report_does_not_fallback_to_strategy_v1() -> None:
    report = build_cluster_router_report("run_20260619_180005", _split())

    assert report.router_artifact["frozen"] == bool(report.selected_setups)
    assert report.blindtest_used_frozen_router == bool(report.selected_setups)
    assert report.router_artifact["selected_setups"] == report.selected_setups
    assert report.router_artifact["blindtest_learning_allowed"] is False
    assert report.router_artifact["training_only"] is True


def test_cluster_router_never_trades_diagnostic_or_research_only_setups() -> None:
    report = build_cluster_router_report("run_20260619_180007", _split())

    for row in report.selected_setups:
        assert row.get("trade_allowed") is True
        assert row.get("diagnostic_only", False) is False
        assert row.get("research_only", False) is False
    traded_setup_ids = {trade["setup_id"] for trade in report.blindtest_trades}
    approved_setup_ids = {row["setup_name"] for row in report.selected_setups}
    assert traded_setup_ids <= approved_setup_ids


def test_blindtest_uses_frozen_router_setups_without_learning_new_setups() -> None:
    report = build_cluster_router_report("run_20260619_180008", _split())

    assert report.router_artifact["frozen"] == report.router_frozen
    assert report.router_artifact["selected_setups"] == report.selected_setups
    assert report.learned_setup_count == len(report.router_artifact["selected_setups"])
    assert report.router_setup_count == report.learned_setup_count


def test_local_setup_rows_include_target_awareness_metrics() -> None:
    report = build_cluster_router_report("run_20260619_180006", _split())
    rows = report.selected_setups + report.rejected_clusters

    assert rows
    for row in rows:
        assert "trades_per_day" in row
        assert "net_per_trade" in row
        assert "expected_usdc_per_day" in row
        assert "required_net_per_trade_for_3_usdc_day" in row
        assert "required_trades_per_day_at_current_edge" in row
        assert "target_math_status" in row
        assert "activity_gap" in row
        assert "edge_gap" in row


def test_target_aware_score_prefers_more_viable_activity_not_only_net_per_trade() -> None:
    rare_high_edge = {
        "trade_allowed": True,
        "expected_usdc_per_day": 0.03,
        "validation_expected_usdc_per_day": 0.02,
        "trades_per_day": 0.01,
        "validation_trades_per_day": 0.01,
        "activity_gap": 0.055,
        "edge_gap": 250.0,
        "training_active_days": 3,
        "robustness_positive_block_count": 1,
        "setup_validation_profit_factor": 9.0,
    }
    more_active_positive = {
        "trade_allowed": True,
        "expected_usdc_per_day": 0.08,
        "validation_expected_usdc_per_day": 0.05,
        "trades_per_day": 0.12,
        "validation_trades_per_day": 0.08,
        "activity_gap": 0.0,
        "edge_gap": 20.0,
        "training_active_days": 30,
        "robustness_positive_block_count": 3,
        "setup_validation_profit_factor": 1.6,
    }

    assert _target_aware_score(more_active_positive) > _target_aware_score(rare_high_edge)


def test_frozen_router_no_trade_when_no_approved_setup_matches() -> None:
    result = _run_frozen_router(_trend_candles(180), [], 100.0)

    assert result.trade_count == 0
    assert result.signal_count == 0
    assert result.total_net_pnl == 0.0


def test_setup_candidate_deduplication_removes_identical_variants() -> None:
    candidate = StrategyV1Candidate("momentum_breakout", "a", 5, None, 0.003, 0.006, 0.004, 60, 1, 10.0, 100.0)
    duplicate_name_only = StrategyV1Candidate("momentum_breakout", "b", 5, None, 0.003, 0.006, 0.004, 60, 1, 10.0, 100.0)
    different = StrategyV1Candidate("momentum_breakout", "c", 8, None, 0.003, 0.006, 0.004, 60, 1, 10.0, 100.0)

    deduped = _deduplicated_setup_candidates((candidate, duplicate_name_only, different))

    assert deduped == (candidate, different)


def test_training_precheck_skips_target_math_impossible_variants_early() -> None:
    candidate = StrategyV1Candidate("momentum_breakout", "rare", 5, None, 0.003, 0.006, 0.004, 60, 1, 10.0, 100.0)
    result = StrategyV1Result(
        candidate,
        100.0,
        100.0,
        101.0,
        1.0,
        1.0,
        1.0 / 730.0,
        1,
        1,
        0,
        0,
        0.0,
        [],
    )

    assert _training_precheck_reject_reason(result, 730 * 1440, 100.0) == "target_math_not_reachable_current_activity"


def test_second_training_only_search_pass_starts_when_primary_finds_no_setup(monkeypatch) -> None:
    calls: list[str] = []
    candidate = StrategyV1Candidate("momentum_breakout", "second", 3, None, 0.0015, 0.0035, 0.0025, 45, 0, 10.0, 100.0)
    selected_row = {
        "cluster_id": "activity_pass|trend_strong|mom_active|vol_low",
        "setup_candidate": candidate.__dict__,
        "setup_name": candidate.name,
        "trade_allowed": True,
    }

    def fake_pass(training_candles, stake_quote_amount, setup_candidates, cluster_key_func, pass_name, progress_callback=None, allowed_cluster_keys=None):
        calls.append(pass_name)
        if pass_name == "primary":
            return [], [{"reject_reason": "training_activity_floor_not_met"}], 10
        return [selected_row], [], 20

    monkeypatch.setattr(router_module, "_build_router_pass", fake_pass)

    selected, rejected, opportunity_count, summary = router_module._build_router(_trend_candles(160), 100.0)

    assert calls == ["primary", "activity_expansion"]
    assert selected == [selected_row]
    assert rejected == [{"reject_reason": "training_activity_floor_not_met"}]
    assert opportunity_count == 30
    assert summary["second_search_pass_used"] is True


def test_target_activity_pass_and_optimizer_failure_status_when_no_setup_found(monkeypatch) -> None:
    calls: list[str] = []

    def fake_pass(training_candles, stake_quote_amount, setup_candidates, cluster_key_func, pass_name, progress_callback=None, allowed_cluster_keys=None):
        calls.append(pass_name)
        return [], [
            {
                "reject_reason": "training_activity_floor_not_met",
                "training_quote_per_day": 0.01,
                "trades_per_day": 0.5,
                "net_per_trade": 0.02,
                "activity_gap": 2.5,
            }
        ], 10

    monkeypatch.setattr(router_module, "_build_router_pass", fake_pass)

    selected, rejected, _opportunity_count, summary = router_module._build_router(_trend_candles(160), 100.0)

    assert selected == []
    assert len(rejected) == 4
    assert calls == ["primary", "activity_expansion", "target_activity", "opportunity_mining"]
    assert summary["second_search_pass_used"] is True
    assert summary["third_search_pass_used"] is True
    assert summary["opportunity_search_pass_used"] is True
    assert summary["optimizer_status"] == "optimizer_search_space_failed"
    assert summary["best_found_candidate"] is not None
    assert summary["best_activity_candidate"] is not None
    assert summary["best_edge_candidate"] is not None
    assert summary["best_balanced_candidate"] is not None
    assert summary["best_target_candidate"] is not None


def test_rejection_summary_groups_rejections_by_search_pass() -> None:
    summary = router_module._rejection_summary(
        [
            {"search_pass": "primary", "reject_reason": "target_math_not_reachable_current_activity"},
            {"search_pass": "primary", "reject_reason": "training_activity_floor_not_met"},
            {"search_pass": "activity_expansion", "reject_reason": "training_net_profit_not_positive"},
            {"search_pass": "target_activity", "reject_reason": "training_validation_or_multiblock_robustness_not_met"},
        ],
        deduplicated_count=4,
        raw_candidate_count=4,
    )

    assert summary["search_pass_summary"]["primary"]["candidate_count"] == 2
    assert summary["search_pass_summary"]["primary"]["rejected_by_target_math"] == 1
    assert summary["search_pass_summary"]["primary"]["rejected_by_activity"] == 1
    assert summary["search_pass_summary"]["activity_expansion"]["rejected_by_training_net"] == 1
    assert summary["search_pass_summary"]["target_activity"]["rejected_by_other"] == 1
    assert summary["rejected_by_other"] == 1


def test_opportunity_mining_finds_training_windows_with_sufficient_move() -> None:
    candles = [_candle(index, 100.0) for index in range(200)]
    for index in range(121, 181):
        candles[index] = Candle(candles[index].open_time, 100.0, 100.7, 99.9, 100.4, 2.0)

    opportunities = _mine_training_opportunities(candles, lookahead_candles=30)

    assert opportunities
    assert opportunities[0]["mfe_pct"] > 0.003
    assert "trend_short" in opportunities[0]["features"]


def test_opportunity_mining_pass_uses_mined_training_clusters(monkeypatch) -> None:
    candles = _trend_candles(200)
    mined = [{"index": 150, "open_time": candles[150].open_time, "features": {}}]
    expected_key = router_module._opportunity_cluster_key(candles, 150)
    captured: dict[str, object] = {}

    def fake_pass(training_candles, stake_quote_amount, setup_candidates, cluster_key_func, pass_name, progress_callback=None, allowed_cluster_keys=None):
        if pass_name == "opportunity_mining":
            captured["allowed_cluster_keys"] = allowed_cluster_keys
            captured["cluster_key"] = cluster_key_func(training_candles, 150)
        return [], [{"search_pass": pass_name, "reject_reason": "training_activity_floor_not_met"}], 1

    monkeypatch.setattr(router_module, "_mine_training_opportunities", lambda training_candles: mined)
    monkeypatch.setattr(router_module, "_build_router_pass", fake_pass)

    _selected, _rejected, _opportunity_count, summary = router_module._build_router(candles, 100.0)

    assert captured["allowed_cluster_keys"] == {expected_key}
    assert captured["cluster_key"] == expected_key
    assert summary["mined_opportunity_cluster_count"] == 1


def test_activity_classes_match_target_ranges() -> None:
    assert _activity_class(0.1) == "low_activity"
    assert _activity_class(1.5) == "usable_activity"
    assert _activity_class(4.0) == "target_activity"
    assert _activity_class(8.0) == "high_activity"


def test_low_activity_candidate_is_not_target_relevant() -> None:
    candidate = StrategyV1Candidate("momentum_breakout", "rare", 5, None, 0.01, 0.02, 0.008, 60, 0, 10.0, 100.0)
    trade = router_module.StrategyV1Trade("2026-01-01", "2026-01-01", 100.0, 102.0, 100.0, 1.0, 2.0, 0.2, 1.8, 1.8, "tp", candidate.family, candidate.name)
    result = StrategyV1Result(candidate, 100.0, 100.0, 101.8, 1.8, 1.8, 0.00246, 1, 1, 0, 0, 0.0, [trade])

    target_math = router_module._target_math_for_result(result, 100.0, 730 * 1440)

    assert target_math["activity_class"] == "low_activity"
    assert target_math["target_relevant"] is False


def test_smoke_14_training_days_scales_target_activity_trade_counts() -> None:
    candidate = StrategyV1Candidate("momentum_breakout", "target_activity", 5, None, 0.001, 0.003, 0.002, 30, 0, 10.0, 100.0)
    trades = [
        router_module.StrategyV1Trade(
            f"2026-01-{(index % 14) + 1:02d}T00:00:00Z",
            f"2026-01-{(index % 14) + 1:02d}T00:01:00Z",
            100.0,
            100.3,
            100.0,
            1.0,
            0.3,
            0.2,
            0.1,
            0.1,
            "take_profit",
            candidate.family,
            candidate.name,
        )
        for index in range(42)
    ]
    result = StrategyV1Result(candidate, 100.0, 100.0, 104.2, 4.2, 4.2, 0.3, 42, 42, 0, 0, 0.0, trades)

    target_math = router_module._target_math_for_result(result, 100.0, 14 * 1440)

    assert target_math["trades_per_day"] == 3.0
    assert target_math["target_activity_min_training_trades_for_window"] == 42
    assert target_math["target_activity_max_training_trades_for_window"] == 84
    assert target_math["min_training_trades_for_window"] == 14
    assert target_math["min_training_trades_per_year"] == 365.0
    assert target_math["target_relevant"] is True


def test_smoke_precheck_uses_window_scaled_activity_floor() -> None:
    candidate = StrategyV1Candidate("momentum_breakout", "under_active", 5, None, 0.001, 0.003, 0.002, 30, 0, 10.0, 100.0)
    trades = [
        router_module.StrategyV1Trade(
            f"2026-01-{index + 1:02d}T00:00:00Z",
            f"2026-01-{index + 1:02d}T00:01:00Z",
            100.0,
            100.3,
            100.0,
            1.0,
            0.3,
            0.2,
            0.1,
            0.1,
            "take_profit",
            candidate.family,
            candidate.name,
        )
        for index in range(13)
    ]
    result = StrategyV1Result(candidate, 100.0, 100.0, 101.3, 1.3, 1.3, 0.092857, 13, 13, 0, 0, 0.0, trades)

    assert router_module._training_precheck_reject_reason(result, 14 * 1440, 100.0) == "training_activity_floor_not_met"


def test_positive_training_candidate_is_fully_evaluated_after_precheck(monkeypatch) -> None:
    candles = _trend_candles(140)
    candidate = StrategyV1Candidate("momentum_breakout", "positive_precheck", 2, None, 0.001, 0.003, 0.002, 20, 0, 10.0, 100.0)
    trade = router_module.StrategyV1Trade(
        candles[10].open_time,
        candles[11].open_time,
        100.0,
        100.3,
        100.0,
        1.0,
        0.3,
        0.2,
        0.1,
        0.1,
        "take_profit",
        candidate.family,
        candidate.name,
    )
    positive_result = StrategyV1Result(candidate, 100.0, 100.0, 100.1, 0.1, 0.1, 0.1, 1, 1, 0, 0, 0.0, [trade])
    empty_result = StrategyV1Result(candidate, 100.0, 100.0, 100.0, 0.0, 0.0, 0.0, 0, 0, 0, 0, 0.0, [])
    calls = {"count": 0}

    def fake_result_for_cluster(*args, **kwargs):
        calls["count"] += 1
        return positive_result if calls["count"] == 1 else empty_result

    monkeypatch.setattr(router_module, "_result_for_cluster", fake_result_for_cluster)

    selected, rejected, _opportunity_count = router_module._build_router_pass(
        candles,
        100.0,
        (candidate,),
        lambda _candles, _index: "test_cluster",
        "primary",
    )

    assert selected == []
    assert len(rejected) == 1
    assert rejected[0].get("skipped_after_training_precheck") is not True
    assert rejected[0]["setup_validation_trades"] == 0
    assert rejected[0]["reject_reason"] == "training_edge_not_met"
    assert calls["count"] > 1


def test_positive_target_activity_candidate_scores_above_rare_edge() -> None:
    active = {"trade_allowed": True, "expected_usdc_per_day": 0.8, "validation_expected_usdc_per_day": 0.4, "trades_per_day": 4.0, "validation_trades_per_day": 3.0, "net_per_trade": 0.2, "fee_to_move_ratio": 0.4, "target_relevant": True}
    rare = {"trade_allowed": True, "expected_usdc_per_day": 0.02, "validation_expected_usdc_per_day": 0.0, "trades_per_day": 0.01, "validation_trades_per_day": 0.0, "net_per_trade": 2.0, "fee_to_move_ratio": 0.1, "target_relevant": False}

    assert _target_aware_score(active) > _target_aware_score(rare)


def test_cluster_router_smoke_uses_new_search_passes_and_diagnostics() -> None:
    training = _trend_candles(360)
    blindtest = _trend_candles(180)
    split = TrainBlindSplit(
        "ETHUSDC",
        "1m",
        training,
        blindtest,
        training[0].open_time,
        training[-1].open_time,
        blindtest[0].open_time,
        blindtest[-1].open_time,
    )

    report = build_cluster_router_report("run_20260623_smoke", split)
    summary = report.rejection_summary

    assert report.router_artifact["training_only"] is True
    assert report.router_artifact["blindtest_learning_allowed"] is False
    assert summary["opportunity_search_pass_used"] is True
    assert summary["opportunity_search_pass_name"] == "opportunity_mining"
    assert summary["mined_training_opportunity_count"] >= 0
    assert set(summary["search_pass_summary"]).issuperset({"primary", "activity_expansion", "target_activity", "opportunity_mining"})
    assert summary["search_pass_summary"]["opportunity_mining"]["candidate_count"] > 0
    assert summary["best_activity_candidate"] is not None
    assert summary["best_target_candidate"] is not None
    assert "best_fee_survivor_candidate" in summary
    assert all(row.get("setup_name") != "cluster_router_situation_router_lb30_th0.006_tp0.012_sl0.006_hold240" for row in report.selected_setups)
    if not report.selected_setups:
        assert summary["optimizer_status"] == "optimizer_search_space_failed"
        assert summary["opportunity_pass_rejected_count"] > 0
    assert report.blindtest_used_frozen_router == bool(report.selected_setups)