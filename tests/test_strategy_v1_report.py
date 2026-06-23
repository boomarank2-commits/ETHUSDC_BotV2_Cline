from dataclasses import fields

import src.backtest.strategy_v1_report as report_module
from src.backtest.strategy_v1 import StrategyV1Candidate, StrategyV1Result, StrategyV1Trade
from src.backtest.strategy_v1_report import (
    StrategyV1TrainingBlindtestReport,
    build_strategy_v1_training_blindtest_report,
    load_strategy_v1_report,
    save_strategy_v1_report,
)
from src.data.candle_schema import Candle
from src.data.train_blind_split import TrainBlindSplit


def _candle(index: int) -> Candle:
    return Candle(f"2026-01-0{1 + index // 2}T00:0{index % 2}:00", 100.0, 100.0, 100.0, 100.0, 1.0)


def _split() -> TrainBlindSplit:
    training = [_candle(0), _candle(1)]
    blindtest = [_candle(2), _candle(3), _candle(4)]
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


def _candidate() -> StrategyV1Candidate:
    return StrategyV1Candidate(
        "momentum_breakout", "selected", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0
    )


def _trade(day: str, pnl: float) -> StrategyV1Trade:
    return StrategyV1Trade(
        day,
        day,
        100.0,
        101.0,
        100.0,
        1.0,
        pnl,
        0.2,
        pnl,
        pnl,
        "max_hold",
        "momentum_breakout",
        "selected",
    )


def test_blindtest_uses_exact_training_candidate(monkeypatch) -> None:
    selected = _candidate()
    used: list[StrategyV1Candidate] = []
    monkeypatch.setattr(
        report_module,
        "select_best_strategy_v1",
        lambda candles, start_capital_reference, progress_callback=None: StrategyV1Result(
            selected, 100.0, 100.0, 110.0, 10.0, 10.0, 1.0, 1, 1, 0, 0, 0.0, []
        ),
    )

    def fake_run(candles, candidate, start_capital_reference=100.0):
        used.append(candidate)
        return StrategyV1Result(candidate, 100.0, 100.0, 101.0, 1.0, 1.0, 1.0, 1, 1, 0, 0, 0.0, [])

    monkeypatch.setattr(report_module, "run_strategy_v1_on_candles", fake_run)
    report = build_strategy_v1_training_blindtest_report("run_20260612_240001", _split())

    assert report.selected_candidate == selected
    assert used == [selected]


def test_daily_stats_are_calculated(monkeypatch) -> None:
    selected = _candidate()
    monkeypatch.setattr(
        report_module,
        "select_best_strategy_v1",
        lambda candles, start_capital_reference, progress_callback=None: StrategyV1Result(
            selected, 100.0, 100.0, 110.0, 10.0, 10.0, 1.0, 1, 1, 0, 0, 0.0, []
        ),
    )
    monkeypatch.setattr(
        report_module,
        "run_strategy_v1_on_candles",
        lambda candles, candidate, start_capital_reference=100.0: StrategyV1Result(
            candidate,
            100.0,
            100.0,
            100.0,
            0.0,
            0.0,
            0.0,
            2,
            1,
            1,
            0,
            1.0,
            [_trade("2026-01-02", 2.0), _trade("2026-01-03", -1.0)],
        ),
    )

    report = build_strategy_v1_training_blindtest_report("run_20260612_240002", _split())

    assert report.positive_days == 1
    assert report.negative_days == 1
    assert report.best_day_pnl == 2.0
    assert report.worst_day_pnl == -1.0


