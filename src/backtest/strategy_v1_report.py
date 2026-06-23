"""Strategy V1 training/blindtest report persistence."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from src.backtest.strategy_v1 import (
    MIN_ROBUST_FINAL_TRAINING_SCORE,
    StrategyV1CandidateEvaluation,
    StrategyV1Candidate,
    StrategyV1Trade,
    evaluate_strategy_v1_candidates,
    run_strategy_v1_on_candles,
    select_best_strategy_v1,
)
from src.common.config import CONFIG
from src.common.report_paths import ensure_run_report_dir, get_run_report_dir
from src.data.train_blind_split import TrainBlindSplit
from src.data.local_candle_loader import load_local_candle_dataset_from_catalog

STRATEGY_V1_REPORT_FILENAME = "strategy_v1_report.json"
_ORIGINAL_SELECT_BEST_STRATEGY_V1 = select_best_strategy_v1
TARGET_MIN_QUOTE_PER_DAY = 1.5
TARGET_MAX_QUOTE_PER_DAY = 3.0


@dataclass(frozen=True)
class StrategyV1TrainingBlindtestReport:
    """Training-selected Strategy V1 result on blindtest candles."""

    run_id: str
    symbol: str
    quote_asset: str
    start_capital_reference: float
    stake_quote_amount: float
    profile: str
    selected_candidate: StrategyV1Candidate
    training_family: str
    training_final_capital_reference: float
    training_total_net_pnl: float
    training_total_net_pnl_pct: float
    training_quote_per_day: float
    training_trade_count: int
    blindtest_final_capital_reference: float
    blindtest_total_net_pnl: float
    blindtest_total_net_pnl_pct: float
    blindtest_quote_per_day: float
    blindtest_trade_count: int
    blindtest_winning_trades: int
    blindtest_losing_trades: int
    blindtest_neutral_trades: int
    blindtest_max_drawdown: float
    blindtest_start: str
    blindtest_end: str
    positive_days: int
    negative_days: int
    neutral_days: int
    best_day_pnl: float
    worst_day_pnl: float
    all_training_candidates: list[StrategyV1CandidateEvaluation] = field(default_factory=list)
    context_symbols_used: list[str] = field(default_factory=list)
    context_reason: str = "not available"
    total_candidates: int = 0
    context_candidate_count: int = 0
    non_context_candidate_count: int = 0
    context_candidates_with_trades: int = 0
    context_candidates_zero_trades: int = 0
    selected_candidate_use_context_filter: bool = False
    best_context_candidate: dict[str, Any] | None = None
    best_non_context_candidate: dict[str, Any] | None = None
    top_10_candidates_by_score: list[dict[str, Any]] = field(default_factory=list)
    selection_diagnosis: str = "not available"
    selected_candidate_raw_score: float = 0.0
    selected_candidate_adjusted_score_before_stability: float = 0.0
    selected_candidate_adjusted_score_final: float = 0.0
    selected_candidate_stability_diagnosis: str = "not available"
    best_candidate_before_stability: dict[str, Any] | None = None
    best_candidate_after_stability: dict[str, Any] | None = None
    top_10_candidates_by_final_score: list[dict[str, Any]] = field(default_factory=list)
    training_stability_metrics: dict[str, Any] = field(default_factory=dict)
    selection_reason: str = "not available"
    no_robust_positive_candidate: bool = False
    candidate_space_status: str = "not available"
    candidate_space_reason: str = "not available"
    best_final_training_score: float = 0.0
    candidate_space_total_before_extension: int = 144
    candidate_space_total_after_extension: int = 0
    best_training_quote_per_day: float = 0.0
    target_min_quote_per_day: float = TARGET_MIN_QUOTE_PER_DAY
    target_max_quote_per_day: float = TARGET_MAX_QUOTE_PER_DAY
    target_min_training_ratio: float = 0.0
    target_max_training_ratio: float = 0.0
    target_feasibility_status: str = "not available"
    target_feasibility_reason: str = "not available"
    blindtest_trades: list[dict[str, Any]] = field(default_factory=list)
    blindtest_gross_pnl: float = 0.0
    blindtest_fees: float = 0.0
    blindtest_slippage: float = 0.0
    blindtest_exit_reasons: dict[str, int] = field(default_factory=dict)
    blindtest_signal_count: int = 0
    blindtest_no_trade_count: int = 0
    blindtest_blocked_signal_count: int = 0
    blindtest_daily_distribution: list[dict[str, Any]] = field(default_factory=list)
    blindtest_monthly_distribution: list[dict[str, Any]] = field(default_factory=list)
    candidate_train_blind_outcomes: list[dict[str, Any]] = field(default_factory=list)
    target_model_chain: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        get_run_report_dir(self.run_id)


def _get_strategy_v1_report_path(run_id: str) -> Path:
    return get_run_report_dir(run_id) / STRATEGY_V1_REPORT_FILENAME


def _daily_pnls(trades: list[StrategyV1Trade]) -> dict[str, float]:
    daily: dict[str, float] = {}
    for trade in trades:
        day = trade.exit_time[:10]
        daily[day] = daily.get(day, 0.0) + trade.net_pnl
    return daily


def _trade_to_dict(trade: StrategyV1Trade) -> dict[str, Any]:
    return {
        "entry_time": trade.entry_time,
        "exit_time": trade.exit_time,
        "entry_price": trade.entry_price,
        "exit_price": trade.exit_price,
        "stake_quote_amount": trade.stake_quote_amount,
        "quantity": trade.quantity,
        "gross_pnl": trade.gross_pnl,
        "fees_paid": trade.fees_paid,
        "slippage": 0.0,
        "net_pnl": trade.net_pnl,
        "net_pnl_pct": trade.net_pnl_pct,
        "exit_reason": trade.exit_reason,
        "family": trade.family,
        "candidate_name": trade.candidate_name,
    }


def _period_distribution(trades: list[StrategyV1Trade], period_length: int) -> list[dict[str, Any]]:
    periods: dict[str, dict[str, Any]] = {}
    for trade in trades:
        period = trade.exit_time[:period_length]
        row = periods.setdefault(
            period,
            {
                "period": period,
                "gross_pnl": 0.0,
                "fees": 0.0,
                "slippage": 0.0,
                "net_pnl": 0.0,
                "trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "neutral_trades": 0,
            },
        )
        row["gross_pnl"] += trade.gross_pnl
        row["fees"] += trade.fees_paid
        row["net_pnl"] += trade.net_pnl
        row["trades"] += 1
        if trade.net_pnl > 0:
            row["winning_trades"] += 1
        elif trade.net_pnl < 0:
            row["losing_trades"] += 1
        else:
            row["neutral_trades"] += 1
    return [periods[key] for key in sorted(periods)]


def _exit_reason_counts(trades: list[StrategyV1Trade]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trade in trades:
        counts[trade.exit_reason] = counts.get(trade.exit_reason, 0) + 1
    return counts


def _candidate_summary(evaluation: StrategyV1CandidateEvaluation) -> dict[str, Any]:
    return {
        "name": evaluation.candidate.name,
        "family": evaluation.candidate.family,
        "use_context_filter": evaluation.candidate.use_context_filter,
        "score": evaluation.score,
        "raw_score": evaluation.raw_score,
        "adjusted_score": evaluation.adjusted_score,
        "adjusted_score_final": evaluation.adjusted_score_final,
        "low_activity_penalty": evaluation.low_activity_penalty,
        "low_activity_penalty_applied": evaluation.low_activity_penalty_applied,
        "stability_penalty": evaluation.stability_penalty,
        "drawdown_penalty": evaluation.drawdown_penalty,
        "concentration_penalty": evaluation.concentration_penalty,
        "train_trade_count": evaluation.train_trade_count,
        "train_trades_per_month": evaluation.train_trades_per_month,
        "train_net_pnl": evaluation.train_net_pnl,
        "train_pnl_per_day": evaluation.train_pnl_per_day,
        "train_win_rate": evaluation.train_win_rate,
        "training_positive_months": evaluation.training_positive_months,
        "training_negative_months": evaluation.training_negative_months,
        "training_active_months": evaluation.training_active_months,
        "training_total_months": evaluation.training_total_months,
        "training_max_drawdown": evaluation.training_max_drawdown,
        "training_best_trade_pnl": evaluation.training_best_trade_pnl,
        "training_worst_trade_pnl": evaluation.training_worst_trade_pnl,
        "training_top_trade_profit_share": evaluation.training_top_trade_profit_share,
        "training_profit_concentration_warning": evaluation.training_profit_concentration_warning,
        "stability_diagnosis": evaluation.stability_diagnosis,
        "reason": evaluation.reason,
    }


def _build_selection_diagnostics(
    evaluations: list[StrategyV1CandidateEvaluation],
    selected: StrategyV1Candidate,
) -> dict[str, Any]:
    context = [item for item in evaluations if item.candidate.use_context_filter]
    non_context = [item for item in evaluations if not item.candidate.use_context_filter]
    best_context = max(context, key=lambda item: item.score) if context else None
    best_non_context = max(non_context, key=lambda item: item.score) if non_context else None
    best_before_stability = max(evaluations, key=lambda item: item.adjusted_score) if evaluations else None
    best_after_stability = max(evaluations, key=lambda item: item.adjusted_score_final) if evaluations else None
    best_by_training_day = max(evaluations, key=lambda item: item.train_pnl_per_day) if evaluations else None
    selected_evaluation = next((item for item in evaluations if item.candidate == selected), None)
    best_final_score = best_after_stability.adjusted_score_final if best_after_stability else 0.0
    best_training_quote_per_day = best_by_training_day.train_pnl_per_day if best_by_training_day else 0.0
    target_min_ratio = best_training_quote_per_day / TARGET_MIN_QUOTE_PER_DAY
    target_max_ratio = best_training_quote_per_day / TARGET_MAX_QUOTE_PER_DAY
    target_feasibility_status = (
        "target_training_range_reached"
        if best_training_quote_per_day >= TARGET_MIN_QUOTE_PER_DAY
        else "target_out_of_reach_current_space"
    )
    no_robust_positive = best_after_stability is None or best_final_score <= MIN_ROBUST_FINAL_TRAINING_SCORE
    candidate_space_status = "no_robust_positive_candidate" if no_robust_positive else "robust_positive_candidate_found"
    if not evaluations:
        diagnosis = "candidate audit unavailable"
    elif selected.use_context_filter:
        diagnosis = "selected candidate uses context filter"
    elif best_context is None:
        diagnosis = "no context candidates were evaluated"
    elif best_context.score < (best_non_context.score if best_non_context else best_context.score):
        diagnosis = (
            "context candidates were evaluated and mostly traded, but the best non-context "
            "candidate had the highest adjusted training score"
        )
    else:
        diagnosis = "non-context candidate selected despite context score comparison; inspect selection logic"
    return {
        "total_candidates": len(evaluations),
        "context_candidate_count": len(context),
        "non_context_candidate_count": len(non_context),
        "context_candidates_with_trades": sum(1 for item in context if item.train_trade_count > 0),
        "context_candidates_zero_trades": sum(1 for item in context if item.train_trade_count == 0),
        "selected_candidate_use_context_filter": selected.use_context_filter,
        "best_context_candidate": _candidate_summary(best_context) if best_context else None,
        "best_non_context_candidate": _candidate_summary(best_non_context) if best_non_context else None,
        "top_10_candidates_by_score": [
            _candidate_summary(item) for item in sorted(evaluations, key=lambda item: item.score, reverse=True)[:10]
        ],
        "selection_diagnosis": diagnosis,
        "selected_candidate_raw_score": selected_evaluation.raw_score if selected_evaluation else 0.0,
        "selected_candidate_adjusted_score_before_stability": selected_evaluation.adjusted_score if selected_evaluation else 0.0,
        "selected_candidate_adjusted_score_final": selected_evaluation.adjusted_score_final if selected_evaluation else 0.0,
        "selected_candidate_stability_diagnosis": selected_evaluation.stability_diagnosis if selected_evaluation else "not available",
        "best_candidate_before_stability": _candidate_summary(best_before_stability) if best_before_stability else None,
        "best_candidate_after_stability": _candidate_summary(best_after_stability) if best_after_stability else None,
        "top_10_candidates_by_final_score": [
            _candidate_summary(item) for item in sorted(evaluations, key=lambda item: item.adjusted_score_final, reverse=True)[:10]
        ],
        "training_stability_metrics": _candidate_summary(selected_evaluation) if selected_evaluation else {},
        "selection_reason": selected_evaluation.reason if selected_evaluation else "candidate audit unavailable",
        "no_robust_positive_candidate": no_robust_positive,
        "candidate_space_status": candidate_space_status,
        "candidate_space_reason": (
            "best final training score is not robust positive after costs, intrabar exits and stability penalties"
            if no_robust_positive
            else "best final training score is positive after costs, intrabar exits and stability penalties"
        ),
        "best_final_training_score": best_final_score,
        "candidate_space_total_after_extension": len(evaluations),
        "best_training_quote_per_day": best_training_quote_per_day,
        "target_min_quote_per_day": TARGET_MIN_QUOTE_PER_DAY,
        "target_max_quote_per_day": TARGET_MAX_QUOTE_PER_DAY,
        "target_min_training_ratio": target_min_ratio,
        "target_max_training_ratio": target_max_ratio,
        "target_feasibility_status": target_feasibility_status,
        "target_feasibility_reason": (
            "best training-only candidate is far below the requested 1.5-3.0 USDC/day range"
            if target_feasibility_status == "target_out_of_reach_current_space"
            else "best training-only candidate reaches the requested 1.5-3.0 USDC/day range before blindtest"
        ),
    }


def _candidate_train_blind_outcomes(
    evaluations: list[StrategyV1CandidateEvaluation],
    selected: StrategyV1Candidate,
    blindtest_result: object,
) -> list[dict[str, Any]]:
    outcomes: list[dict[str, Any]] = []
    for evaluation in evaluations:
        is_selected = evaluation.candidate == selected
        blind_net_pnl = getattr(blindtest_result, "total_net_pnl", None) if is_selected else None
        blind_trade_count = getattr(blindtest_result, "trade_count", None) if is_selected else None
        blind_positive = blind_net_pnl is not None and blind_net_pnl > 0
        outcomes.append(
            {
                "name": evaluation.candidate.name,
                "family": evaluation.candidate.family,
                "use_context_filter": evaluation.candidate.use_context_filter,
                "selected": is_selected,
                "training_positive": evaluation.train_net_pnl > 0,
                "training_negative": evaluation.train_net_pnl < 0,
                "training_net_pnl": evaluation.train_net_pnl,
                "training_trade_count": evaluation.train_trade_count,
                "training_score_final": evaluation.adjusted_score_final,
                "blindtest_known": is_selected,
                "blindtest_positive": blind_positive if is_selected else None,
                "blindtest_negative": (blind_net_pnl < 0) if blind_net_pnl is not None else None,
                "blindtest_net_pnl": blind_net_pnl,
                "blindtest_trade_count": blind_trade_count,
                "discard_reason": "selected for frozen blindtest" if is_selected else evaluation.reason,
            }
        )
    return outcomes


def _target_model_chain_status(
    evaluations: list[StrategyV1CandidateEvaluation],
    training_result: object,
    blindtest_result: object,
) -> dict[str, Any]:
    signal_count = int(getattr(training_result, "signal_count", 0))
    trade_count = int(getattr(training_result, "trade_count", 0))
    return {
        "current_implementation": "Strategy V1 candidate search -> selected candidate -> blindtest",
        "target_model": "Situation -> Cluster -> Router -> Setup -> Trade",
        "opportunity_events_detected": signal_count,
        "candidate_situation_count": len(evaluations),
        "situation_clusters_built": False,
        "situation_cluster_count": 0,
        "setup_learning_done": False,
        "learned_setup_count": 0,
        "adoption_allowed_setup_count": 0,
        "trade_allowed_setup_count": 0,
        "router_frozen": False,
        "router_artifact_path": None,
        "router_trade_signals": 0,
        "blindtest_used_frozen_router": False,
        "engine_entry_attempts": int(getattr(blindtest_result, "signal_count", 0)),
        "engine_entry_executions": int(getattr(blindtest_result, "trade_count", 0)),
        "training_trades": trade_count,
        "blindtest_trades": int(getattr(blindtest_result, "trade_count", 0)),
        "next_blocker": "Build and freeze real Situation->Cluster->Setup->Router chain before judging target model performance",
    }


def build_strategy_v1_training_blindtest_report(
    run_id: str,
    split: TrainBlindSplit,
    start_capital_reference: float = 100.0,
    stake_quote_amount: float = 100.0,
    profile: str = "normal",
    progress_callback: Callable[[dict], None] | None = None,
) -> StrategyV1TrainingBlindtestReport:
    """Train on training candles, then run frozen V1 candidate on blindtest candles."""
    get_run_report_dir(run_id)
    if profile not in ("conservative", "normal", "aggressive"):
        msg = "profile must be conservative, normal or aggressive"
        raise ValueError(msg)
    context_by_symbol, context_symbols, context_reason = _load_context_by_symbol(split)
    if select_best_strategy_v1 is _ORIGINAL_SELECT_BEST_STRATEGY_V1:
        training_result, all_training_candidates = evaluate_strategy_v1_candidates(
            split.training_candles,
            start_capital_reference,
            profile=profile,
            context_by_symbol=context_by_symbol,
            progress_callback=progress_callback,
        )
    else:
        try:
            training_result = select_best_strategy_v1(
                split.training_candles,
                start_capital_reference,
                progress_callback=progress_callback,
                profile=profile,
                context_by_symbol=context_by_symbol,
            )
        except TypeError:
            training_result = select_best_strategy_v1(
                split.training_candles, start_capital_reference, progress_callback=progress_callback
            )
        all_training_candidates = []
    selected = StrategyV1Candidate(
        **{**asdict(training_result.candidate), "stake_quote_amount": stake_quote_amount}
    )
    if progress_callback is not None:
        progress_callback(
            {
                "phase": "strategy_v1_blindtest_started",
                "progress_pct": 82.0,
                "detail": "Strategy V1 Blindtest läuft",
            }
        )
    try:
        blindtest_result = run_strategy_v1_on_candles(
            split.blindtest_candles, selected, start_capital_reference, context_by_symbol
        )
    except TypeError:
        blindtest_result = run_strategy_v1_on_candles(
            split.blindtest_candles, selected, start_capital_reference
        )
    if progress_callback is not None:
        progress_callback(
            {
                "phase": "strategy_v1_blindtest_completed",
                "progress_pct": 88.0,
                "detail": "Strategy V1 Blindtest abgeschlossen",
            }
        )
    daily = _daily_pnls(blindtest_result.trades)
    daily_values = list(daily.values())
    diagnostics = _build_selection_diagnostics(all_training_candidates, selected)
    blindtest_gross_pnl = sum(trade.gross_pnl for trade in blindtest_result.trades)
    blindtest_fees = sum(trade.fees_paid for trade in blindtest_result.trades)
    return StrategyV1TrainingBlindtestReport(
        run_id=run_id,
        symbol=split.symbol,
        quote_asset=CONFIG.quote_asset,
        start_capital_reference=start_capital_reference,
        stake_quote_amount=stake_quote_amount,
        profile=profile,
        selected_candidate=selected,
        training_family=selected.family,
        training_final_capital_reference=training_result.final_capital_reference,
        training_total_net_pnl=training_result.total_net_pnl,
        training_total_net_pnl_pct=training_result.total_net_pnl_pct,
        training_quote_per_day=training_result.quote_per_day,
        training_trade_count=training_result.trade_count,
        blindtest_final_capital_reference=blindtest_result.final_capital_reference,
        blindtest_total_net_pnl=blindtest_result.total_net_pnl,
        blindtest_total_net_pnl_pct=blindtest_result.total_net_pnl_pct,
        blindtest_quote_per_day=blindtest_result.quote_per_day,
        blindtest_trade_count=blindtest_result.trade_count,
        blindtest_winning_trades=blindtest_result.winning_trades,
        blindtest_losing_trades=blindtest_result.losing_trades,
        blindtest_neutral_trades=blindtest_result.neutral_trades,
        blindtest_max_drawdown=blindtest_result.max_drawdown,
        blindtest_start=split.blindtest_start,
        blindtest_end=split.blindtest_end,
        positive_days=sum(1 for pnl in daily_values if pnl > 0),
        negative_days=sum(1 for pnl in daily_values if pnl < 0),
        neutral_days=sum(1 for pnl in daily_values if pnl == 0),
        best_day_pnl=max(daily_values, default=0.0),
        worst_day_pnl=min(daily_values, default=0.0),
        all_training_candidates=all_training_candidates,
        context_symbols_used=context_symbols,
        context_reason=context_reason,
        blindtest_trades=[_trade_to_dict(trade) for trade in blindtest_result.trades],
        blindtest_gross_pnl=blindtest_gross_pnl,
        blindtest_fees=blindtest_fees,
        blindtest_slippage=0.0,
        blindtest_exit_reasons=_exit_reason_counts(blindtest_result.trades),
        blindtest_signal_count=blindtest_result.signal_count,
        blindtest_no_trade_count=blindtest_result.no_trade_count,
        blindtest_blocked_signal_count=blindtest_result.blocked_signal_count,
        blindtest_daily_distribution=_period_distribution(blindtest_result.trades, 10),
        blindtest_monthly_distribution=_period_distribution(blindtest_result.trades, 7),
        candidate_train_blind_outcomes=_candidate_train_blind_outcomes(
            all_training_candidates, selected, blindtest_result
        ),
        target_model_chain=_target_model_chain_status(
            all_training_candidates, training_result, blindtest_result
        ),
        **diagnostics,
    )


def _load_context_by_symbol(split: TrainBlindSplit) -> tuple[dict[str, dict[str, object]] | None, list[str], str]:
    context: dict[str, dict[str, object]] = {}
    for symbol in ("BTCUSDC", "ETHBTC"):
        try:
            dataset = load_local_candle_dataset_from_catalog(symbol=symbol, interval="1m")
        except Exception:  # noqa: BLE001
            continue
        first_needed = split.training_start
        last_needed = split.blindtest_end
        by_time = {candle.open_time: candle for candle in dataset.candles if first_needed <= candle.open_time <= last_needed}
        if split.training_start in by_time and split.blindtest_end in by_time:
            context[symbol] = by_time
    if len(context) == 2:
        return context, sorted(context), "BTCUSDC and ETHBTC context available and aligned by candle timestamp"
    return None, [], "context unavailable or incomplete; non-context candidates remain eligible"


def save_strategy_v1_report(report: StrategyV1TrainingBlindtestReport) -> Path:
    """Save Strategy V1 report as readable JSON."""
    report_dir = ensure_run_report_dir(report.run_id)
    report_path = report_dir / STRATEGY_V1_REPORT_FILENAME
    content = json.dumps(asdict(report), indent=2, sort_keys=True)
    report_path.write_text(f"{content}\n", encoding="utf-8")
    return report_path


def load_strategy_v1_report(run_id: str) -> StrategyV1TrainingBlindtestReport:
    """Load and validate Strategy V1 report."""
    raw_report: dict[str, Any] = json.loads(
        _get_strategy_v1_report_path(run_id).read_text(encoding="utf-8")
    )
    raw_selected_candidate = dict(raw_report["selected_candidate"])
    raw_selected_candidate.setdefault("trailing_stop_pct", None)
    raw_report["selected_candidate"] = StrategyV1Candidate(**raw_selected_candidate)
    raw_report["all_training_candidates"] = [
        StrategyV1CandidateEvaluation(
            candidate=StrategyV1Candidate(**{**candidate["candidate"], "trailing_stop_pct": candidate["candidate"].get("trailing_stop_pct")}),
            train_trade_count=candidate["train_trade_count"],
            train_gross_pnl=candidate["train_gross_pnl"],
            train_fees=candidate["train_fees"],
            train_net_pnl=candidate["train_net_pnl"],
            train_pnl_per_day=candidate["train_pnl_per_day"],
            train_trades_per_month=candidate.get("train_trades_per_month", 0.0),
            raw_score=candidate.get("raw_score", candidate["score"]),
            low_activity_penalty=candidate.get("low_activity_penalty", 0.0),
            adjusted_score=candidate.get("adjusted_score", candidate["score"]),
            low_activity_penalty_applied=candidate.get("low_activity_penalty_applied", False),
            train_win_rate=candidate["train_win_rate"],
            score=candidate["score"],
            selected=candidate["selected"],
            reason=candidate["reason"],
            training_positive_months=candidate.get("training_positive_months", 0),
            training_negative_months=candidate.get("training_negative_months", 0),
            training_active_months=candidate.get("training_active_months", 0),
            training_total_months=candidate.get("training_total_months", 24),
            training_max_drawdown=candidate.get("training_max_drawdown", 0.0),
            training_best_trade_pnl=candidate.get("training_best_trade_pnl", 0.0),
            training_worst_trade_pnl=candidate.get("training_worst_trade_pnl", 0.0),
            training_top_trade_profit_share=candidate.get("training_top_trade_profit_share", 0.0),
            training_profit_concentration_warning=candidate.get("training_profit_concentration_warning", False),
            stability_penalty=candidate.get("stability_penalty", 0.0),
            drawdown_penalty=candidate.get("drawdown_penalty", 0.0),
            concentration_penalty=candidate.get("concentration_penalty", 0.0),
            adjusted_score_final=candidate.get("adjusted_score_final", candidate.get("adjusted_score", candidate["score"])),
            stability_diagnosis=candidate.get("stability_diagnosis", "not available"),
        )
        for candidate in raw_report.get("all_training_candidates", [])
    ]
    raw_report.setdefault("context_symbols_used", [])
    raw_report.setdefault("context_reason", "not available in older report")
    diagnostics = _build_selection_diagnostics(
        raw_report["all_training_candidates"], raw_report["selected_candidate"]
    )
    for key, value in diagnostics.items():
        raw_report.setdefault(key, value)
    raw_report.setdefault("candidate_space_total_before_extension", 144)
    raw_report.setdefault("best_training_quote_per_day", diagnostics.get("best_training_quote_per_day", 0.0))
    raw_report.setdefault("target_min_quote_per_day", TARGET_MIN_QUOTE_PER_DAY)
    raw_report.setdefault("target_max_quote_per_day", TARGET_MAX_QUOTE_PER_DAY)
    raw_report.setdefault("target_min_training_ratio", diagnostics.get("target_min_training_ratio", 0.0))
    raw_report.setdefault("target_max_training_ratio", diagnostics.get("target_max_training_ratio", 0.0))
    raw_report.setdefault("target_feasibility_status", diagnostics.get("target_feasibility_status", "not available"))
    raw_report.setdefault("target_feasibility_reason", diagnostics.get("target_feasibility_reason", "not available"))
    raw_report.setdefault("blindtest_trades", [])
    raw_report.setdefault("blindtest_gross_pnl", 0.0)
    raw_report.setdefault("blindtest_fees", 0.0)
    raw_report.setdefault("blindtest_slippage", 0.0)
    raw_report.setdefault("blindtest_exit_reasons", {})
    raw_report.setdefault("blindtest_signal_count", 0)
    raw_report.setdefault("blindtest_no_trade_count", 0)
    raw_report.setdefault("blindtest_blocked_signal_count", 0)
    raw_report.setdefault("blindtest_daily_distribution", [])
    raw_report.setdefault("blindtest_monthly_distribution", [])
    raw_report.setdefault("candidate_train_blind_outcomes", [])
    raw_report.setdefault("target_model_chain", {})
    return StrategyV1TrainingBlindtestReport(**raw_report)