def test_report_stores_blindtest_trade_costs_distributions_and_chain_status(monkeypatch) -> None:
    selected = _candidate()
    evaluations = [
        report_module.StrategyV1CandidateEvaluation(
            candidate=selected,
            train_trade_count=2,
            train_gross_pnl=2.0,
            train_fees=0.4,
            train_net_pnl=1.6,
            train_pnl_per_day=0.8,
            train_trades_per_month=0.0834,
            raw_score=1.6,
            low_activity_penalty=0.0,
            adjusted_score=1.6,
            low_activity_penalty_applied=False,
            train_win_rate=0.5,
            score=1.6,
            selected=True,
            reason="selected best final training stability score",
            adjusted_score_final=1.6,
        )
    ]
    blindtest_trades = [_trade("2026-01-02", 2.0), _trade("2026-01-03", -1.0)]
    monkeypatch.setattr(
        report_module,
        "evaluate_strategy_v1_candidates",
        lambda *args, **kwargs: (
            StrategyV1Result(selected, 100.0, 100.0, 101.6, 1.6, 1.6, 0.8, 2, 1, 1, 0, 0.0, [], 3, 4, 0),
            evaluations,
        ),
    )
    monkeypatch.setattr(
        report_module,
        "run_strategy_v1_on_candles",
        lambda candles, candidate, start_capital_reference=100.0, context_by_symbol=None: StrategyV1Result(
            candidate,
            100.0,
            100.0,
            101.0,
            1.0,
            1.0,
            1.0,
            2,
            1,
            1,
            0,
            1.0,
            blindtest_trades,
            5,
            7,
            1,
        ),
    )

    report = build_strategy_v1_training_blindtest_report("run_20260612_240010", _split())

    assert len(report.blindtest_trades) == 2
    assert report.blindtest_trades[0]["gross_pnl"] == 2.0
    assert report.blindtest_trades[0]["fees_paid"] == 0.2
    assert report.blindtest_trades[0]["slippage"] == 0.0
    assert report.blindtest_gross_pnl == 1.0
    assert report.blindtest_fees == 0.4
    assert report.blindtest_exit_reasons == {"max_hold": 2}
    assert report.blindtest_signal_count == 5
    assert report.blindtest_no_trade_count == 7
    assert report.blindtest_blocked_signal_count == 1
    assert report.blindtest_daily_distribution[0]["period"] == "2026-01-02"
    assert report.blindtest_monthly_distribution[0]["period"] == "2026-01"
    assert report.candidate_train_blind_outcomes[0]["training_positive"] is True
    assert report.candidate_train_blind_outcomes[0]["blindtest_positive"] is True
    assert report.target_model_chain["current_implementation"] == "Strategy V1 candidate search -> selected candidate -> blindtest"
    assert report.target_model_chain["router_frozen"] is False


def test_strategy_v1_report_save_and_load(monkeypatch) -> None:
    selected = _candidate()
    monkeypatch.setattr(
        report_module,
        "select_best_strategy_v1",
        lambda candles, start_capital_reference, progress_callback=None: StrategyV1Result(
            selected, 100.0, 100.0, 110.0, 10.0, 10.0, 1.0, 1, 1, 0, 0, 0.0, []
        ),
    )
    monkeypatch.setattr(
        report_module,
        "run_strategy_v1_on_candles",
        lambda candles, candidate, start_capital_reference=100.0: StrategyV1Result(
            candidate, 100.0, 100.0, 101.0, 1.0, 1.0, 1.0, 1, 1, 0, 0, 0.0, []
        ),
    )
    report = build_strategy_v1_training_blindtest_report("run_20260612_240003", _split())

    save_strategy_v1_report(report)

    assert load_strategy_v1_report(report.run_id) == report


def test_report_uses_selected_stake_quote_amount(monkeypatch) -> None:
    selected = _candidate()
    used: list[StrategyV1Candidate] = []
    monkeypatch.setattr(
        report_module,
        "select_best_strategy_v1",
        lambda candles, start_capital_reference, progress_callback=None: StrategyV1Result(
            selected, 100.0, 100.0, 110.0, 10.0, 10.0, 1.0, 1, 1, 0, 0, 0.0, []
        ),
    )

    def fake_run(candles, candidate, start_capital_reference=100.0):
        used.append(candidate)
        return StrategyV1Result(
            candidate,
            100.0,
            candidate.stake_quote_amount,
            101.0,
            1.0,
            1.0,
            1.0,
            1,
            1,
            0,
            0,
            0.0,
            [],
        )

    monkeypatch.setattr(report_module, "run_strategy_v1_on_candles", fake_run)

    report = build_strategy_v1_training_blindtest_report(
        "run_20260612_240004", _split(), stake_quote_amount=500.0
    )

    assert report.stake_quote_amount == 500.0
    assert report.selected_candidate.stake_quote_amount == 500.0
    assert used[0].stake_quote_amount == 500.0


def test_report_stores_profile(monkeypatch) -> None:
    selected = _candidate()
    monkeypatch.setattr(
        report_module,
        "select_best_strategy_v1",
        lambda candles, start_capital_reference, progress_callback=None: StrategyV1Result(
            selected, 100.0, 100.0, 110.0, 10.0, 10.0, 1.0, 1, 1, 0, 0, 0.0, []
        ),
    )
    monkeypatch.setattr(
        report_module,
        "run_strategy_v1_on_candles",
        lambda candles, candidate, start_capital_reference=100.0: StrategyV1Result(
            candidate,
            100.0,
            candidate.stake_quote_amount,
            101.0,
            1.0,
            1.0,
            1.0,
            1,
            1,
            0,
            0,
            0.0,
            [],
        ),
    )

    report = build_strategy_v1_training_blindtest_report(
        "run_20260612_240005", _split(), profile="aggressive"
    )

    assert report.profile == "aggressive"


def test_report_stores_candidate_selection_diagnostics(monkeypatch) -> None:
    selected = _candidate()
    context_candidate = StrategyV1Candidate(
        "momentum_breakout", "context", 1, None, 0.001, 0.004, 0.004, 2, 0, 10.0, 100.0, use_context_filter=True
    )
    evaluations = [
        report_module.StrategyV1CandidateEvaluation(
            candidate=selected,
            train_trade_count=2,
            train_gross_pnl=1.0,
            train_fees=0.2,
            train_net_pnl=0.8,
            train_pnl_per_day=0.4,
            train_trades_per_month=0.0834,
            raw_score=0.8,
            low_activity_penalty=0.04,
            adjusted_score=0.76,
            low_activity_penalty_applied=True,
            train_win_rate=0.5,
            score=0.76,
            selected=True,
            reason="selected best training score",
            adjusted_score_final=0.76,
        ),
        report_module.StrategyV1CandidateEvaluation(
            candidate=context_candidate,
            train_trade_count=1,
            train_gross_pnl=0.5,
            train_fees=0.2,
            train_net_pnl=0.3,
            train_pnl_per_day=0.15,
            train_trades_per_month=0.0417,
            raw_score=0.3,
            low_activity_penalty=0.46,
            adjusted_score=-0.16,
            low_activity_penalty_applied=True,
            train_win_rate=1.0,
            score=-0.16,
            selected=False,
            reason="lower training score",
            adjusted_score_final=-0.16,
        ),
    ]
    monkeypatch.setattr(
        report_module,
        "evaluate_strategy_v1_candidates",
        lambda *args, **kwargs: (
            StrategyV1Result(selected, 100.0, 100.0, 100.8, 0.8, 0.8, 0.4, 2, 1, 1, 0, 0.0, []),
            evaluations,
        ),
    )
    monkeypatch.setattr(
        report_module,
        "run_strategy_v1_on_candles",
        lambda candles, candidate, start_capital_reference=100.0, context_by_symbol=None: StrategyV1Result(
            candidate, 100.0, 100.0, 101.0, 1.0, 1.0, 1.0, 1, 1, 0, 0, 0.0, []
        ),
    )

    report = build_strategy_v1_training_blindtest_report("run_20260612_240008", _split())

    assert report.total_candidates == 2
    assert report.context_candidate_count == 1
    assert report.non_context_candidate_count == 1
    assert report.context_candidates_with_trades == 1
    assert report.selected_candidate_use_context_filter is False
    assert report.best_context_candidate["name"] == "context"
    assert len(report.top_10_candidates_by_score) == 2
    assert report.selected_candidate_raw_score == 0.8
    assert report.selected_candidate_adjusted_score_before_stability == 0.76
    assert report.selected_candidate_adjusted_score_final == 0.76
    assert report.best_candidate_after_stability["name"] == "selected"
    assert len(report.top_10_candidates_by_final_score) == 2
    assert report.training_stability_metrics["name"] == "selected"
    assert report.no_robust_positive_candidate is False
    assert report.candidate_space_status == "robust_positive_candidate_found"
    assert report.best_final_training_score == 0.76
    assert report.candidate_space_total_before_extension == 144
    assert report.candidate_space_total_after_extension == 2
    assert report.best_training_quote_per_day == 0.4
    assert report.target_feasibility_status == "target_out_of_reach_current_space"
    assert report.target_min_training_ratio == 0.4 / 1.5


def test_report_marks_no_robust_positive_candidate(monkeypatch) -> None:
    selected = _candidate()
    evaluations = [
        report_module.StrategyV1CandidateEvaluation(
            candidate=selected,
            train_trade_count=31,
            train_gross_pnl=0.0,
            train_fees=0.2,
            train_net_pnl=-0.2,
            train_pnl_per_day=-0.1,
            train_trades_per_month=1.2,
            raw_score=-0.2,
            low_activity_penalty=0.0,
            adjusted_score=-0.2,
            low_activity_penalty_applied=False,
            train_win_rate=0.4,
            score=-1.0,
            selected=True,
            reason="selected best final training stability score",
            adjusted_score_final=-1.0,
        )
    ]
    monkeypatch.setattr(
        report_module,
        "evaluate_strategy_v1_candidates",
        lambda *args, **kwargs: (
            StrategyV1Result(selected, 100.0, 100.0, 99.8, -0.2, -0.2, -0.1, 31, 10, 21, 0, 1.0, []),
            evaluations,
        ),
    )
    monkeypatch.setattr(
        report_module,
        "run_strategy_v1_on_candles",
        lambda candles, candidate, start_capital_reference=100.0, context_by_symbol=None: StrategyV1Result(
            candidate, 100.0, 100.0, 100.0, 0.0, 0.0, 0.0, 0, 0, 0, 0, 0.0, []
        ),
    )

    report = build_strategy_v1_training_blindtest_report("run_20260612_240009", _split())

    assert report.no_robust_positive_candidate is True
    assert report.candidate_space_status == "no_robust_positive_candidate"
    assert report.best_final_training_score == -1.0
    assert "not robust positive" in report.candidate_space_reason
    assert report.target_feasibility_status == "target_out_of_reach_current_space"


def test_report_emits_training_and_blindtest_progress(monkeypatch) -> None:
    selected = _candidate()
    events: list[dict] = []

    def fake_select(candles, start_capital_reference, progress_callback=None):
        progress_callback(
            {
                "phase": "strategy_v1_training_started",
                "current_candidate": 1,
                "total_candidates": 1,
                "progress_pct": 80.0,
            }
        )
        return StrategyV1Result(selected, 100.0, 100.0, 110.0, 10.0, 10.0, 1.0, 1, 1, 0, 0, 0.0, [])

    monkeypatch.setattr(report_module, "select_best_strategy_v1", fake_select)
    monkeypatch.setattr(
        report_module,
        "run_strategy_v1_on_candles",
        lambda candles, candidate, start_capital_reference=100.0: StrategyV1Result(
            candidate,
            100.0,
            candidate.stake_quote_amount,
            101.0,
            1.0,
            1.0,
            1.0,
            1,
            1,
            0,
            0,
            0.0,
            [],
        ),
    )

    build_strategy_v1_training_blindtest_report(
        "run_20260612_240007", _split(), progress_callback=events.append
    )

    phases = [event.get("phase") for event in events]
    assert "strategy_v1_training_started" in phases
    assert "strategy_v1_blindtest_started" in phases
    assert "strategy_v1_blindtest_completed" in phases


def test_invalid_profile_is_rejected() -> None:
    try:
        build_strategy_v1_training_blindtest_report(
            "run_20260612_240006", _split(), profile="invalid"
        )
    except ValueError as error:
        assert "profile" in str(error)
    else:
        raise AssertionError("invalid profile must fail")


def test_no_short_futures_margin_or_leverage_fields() -> None:
    field_names = {field.name for field in fields(StrategyV1TrainingBlindtestReport)}

    assert "short" not in field_names
    assert "futures" not in field_names
    assert "margin" not in field_names
    assert "leverage" not in field_names
