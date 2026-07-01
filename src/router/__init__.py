"""ETHUSDC router package patch layer."""

from array import array
from bisect import bisect_left
from dataclasses import asdict, replace

from src.data.derived_timeframes import (
    DerivedTimeframeFeatureSeries,
    build_closed_timeframe_feature_series,
    build_closed_timeframe_feature_snapshots,
)
from src.data.agg_trade_feature_series import (
    AGG_TRADE_METRICS,
    AggTradeFeatureSeries,
    build_closed_agg_trade_feature_series,
)
from src.data.agg_trade_data_ensure import load_agg_trade_data_status
from src.data.context_market_features import (
    CONTEXT_MARKET_METRICS,
    ContextMarketFeatureSeries,
    ContextMarketFeatureStore,
    build_closed_context_market_feature_store,
)
from src.data.kline_orderflow_features import (
    ORDERFLOW_METRICS,
    KlineOrderflowFeatureSeries,
    build_closed_kline_orderflow_feature_series,
)

from . import activity_first_router_report as _r

TEMPORAL_VALIDATION_SEGMENT_DAYS = 60
TEMPORAL_VALIDATION_MIN_SEGMENTS = 3
TEMPORAL_VALIDATION_MIN_ACTIVE_SEGMENTS = 2
TEMPORAL_VALIDATION_MIN_SEGMENT_TRADES = 3
TEMPORAL_VALIDATION_MIN_POSITIVE_ACTIVE_SEGMENT_RATE = 0.80
TARGET_FEASIBILITY_AUDIT_VERSION = "target_feasibility_v16_long_only_oracle"
WALKFORWARD_REGIME_RESEARCH_VERSION = "walkforward_regime_research_v17_training_only"
WALKFORWARD_STABILITY_POOL_SELECTION_VERSION = (
    "activity_first_v20_all_positive_walkforward_pool"
)
WALKFORWARD_STABILITY_REQUIRED_LABEL = "training_stable_positive"
WALKFORWARD_STABILITY_POLICY = "stable_only_when_stable_candidates_available"
WALKFORWARD_ALL_POSITIVE_POLICY = (
    "all_positive_folds_when_all_positive_candidates_available"
)
WALKFORWARD_ALL_POSITIVE_MIN_ACTIVE_FOLDS = 3
WALKFORWARD_REGIME_FOLD_DAYS = 90


def _ceil(value):
    whole = int(value)
    return whole if value <= whole else whole + 1


def _result_days(result):
    if result.trade_count <= 0 or result.trades_per_day <= 0:
        return 0.0
    return max(1.0, result.trade_count / result.trades_per_day)


def _run_days(evaluations):
    return max((_result_days(e.result) for e in evaluations), default=1.0)


def _active_days(trades):
    return len({trade.exit_time[:10] for trade in trades})


def _is_eth(result):
    return result.candidate.search_pass.startswith("eth_")


def _filter_learning_eligible(evaluation):
    """Allow filters to rescue ETH setups that have gross edge but lose to fees.

    The final filtered candidate is still evaluated by the unchanged activity,
    fee, profit-factor and drawdown gates.  This only widens which training-only
    candidates may *attempt* a frozen filter rule.
    """
    result = evaluation.result
    if not _is_eth(result):
        return False
    if result.trade_count < 40 or result.winning_trades < 20 or result.losing_trades < 20:
        return False
    if result.total_net_pnl > 0:
        return True
    if result.total_gross_pnl <= 0:
        return False
    fee_to_gross = result.total_fees / result.total_gross_pnl
    return fee_to_gross <= 1.50


def _filter_learning_scope(evaluation):
    result = evaluation.result
    if result.total_net_pnl > 0:
        return "net_positive_eth_candidate"
    return "gross_edge_fee_rescue_eth_candidate"


def _activity_ok(result):
    if result.trade_count == 0:
        return False
    if _is_eth(result):
        days = _result_days(result)
        min_trades = max(2, min(20, _ceil(days * 0.20)))
        min_active_days = max(1, min(10, _ceil(days * 0.10)))
        return result.trade_count >= min_trades and _active_days(result.trades) >= min_active_days
    return result.trades_per_day >= 1.0


def _candidate_rejection(result):
    if not _activity_ok(result):
        return "rejected_by_activity"
    if result.trades_per_day > 10.0:
        return "rejected_by_overactivity"
    if result.total_net_pnl <= 0:
        if result.total_gross_pnl > 0 and result.total_fees >= result.total_gross_pnl:
            return "rejected_by_fees"
        return "rejected_by_training_net"
    ratio = _r._fee_to_gross_ratio(result)
    if ratio is not None and ratio > _r.MAX_FEE_TO_GROSS_RATIO:
        return "rejected_by_fees"
    profit_factor = _r._profit_factor(result.trades)
    if profit_factor is not None and profit_factor < _r.MIN_PROFIT_FACTOR:
        return "rejected_by_profit_factor"
    if result.max_drawdown > _r.MAX_DRAWDOWN_PCT:
        return "rejected_by_drawdown"
    return None


def _score(result):
    target_distance = abs(_r.TARGET_QUOTE_PER_DAY - result.quote_per_day)
    profit_factor = _r._profit_factor(result.trades) or 0.0
    score = (
        result.quote_per_day
        + min(result.trades_per_day, 6.0) * 0.05
        + min(profit_factor, 2.0) * 0.03
        - result.max_drawdown * 0.01
        - target_distance * 0.03
    )
    if _is_eth(result) and result.trades_per_day < 1.0:
        score -= 0.20 + (1.0 - result.trades_per_day) * 0.10
    return score


def _net_pnl_for_long_return(
    stake_quote_amount,
    gross_return,
    fee_bps=None,
):
    fee_rate = (fee_bps if fee_bps is not None else _r.FEE_BPS) / 10_000
    exit_ratio = 1.0 + gross_return
    gross_pnl = stake_quote_amount * gross_return
    fees = stake_quote_amount * fee_rate * (1.0 + exit_ratio)
    return gross_pnl - fees


def _calendar_day_groups(candles):
    groups = []
    current_day = None
    current = []
    for candle in candles:
        day = candle.open_time[:10]
        if current_day is None:
            current_day = day
        if day != current_day:
            groups.append((current_day, current))
            current_day = day
            current = []
        current.append(candle)
    if current_day is not None and current:
        groups.append((current_day, current))
    return groups


def _perfect_single_long_day_pnl(day_candles, stake_quote_amount):
    """Diagnostic-only same-day long oracle; not a tradeable strategy."""
    if len(day_candles) < 2:
        return 0.0
    best_future_high = day_candles[-1].high
    best_net = 0.0
    for candle in reversed(day_candles[:-1]):
        if best_future_high > candle.close:
            gross_return = best_future_high / candle.close - 1.0
            best_net = max(
                best_net,
                _net_pnl_for_long_return(stake_quote_amount, gross_return),
            )
        best_future_high = max(best_future_high, candle.high)
    return max(0.0, best_net)


def _buy_hold_diagnostic(candles, stake_quote_amount):
    if len(candles) < 2:
        return {
            "net_pnl": 0.0,
            "quote_per_day": 0.0,
            "return_pct": 0.0,
        }
    gross_return = candles[-1].close / candles[0].close - 1.0
    net_pnl = _net_pnl_for_long_return(stake_quote_amount, gross_return)
    days = max(1.0, len(candles) / 1440)
    return {
        "net_pnl": net_pnl,
        "quote_per_day": net_pnl / days,
        "return_pct": net_pnl / stake_quote_amount * 100,
    }


def _long_only_oracle_summary(candles, stake_quote_amount, target_quote_per_day=None):
    """Build a diagnostic upper-bound summary without affecting routing."""
    target = (
        _r.TARGET_QUOTE_PER_DAY
        if target_quote_per_day is None
        else target_quote_per_day
    )
    day_rows = []
    for day, day_candles in _calendar_day_groups(candles):
        net_pnl = _perfect_single_long_day_pnl(day_candles, stake_quote_amount)
        day_rows.append(
            {
                "day": day,
                "net_pnl": net_pnl,
                "target_reached": net_pnl >= target,
            }
        )
    total_net = sum(row["net_pnl"] for row in day_rows)
    days = max(1.0, len(candles) / 1440)
    average = total_net / days
    target_day_count = sum(1 for row in day_rows if row["target_reached"])
    positive_day_count = sum(1 for row in day_rows if row["net_pnl"] > 0)
    top_days = sorted(day_rows, key=lambda row: row["net_pnl"], reverse=True)[:10]
    required_capture = target / average if average > 0 else None
    return {
        "oracle_type": "diagnostic_perfect_single_long_per_day_same_day_high",
        "tradeable": False,
        "uses_future_high_inside_day": True,
        "lookahead_safe_for_strategy": False,
        "day_count": len(day_rows),
        "positive_day_count": positive_day_count,
        "target_day_count": target_day_count,
        "target_day_rate": target_day_count / len(day_rows) if day_rows else 0.0,
        "total_net_pnl": total_net,
        "quote_per_day": average,
        "target_ratio": average / target if target else None,
        "required_capture_of_oracle_for_target": required_capture,
        "best_day_net_pnl": max((row["net_pnl"] for row in day_rows), default=0.0),
        "median_positive_day_net_pnl": _median(
            [row["net_pnl"] for row in day_rows if row["net_pnl"] > 0]
        ),
        "top_days": top_days,
        "buy_hold_diagnostic": _buy_hold_diagnostic(candles, stake_quote_amount),
    }


def _median(values):
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _build_target_feasibility_audit(
    split,
    stake_quote_amount,
    selected_result,
    best_training_quote_per_day,
    candidate_count,
    training_trade_allowed_count,
    validation_trade_allowed_count,
    selected_pool_size,
):
    target = _r.TARGET_QUOTE_PER_DAY
    training_oracle = _long_only_oracle_summary(
        split.training_candles,
        stake_quote_amount,
        target,
    )
    blindtest_oracle = _long_only_oracle_summary(
        split.blindtest_candles,
        stake_quote_amount,
        target,
    )
    best_training_ratio = (
        best_training_quote_per_day / target if target else None
    )
    blindtest_ratio = selected_result.quote_per_day / target if target else None
    oracle_capture_by_blindtest = (
        selected_result.quote_per_day / blindtest_oracle["quote_per_day"]
        if blindtest_oracle["quote_per_day"] > 0
        else None
    )
    oracle_capture_by_best_training = (
        best_training_quote_per_day / training_oracle["quote_per_day"]
        if training_oracle["quote_per_day"] > 0
        else None
    )
    if selected_result.quote_per_day >= target:
        assessment = "target_reached_by_blindtest"
    elif best_training_quote_per_day < target * 0.25:
        assessment = "target_far_above_current_candidate_space"
    elif blindtest_oracle["required_capture_of_oracle_for_target"] is not None and (
        blindtest_oracle["required_capture_of_oracle_for_target"] > 0.50
    ):
        assessment = "target_requires_unusually_high_oracle_capture"
    else:
        assessment = "target_possible_in_price_action_but_not_current_router"
    return {
        "audit_version": TARGET_FEASIBILITY_AUDIT_VERSION,
        "scope": "diagnostic_only_no_trade_decision",
        "changes_trade_selection": False,
        "changes_gates": False,
        "uses_blindtest_for_learning": False,
        "blindtest_metrics_are_post_run_diagnostics_only": True,
        "symbol": split.symbol,
        "quote_asset": "USDC",
        "stake_quote_amount": stake_quote_amount,
        "target_quote_per_day": target,
        "target_return_per_day_pct_on_stake": target / stake_quote_amount * 100,
        "required_365_day_net_pnl": target * 365,
        "candidate_count": candidate_count,
        "training_trade_allowed_count": training_trade_allowed_count,
        "validation_trade_allowed_count": validation_trade_allowed_count,
        "selected_pool_size": selected_pool_size,
        "best_training_quote_per_day": best_training_quote_per_day,
        "best_training_target_ratio": best_training_ratio,
        "blindtest_quote_per_day": selected_result.quote_per_day,
        "blindtest_target_ratio": blindtest_ratio,
        "oracle_capture_by_best_training_candidate": oracle_capture_by_best_training,
        "oracle_capture_by_blindtest_pool": oracle_capture_by_blindtest,
        "training_single_long_daily_oracle": training_oracle,
        "blindtest_single_long_daily_oracle": blindtest_oracle,
        "assessment": assessment,
        "next_research_step": (
            "use training-only walk-forward regime research before more "
            "full-run router changes"
        ),
    }


def _walkforward_fold_ranges(candles, fold_days=None):
    candles = list(candles)
    if not candles:
        return []
    days = WALKFORWARD_REGIME_FOLD_DAYS if fold_days is None else fold_days
    fold_size = max(1, int(days * 1440))
    folds = []
    for start in range(0, len(candles), fold_size):
        fold_candles = candles[start : start + fold_size]
        if not fold_candles:
            continue
        folds.append(
            {
                "fold_index": len(folds),
                "start": fold_candles[0].open_time,
                "end": fold_candles[-1].open_time,
                "candle_count": len(fold_candles),
                "day_estimate": len(fold_candles) / 1440,
            }
        )
    return folds


def _candidate_filter_source(candidate):
    if candidate.context_filter_lookback is not None:
        return f"context_market:{candidate.context_filter_metric}"
    if candidate.aggtrade_filter_lookback is not None:
        return f"aggtrade:{candidate.aggtrade_filter_metric}"
    if candidate.orderflow_filter_lookback is not None:
        return f"kline_orderflow:{candidate.orderflow_filter_metric}"
    if candidate.htf_filter_timeframe is not None:
        return f"htf:{candidate.htf_filter_timeframe}:{candidate.htf_filter_metric}"
    return "baseline_ethusdc_ohlcv"


def _candidate_regime_research_key(candidate):
    return "|".join(
        (
            candidate.search_pass,
            candidate.family,
            _candidate_filter_source(candidate),
        )
    )


def _candidate_data_sources(candidate):
    sources = ["ETHUSDC_1m_OHLCV"]
    if candidate.htf_filter_timeframe is not None:
        sources.append(f"ETHUSDC_{candidate.htf_filter_timeframe}_closed_htf")
    if candidate.orderflow_filter_lookback is not None:
        sources.append("ETHUSDC_kline_orderflow")
    if candidate.aggtrade_filter_lookback is not None:
        sources.append("ETHUSDC_aggtrade_minutes")
    if candidate.context_filter_lookback is not None:
        sources.append("BTCUSDC_ETHBTC_ETHUSDT_USDCUSDT_context")
    return sources


def _period_overlaps_fold(period, fold):
    return period["start"] <= fold["end"] and period["end"] >= fold["start"]


def _trade_belongs_to_fold(trade, fold):
    return fold["start"] <= trade.entry_time <= fold["end"]


def _summarize_trade_list(trades, day_count):
    total_gross = sum(trade.gross_pnl for trade in trades)
    total_fees = sum(trade.fees_paid for trade in trades)
    total_net = sum(trade.net_pnl for trade in trades)
    return {
        "trade_count": len(trades),
        "winning_trades": sum(1 for trade in trades if trade.net_pnl > 0),
        "losing_trades": sum(1 for trade in trades if trade.net_pnl < 0),
        "total_gross_pnl": total_gross,
        "total_fees": total_fees,
        "total_net_pnl": total_net,
        "quote_per_day": total_net / max(1.0, day_count),
        "profit_factor": _r._profit_factor(trades) if trades else None,
    }


def _walkforward_candidate_periods(
    training_evaluation,
    validation_evaluation,
    selection_train_candles,
    selection_validation_candles,
):
    periods = []
    if training_evaluation is not None and selection_train_candles:
        periods.append(
            {
                "source": "selection_train",
                "start": selection_train_candles[0].open_time,
                "end": selection_train_candles[-1].open_time,
                "day_count": max(1.0, len(selection_train_candles) / 1440),
                "trades": training_evaluation.result.trades,
            }
        )
    if validation_evaluation is not None and selection_validation_candles:
        periods.append(
            {
                "source": "selection_validation",
                "start": selection_validation_candles[0].open_time,
                "end": selection_validation_candles[-1].open_time,
                "day_count": max(1.0, len(selection_validation_candles) / 1440),
                "trades": validation_evaluation.result.trades,
            }
        )
    return periods


def _walkforward_candidate_row(
    candidate,
    training_evaluation,
    validation_evaluation,
    folds,
    selection_train_candles,
    selection_validation_candles,
):
    periods = _walkforward_candidate_periods(
        training_evaluation,
        validation_evaluation,
        selection_train_candles,
        selection_validation_candles,
    )
    period_trades = [
        trade
        for period in periods
        for trade in period["trades"]
    ]
    analyzed_day_count = sum(period["day_count"] for period in periods)
    fold_rows = []
    for fold in folds:
        evaluated = any(_period_overlaps_fold(period, fold) for period in periods)
        if not evaluated:
            continue
        trades = [
            trade
            for trade in period_trades
            if _trade_belongs_to_fold(trade, fold)
        ]
        summary = _summarize_trade_list(trades, fold["day_estimate"])
        fold_rows.append(
            {
                "fold_index": fold["fold_index"],
                "start": fold["start"],
                "end": fold["end"],
                "evaluated": True,
                **summary,
            }
        )
    active_folds = [row for row in fold_rows if row["trade_count"] > 0]
    positive_active_folds = [
        row for row in active_folds if row["total_net_pnl"] > 0
    ]
    negative_material_folds = [
        row
        for row in active_folds
        if row["total_net_pnl"] < 0
        and row["trade_count"] >= TEMPORAL_VALIDATION_MIN_SEGMENT_TRADES
    ]
    total_summary = _summarize_trade_list(
        period_trades,
        analyzed_day_count if analyzed_day_count else 1.0,
    )
    positive_active_fold_rate = (
        len(positive_active_folds) / len(active_folds) if active_folds else 0.0
    )
    required_active_folds = min(3, max(1, len(fold_rows)))
    if total_summary["trade_count"] == 0:
        stability_label = "no_training_window_trades"
    elif total_summary["total_net_pnl"] <= 0:
        stability_label = "training_window_negative"
    elif len(active_folds) < required_active_folds:
        stability_label = "too_few_active_folds"
    elif positive_active_fold_rate >= 0.67 and not negative_material_folds:
        stability_label = "training_stable_positive"
    elif positive_active_fold_rate >= 0.50:
        stability_label = "training_mixed_positive"
    else:
        stability_label = "training_unstable"
    return {
        "candidate_id": candidate.candidate_id,
        "family": candidate.family,
        "search_pass": candidate.search_pass,
        "lookback_candles": candidate.lookback_candles,
        "entry_threshold_pct": candidate.entry_threshold_pct,
        "take_profit_pct": candidate.take_profit_pct,
        "stop_loss_pct": candidate.stop_loss_pct,
        "max_hold_candles": candidate.max_hold_candles,
        "filter_source": _candidate_filter_source(candidate),
        "data_sources": _candidate_data_sources(candidate),
        "regime_key": _candidate_regime_research_key(candidate),
        "training_trade_allowed": (
            training_evaluation.trade_allowed
            if training_evaluation is not None
            else False
        ),
        "training_rejection_reason": (
            training_evaluation.rejection_reason
            if training_evaluation is not None
            else None
        ),
        "validation_result_available": validation_evaluation is not None,
        "validation_trade_allowed": (
            validation_evaluation.trade_allowed
            if validation_evaluation is not None
            else False
        ),
        "validation_rejection_reason": (
            validation_evaluation.rejection_reason
            if validation_evaluation is not None
            else None
        ),
        "analyzed_scope": (
            "selection_train_plus_selection_validation"
            if validation_evaluation is not None
            else "selection_train_only"
        ),
        "folds_evaluated": len(fold_rows),
        "active_fold_count": len(active_folds),
        "positive_active_fold_count": len(positive_active_folds),
        "negative_material_fold_count": len(negative_material_folds),
        "positive_active_fold_rate": positive_active_fold_rate,
        "worst_fold_net_pnl": min(
            (row["total_net_pnl"] for row in active_folds),
            default=0.0,
        ),
        "best_fold_net_pnl": max(
            (row["total_net_pnl"] for row in active_folds),
            default=0.0,
        ),
        "stability_label": stability_label,
        "folds": fold_rows,
        **total_summary,
    }


def _build_regime_summary(candidate_rows):
    regimes = {}
    for row in candidate_rows:
        key = row["regime_key"]
        regime = regimes.setdefault(
            key,
            {
                "regime_key": key,
                "search_pass": row["search_pass"],
                "family": row["family"],
                "filter_source": row["filter_source"],
                "candidate_count": 0,
                "training_trade_allowed_count": 0,
                "validation_trade_allowed_count": 0,
                "stable_candidate_count": 0,
                "trade_count": 0,
                "total_net_pnl": 0.0,
                "total_gross_pnl": 0.0,
                "total_fees": 0.0,
                "best_candidate_quote_per_day": None,
                "best_candidate_id": None,
                "fold_totals": {},
            },
        )
        regime["candidate_count"] += 1
        if row["training_trade_allowed"]:
            regime["training_trade_allowed_count"] += 1
        if row["validation_trade_allowed"]:
            regime["validation_trade_allowed_count"] += 1
        if row["stability_label"] == "training_stable_positive":
            regime["stable_candidate_count"] += 1
        regime["trade_count"] += row["trade_count"]
        regime["total_net_pnl"] += row["total_net_pnl"]
        regime["total_gross_pnl"] += row["total_gross_pnl"]
        regime["total_fees"] += row["total_fees"]
        if (
            regime["best_candidate_quote_per_day"] is None
            or row["quote_per_day"] > regime["best_candidate_quote_per_day"]
        ):
            regime["best_candidate_quote_per_day"] = row["quote_per_day"]
            regime["best_candidate_id"] = row["candidate_id"]
        for fold in row["folds"]:
            fold_total = regime["fold_totals"].setdefault(
                fold["fold_index"],
                {
                    "fold_index": fold["fold_index"],
                    "start": fold["start"],
                    "end": fold["end"],
                    "candidate_count": 0,
                    "active_candidate_count": 0,
                    "trade_count": 0,
                    "total_net_pnl": 0.0,
                },
            )
            fold_total["candidate_count"] += 1
            if fold["trade_count"] > 0:
                fold_total["active_candidate_count"] += 1
            fold_total["trade_count"] += fold["trade_count"]
            fold_total["total_net_pnl"] += fold["total_net_pnl"]
    summaries = []
    for regime in regimes.values():
        fold_totals = sorted(
            regime.pop("fold_totals").values(),
            key=lambda row: row["fold_index"],
        )
        active_fold_totals = [
            row for row in fold_totals if row["active_candidate_count"] > 0
        ]
        positive_fold_totals = [
            row for row in active_fold_totals if row["total_net_pnl"] > 0
        ]
        regime["active_fold_count"] = len(active_fold_totals)
        regime["positive_active_fold_count"] = len(positive_fold_totals)
        regime["positive_active_fold_rate"] = (
            len(positive_fold_totals) / len(active_fold_totals)
            if active_fold_totals
            else 0.0
        )
        regime["stable_candidate_rate"] = (
            regime["stable_candidate_count"] / regime["candidate_count"]
            if regime["candidate_count"]
            else 0.0
        )
        regime["fold_totals"] = fold_totals
        summaries.append(regime)
    return sorted(
        summaries,
        key=lambda row: (
            row["stable_candidate_count"],
            row["positive_active_fold_rate"],
            row["total_net_pnl"],
            row["best_candidate_quote_per_day"] or 0.0,
        ),
        reverse=True,
    )


def _build_walkforward_red_flags(candidate_rows, selected_pool_ids):
    flags = []
    stable_rows = [
        row for row in candidate_rows
        if row["stability_label"] == "training_stable_positive"
    ]
    if not stable_rows:
        flags.append("no_candidate_stable_positive_across_training_folds")
    target_like_rows = [
        row for row in candidate_rows
        if row["quote_per_day"] >= _r.TARGET_QUOTE_PER_DAY
    ]
    if not target_like_rows:
        flags.append("no_training_candidate_near_3_usdc_per_day")
    selected_rows = [
        row for row in candidate_rows if row["candidate_id"] in selected_pool_ids
    ]
    unstable_selected = [
        row for row in selected_rows
        if row["stability_label"] not in {
            "training_stable_positive",
            "training_mixed_positive",
        }
    ]
    if unstable_selected:
        flags.append("selected_pool_contains_training_unstable_candidates")
    if any(
        row["validation_result_available"] and not row["validation_trade_allowed"]
        for row in selected_rows
    ):
        flags.append("selected_pool_has_validation_rejection_mismatch")
    return flags


def _build_walkforward_candidate_rows(
    training_candles,
    selection_train_candles,
    selection_validation_candles,
    evaluations,
    validation_evaluations,
):
    folds = _walkforward_fold_ranges(training_candles)
    training_by_id = {
        evaluation.candidate.candidate_id: evaluation for evaluation in evaluations
    }
    validation_by_id = {
        evaluation.candidate.candidate_id: evaluation
        for evaluation in validation_evaluations
    }
    candidate_ids = sorted(set(training_by_id) | set(validation_by_id))
    candidate_rows = []
    for candidate_id in candidate_ids:
        training_evaluation = training_by_id.get(candidate_id)
        validation_evaluation = validation_by_id.get(candidate_id)
        candidate = (
            training_evaluation.candidate
            if training_evaluation is not None
            else validation_evaluation.candidate
        )
        candidate_rows.append(
            _walkforward_candidate_row(
                candidate,
                training_evaluation,
                validation_evaluation,
                folds,
                selection_train_candles,
                selection_validation_candles,
            )
        )
    return folds, candidate_rows


def _build_walkforward_regime_research(
    training_candles,
    selection_train_candles,
    selection_validation_candles,
    evaluations,
    validation_evaluations,
    selected_pool,
    folds=None,
    candidate_rows=None,
    used_for_pool_selection=False,
):
    """Training-only map for candidate/regime stability.

    V17 wrote this as pure diagnostics. V18 may also use the same rows as a
    training-only pool-selection input.  It still never uses blindtest candles.
    """
    if folds is None or candidate_rows is None:
        folds, candidate_rows = _build_walkforward_candidate_rows(
            training_candles,
            selection_train_candles,
            selection_validation_candles,
            evaluations,
            validation_evaluations,
        )
    selected_pool_ids = {
        evaluation.candidate.candidate_id for evaluation in selected_pool
    }
    stable_rows = [
        row for row in candidate_rows
        if row["stability_label"] == "training_stable_positive"
    ]
    sorted_candidates = sorted(
        candidate_rows,
        key=lambda row: (
            row["stability_label"] == "training_stable_positive",
            row["positive_active_fold_rate"],
            row["quote_per_day"],
            row["total_net_pnl"],
        ),
        reverse=True,
    )
    selected_pool_diagnostics = [
        row for row in sorted_candidates if row["candidate_id"] in selected_pool_ids
    ]
    return {
        "version": WALKFORWARD_REGIME_RESEARCH_VERSION,
        "selection_version": WALKFORWARD_STABILITY_POOL_SELECTION_VERSION,
        "scope": (
            "training_only_pool_selection_input_plus_diagnostics"
            if used_for_pool_selection
            else "training_only_diagnostic_no_trade_decision"
        ),
        "changes_trade_selection": bool(used_for_pool_selection),
        "changes_gates": False,
        "uses_blindtest": False,
        "uses_blindtest_for_learning": False,
        "blindtest_metrics_used": False,
        "used_for_pool_selection": bool(used_for_pool_selection),
        "fold_days": WALKFORWARD_REGIME_FOLD_DAYS,
        "fold_count": len(folds),
        "folds": folds,
        "selection_train_start": (
            selection_train_candles[0].open_time if selection_train_candles else None
        ),
        "selection_train_end": (
            selection_train_candles[-1].open_time if selection_train_candles else None
        ),
        "selection_validation_start": (
            selection_validation_candles[0].open_time
            if selection_validation_candles
            else None
        ),
        "selection_validation_end": (
            selection_validation_candles[-1].open_time
            if selection_validation_candles
            else None
        ),
        "candidate_count": len(candidate_rows),
        "validation_candidate_count": len(
            {evaluation.candidate.candidate_id for evaluation in validation_evaluations}
        ),
        "stable_candidate_count": len(stable_rows),
        "training_stable_positive_candidate_ids": [
            row["candidate_id"] for row in stable_rows[:50]
        ],
        "regime_summary": _build_regime_summary(candidate_rows)[:30],
        "top_candidate_walkforward_rows": sorted_candidates[:40],
        "selected_pool_walkforward_diagnostics": selected_pool_diagnostics,
        "red_flags": _build_walkforward_red_flags(
            candidate_rows,
            selected_pool_ids,
        ),
        "how_to_use_next": (
            "V18 uses this training-only map for pool ordering. The next step is "
            "to inspect selected_pool_walkforward_diagnostics after the full run "
            "and only then decide whether a stricter regime router is justified."
        ),
    }


def _evaluate_training_candidates(candidates, candles, start_capital_reference, filters, progress_callback=None):
    market = _r._MarketMetrics(candles)
    ordered = sorted(
        candidates,
        key=lambda candidate: (
            candidate.lookback_candles,
            candidate.search_pass,
            candidate.family,
            candidate.candidate_id,
        ),
    )
    evaluations = []
    total = len(ordered)
    for done, candidate in enumerate(ordered, start=1):
        result = _r._run_candidate_on_candles(
            candles,
            candidate,
            start_capital_reference,
            filters,
            market,
        )
        rejection = _candidate_rejection(result)
        activity = _r._activity_class(result.trades_per_day)
        distance = abs(_r.TARGET_QUOTE_PER_DAY - result.quote_per_day)
        evaluations.append(
            _r._TrainingEvaluation(
                candidate,
                result,
                activity,
                rejection is None,
                rejection,
                _score(result),
                distance,
            )
        )
        _r._emit_router_progress(progress_callback, done, total)
    return evaluations


def _feature_values_for_candidate(evaluation, derived_features, timeframe):
    winners = []
    losers = []
    for trade in evaluation.result.trades:
        feature = derived_features.snapshots.get(trade.entry_time, {}).get(timeframe)
        if feature is None or not isinstance(feature.get("range_pct"), int | float):
            continue
        value = float(feature["range_pct"])
        if trade.net_pnl > 0:
            winners.append(value)
        elif trade.net_pnl < 0:
            losers.append(value)
    return winners, losers


def _learn_htf_filter_candidates(evaluations, derived_features, htf_analysis):
    """Learn at most one deterministic HTF range filter per ETH filter candidate."""
    candidate_timeframes = list(
        htf_analysis["candidate_timeframes_for_future_review"]
    )
    learned_candidates = []
    learned_rules = []
    for evaluation in evaluations:
        if not _filter_learning_eligible(evaluation):
            continue
        best_rule = None
        for timeframe in candidate_timeframes:
            winners, losers = _feature_values_for_candidate(
                evaluation,
                derived_features,
                timeframe,
            )
            if len(winners) < 20 or len(losers) < 20:
                continue
            winner_average = _average(winners)
            loser_average = _average(losers)
            if (
                winner_average is None
                or loser_average is None
                or winner_average <= loser_average
            ):
                continue
            threshold = (winner_average + loser_average) / 2.0
            winner_pass_rate = sum(value >= threshold for value in winners) / len(winners)
            loser_pass_rate = sum(value >= threshold for value in losers) / len(losers)
            separation = winner_pass_rate - loser_pass_rate
            if winner_pass_rate < 0.35 or separation < 0.05:
                continue
            rule = {
                "base_candidate_id": evaluation.candidate.candidate_id,
                "learning_scope": _filter_learning_scope(evaluation),
                "timeframe": timeframe,
                "metric": "range_pct",
                "operator": ">=",
                "threshold": threshold,
                "training_winner_sample_count": len(winners),
                "training_loser_sample_count": len(losers),
                "training_winner_average": winner_average,
                "training_loser_average": loser_average,
                "training_winner_pass_rate": winner_pass_rate,
                "training_loser_pass_rate": loser_pass_rate,
                "training_pass_rate_separation": separation,
            }
            if best_rule is None or (
                rule["training_pass_rate_separation"],
                rule["training_winner_sample_count"] + rule["training_loser_sample_count"],
            ) > (
                best_rule["training_pass_rate_separation"],
                best_rule["training_winner_sample_count"]
                + best_rule["training_loser_sample_count"],
            ):
                best_rule = rule
        if best_rule is None:
            continue
        candidate = replace(
            evaluation.candidate,
            candidate_id=(
                f"{evaluation.candidate.candidate_id}"
                f"_htf_{best_rule['timeframe']}_range_filter"
            ),
            search_pass=f"{evaluation.candidate.search_pass}_htf_filter",
            htf_filter_timeframe=str(best_rule["timeframe"]),
            htf_filter_metric="range_pct",
            htf_filter_min_value=float(best_rule["threshold"]),
            htf_filter_training_winner_average=float(
                best_rule["training_winner_average"]
            ),
            htf_filter_training_loser_average=float(
                best_rule["training_loser_average"]
            ),
            htf_filter_training_winner_pass_rate=float(
                best_rule["training_winner_pass_rate"]
            ),
            htf_filter_training_loser_pass_rate=float(
                best_rule["training_loser_pass_rate"]
            ),
        )
        learned_candidates.append(candidate)
        learned_rules.append(
            {
                **best_rule,
                "candidate_id": candidate.candidate_id,
                "learned_from": "training_only",
                "frozen_before_blindtest": True,
                "overfitting_risk": "candidate-specific training threshold; requires blindtest confirmation",
            }
        )
    return learned_candidates, learned_rules


def _orderflow_feature_series_cache(
    candles,
    candidates,
    warmup_candles=None,
    include_base_lookbacks=False,
):
    """Build only the per-lookback kline features required by filter candidates."""
    lookbacks = sorted(
        {
            (
                candidate.orderflow_filter_lookback
                if candidate.orderflow_filter_lookback is not None
                else candidate.lookback_candles
            )
            for candidate in candidates
            if candidate.orderflow_filter_lookback is not None
            or include_base_lookbacks
        }
    )
    if not lookbacks:
        return {}
    warmup = list(warmup_candles or [])
    combined = warmup + list(candles)
    offset = len(warmup)
    result = {}
    for lookback in lookbacks:
        series = build_closed_kline_orderflow_feature_series(combined, lookback)
        result[lookback] = KlineOrderflowFeatureSeries(
            lookback_candles=lookback,
            quote_volume_ratio=array("d", series.quote_volume_ratio[offset:]),
            trade_count_ratio=array("d", series.trade_count_ratio[offset:]),
            taker_buy_quote_imbalance=array(
                "d",
                series.taker_buy_quote_imbalance[offset:],
            ),
        )
    return result


def _orderflow_values_for_candidate(
    evaluation,
    open_times,
    feature_series,
    metric,
):
    """Return winner/loser values available at an existing trade's entry."""
    series = feature_series.get(evaluation.candidate.lookback_candles)
    if series is None:
        return [], []
    winners = []
    losers = []
    for trade in evaluation.result.trades:
        index = bisect_left(open_times, trade.entry_time)
        if index >= len(open_times) or open_times[index] != trade.entry_time:
            continue
        value = series.value_at(metric, index)
        if value is None:
            continue
        if trade.net_pnl > 0:
            winners.append(value)
        elif trade.net_pnl < 0:
            losers.append(value)
    return winners, losers


def _learn_orderflow_filter_candidates(evaluations, candles):
    """Learn one frozen order-flow entry filter for each eligible ETH setup.

    This is deliberately limited to existing ETH candidates that are either net
    positive or have a gross edge that may be rescued from fees/noise.  It does
    not create a new entry family, retune exits, or relax any admission gate.  A
    candidate is only added when its own training winners and losers show a
    repeatable directional separation in a completed-minute feature.
    """
    eligible = [
        evaluation
        for evaluation in evaluations
        if _filter_learning_eligible(evaluation)
    ]
    feature_series = _orderflow_feature_series_cache(
        candles,
        [evaluation.candidate for evaluation in eligible],
        include_base_lookbacks=True,
    )
    open_times = [candle.open_time for candle in candles]
    learned_candidates = []
    learned_rules = []
    for evaluation in eligible:
        best_rule = None
        for metric in ORDERFLOW_METRICS:
            winners, losers = _orderflow_values_for_candidate(
                evaluation,
                open_times,
                feature_series,
                metric,
            )
            if len(winners) < 20 or len(losers) < 20:
                continue
            winner_average = _average(winners)
            loser_average = _average(losers)
            if (
                winner_average is None
                or loser_average is None
                or winner_average == loser_average
            ):
                continue
            operator = ">=" if winner_average > loser_average else "<="
            threshold = (winner_average + loser_average) / 2.0
            winner_pass_rate = sum(
                value >= threshold if operator == ">=" else value <= threshold
                for value in winners
            ) / len(winners)
            loser_pass_rate = sum(
                value >= threshold if operator == ">=" else value <= threshold
                for value in losers
            ) / len(losers)
            separation = winner_pass_rate - loser_pass_rate
            if winner_pass_rate < 0.35 or separation < 0.05:
                continue
            rule = {
                "base_candidate_id": evaluation.candidate.candidate_id,
                "learning_scope": _filter_learning_scope(evaluation),
                "lookback_candles": evaluation.candidate.lookback_candles,
                "metric": metric,
                "operator": operator,
                "threshold": threshold,
                "training_winner_sample_count": len(winners),
                "training_loser_sample_count": len(losers),
                "training_winner_average": winner_average,
                "training_loser_average": loser_average,
                "training_winner_pass_rate": winner_pass_rate,
                "training_loser_pass_rate": loser_pass_rate,
                "training_pass_rate_separation": separation,
            }
            if best_rule is None or (
                rule["training_pass_rate_separation"],
                rule["training_winner_sample_count"]
                + rule["training_loser_sample_count"],
            ) > (
                best_rule["training_pass_rate_separation"],
                best_rule["training_winner_sample_count"]
                + best_rule["training_loser_sample_count"],
            ):
                best_rule = rule
        if best_rule is None:
            continue
        candidate = replace(
            evaluation.candidate,
            candidate_id=(
                f"{evaluation.candidate.candidate_id}"
                f"_orderflow_{best_rule['metric']}_filter"
            ),
            search_pass=f"{evaluation.candidate.search_pass}_orderflow_filter",
            orderflow_filter_lookback=int(best_rule["lookback_candles"]),
            orderflow_filter_metric=str(best_rule["metric"]),
            orderflow_filter_operator=str(best_rule["operator"]),
            orderflow_filter_threshold=float(best_rule["threshold"]),
            orderflow_filter_training_winner_average=float(
                best_rule["training_winner_average"]
            ),
            orderflow_filter_training_loser_average=float(
                best_rule["training_loser_average"]
            ),
            orderflow_filter_training_winner_pass_rate=float(
                best_rule["training_winner_pass_rate"]
            ),
            orderflow_filter_training_loser_pass_rate=float(
                best_rule["training_loser_pass_rate"]
            ),
        )
        learned_candidates.append(candidate)
        learned_rules.append(
            {
                **best_rule,
                "candidate_id": candidate.candidate_id,
                "learned_from": "training_only",
                "frozen_before_blindtest": True,
                "overfitting_risk": "candidate-specific training threshold; requires blindtest confirmation",
            }
        )
    return learned_candidates, learned_rules


def _evaluate_orderflow_filter_candidates(
    candidates,
    candles,
    start_capital_reference,
    filters,
    progress_callback=None,
):
    if not candidates:
        return []
    market = _r._MarketMetrics(candles)
    feature_series = _orderflow_feature_series_cache(candles, candidates)
    evaluations = []
    total = len(candidates)
    for done, candidate in enumerate(candidates, start=1):
        result = _r._run_candidate_on_candles(
            candles,
            candidate,
            start_capital_reference,
            filters,
            market,
            orderflow_feature_series=feature_series,
        )
        rejection = _candidate_rejection(result)
        evaluations.append(
            _r._TrainingEvaluation(
                candidate,
                result,
                _r._activity_class(result.trades_per_day),
                rejection is None,
                rejection,
                _score(result),
                abs(_r.TARGET_QUOTE_PER_DAY - result.quote_per_day),
            )
        )
        _r._emit_router_progress(progress_callback, done, total)
    return evaluations


def _aggtrade_feature_series_cache(
    candles,
    candidates,
    warmup_candles=None,
    include_base_lookbacks=False,
):
    lookbacks = sorted(
        {
            (
                candidate.aggtrade_filter_lookback
                if candidate.aggtrade_filter_lookback is not None
                else candidate.lookback_candles
            )
            for candidate in candidates
            if candidate.aggtrade_filter_lookback is not None
            or include_base_lookbacks
        }
    )
    if not lookbacks:
        return {}
    warmup = list(warmup_candles or [])
    combined = warmup + list(candles)
    offset = len(warmup)
    result = {}
    for lookback in lookbacks:
        series = build_closed_agg_trade_feature_series(combined, lookback)
        result[lookback] = AggTradeFeatureSeries(
            lookback_candles=lookback,
            agg_trade_count_ratio=array("d", series.agg_trade_count_ratio[offset:]),
            raw_trade_count_ratio=array("d", series.raw_trade_count_ratio[offset:]),
            taker_buy_quote_imbalance=array(
                "d",
                series.taker_buy_quote_imbalance[offset:],
            ),
            vwap_close_deviation=array("d", series.vwap_close_deviation[offset:]),
            max_agg_trade_quote_share=array(
                "d",
                series.max_agg_trade_quote_share[offset:],
            ),
        )
    return result


def _aggtrade_values_for_candidate(evaluation, open_times, feature_series, metric):
    series = feature_series.get(evaluation.candidate.lookback_candles)
    if series is None:
        return [], []
    winners = []
    losers = []
    for trade in evaluation.result.trades:
        index = bisect_left(open_times, trade.entry_time)
        if index >= len(open_times) or open_times[index] != trade.entry_time:
            continue
        value = series.value_at(metric, index)
        if value is None:
            continue
        if trade.net_pnl > 0:
            winners.append(value)
        elif trade.net_pnl < 0:
            losers.append(value)
    return winners, losers


def _learn_aggtrade_filter_candidates(evaluations, candles):
    """Add one frozen aggTrade filter for each eligible ETH training setup."""
    eligible = [
        evaluation
        for evaluation in evaluations
        if _filter_learning_eligible(evaluation)
    ]
    feature_series = _aggtrade_feature_series_cache(
        candles,
        [evaluation.candidate for evaluation in eligible],
        include_base_lookbacks=True,
    )
    open_times = [candle.open_time for candle in candles]
    learned_candidates = []
    learned_rules = []
    for evaluation in eligible:
        best_rule = None
        for metric in AGG_TRADE_METRICS:
            winners, losers = _aggtrade_values_for_candidate(
                evaluation,
                open_times,
                feature_series,
                metric,
            )
            if len(winners) < 20 or len(losers) < 20:
                continue
            winner_average = _average(winners)
            loser_average = _average(losers)
            if (
                winner_average is None
                or loser_average is None
                or winner_average == loser_average
            ):
                continue
            operator = ">=" if winner_average > loser_average else "<="
            threshold = (winner_average + loser_average) / 2.0
            winner_pass_rate = sum(
                value >= threshold if operator == ">=" else value <= threshold
                for value in winners
            ) / len(winners)
            loser_pass_rate = sum(
                value >= threshold if operator == ">=" else value <= threshold
                for value in losers
            ) / len(losers)
            separation = winner_pass_rate - loser_pass_rate
            if winner_pass_rate < 0.35 or separation < 0.05:
                continue
            rule = {
                "base_candidate_id": evaluation.candidate.candidate_id,
                "learning_scope": _filter_learning_scope(evaluation),
                "lookback_candles": evaluation.candidate.lookback_candles,
                "metric": metric,
                "operator": operator,
                "threshold": threshold,
                "training_winner_sample_count": len(winners),
                "training_loser_sample_count": len(losers),
                "training_winner_average": winner_average,
                "training_loser_average": loser_average,
                "training_winner_pass_rate": winner_pass_rate,
                "training_loser_pass_rate": loser_pass_rate,
                "training_pass_rate_separation": separation,
            }
            if best_rule is None or (
                rule["training_pass_rate_separation"],
                rule["training_winner_sample_count"]
                + rule["training_loser_sample_count"],
            ) > (
                best_rule["training_pass_rate_separation"],
                best_rule["training_winner_sample_count"]
                + best_rule["training_loser_sample_count"],
            ):
                best_rule = rule
        if best_rule is None:
            continue
        candidate = replace(
            evaluation.candidate,
            candidate_id=(
                f"{evaluation.candidate.candidate_id}"
                f"_aggtrade_{best_rule['metric']}_filter"
            ),
            search_pass=f"{evaluation.candidate.search_pass}_aggtrade_filter",
            aggtrade_filter_lookback=int(best_rule["lookback_candles"]),
            aggtrade_filter_metric=str(best_rule["metric"]),
            aggtrade_filter_operator=str(best_rule["operator"]),
            aggtrade_filter_threshold=float(best_rule["threshold"]),
            aggtrade_filter_training_winner_average=float(
                best_rule["training_winner_average"]
            ),
            aggtrade_filter_training_loser_average=float(
                best_rule["training_loser_average"]
            ),
            aggtrade_filter_training_winner_pass_rate=float(
                best_rule["training_winner_pass_rate"]
            ),
            aggtrade_filter_training_loser_pass_rate=float(
                best_rule["training_loser_pass_rate"]
            ),
        )
        learned_candidates.append(candidate)
        learned_rules.append(
            {
                **best_rule,
                "candidate_id": candidate.candidate_id,
                "learned_from": "training_only",
                "frozen_before_blindtest": True,
                "overfitting_risk": "candidate-specific training threshold; requires blindtest confirmation",
            }
        )
    return learned_candidates, learned_rules


def _evaluate_aggtrade_filter_candidates(
    candidates,
    candles,
    start_capital_reference,
    filters,
    progress_callback=None,
):
    if not candidates:
        return []
    market = _r._MarketMetrics(candles)
    feature_series = _aggtrade_feature_series_cache(candles, candidates)
    evaluations = []
    for done, candidate in enumerate(candidates, start=1):
        result = _r._run_candidate_on_candles(
            candles,
            candidate,
            start_capital_reference,
            filters,
            market,
            aggtrade_feature_series=feature_series,
        )
        rejection = _candidate_rejection(result)
        evaluations.append(
            _r._TrainingEvaluation(
                candidate,
                result,
                _r._activity_class(result.trades_per_day),
                rejection is None,
                rejection,
                _score(result),
                abs(_r.TARGET_QUOTE_PER_DAY - result.quote_per_day),
            )
        )
        _r._emit_router_progress(progress_callback, done, len(candidates))
    return evaluations


def _context_market_feature_series_cache(
    candles,
    candidates,
    warmup_candles=None,
    feature_store: ContextMarketFeatureStore | None = None,
    include_base_lookbacks=False,
):
    """Build only the frozen cross-market lookbacks required by candidates."""
    lookbacks = sorted(
        {
            (
                candidate.context_filter_lookback
                if candidate.context_filter_lookback is not None
                else candidate.lookback_candles
            )
            for candidate in candidates
            if candidate.context_filter_lookback is not None
            or include_base_lookbacks
        }
    )
    if not lookbacks:
        return {}
    warmup = list(warmup_candles or [])
    combined = warmup + list(candles)
    store = feature_store or build_closed_context_market_feature_store(combined)
    offset = len(warmup)
    result = {}
    for lookback in lookbacks:
        series = store.series_for_lookback(lookback)
        result[lookback] = ContextMarketFeatureSeries(
            lookback_candles=lookback,
            btcusdc_return=array("d", series.btcusdc_return[offset:]),
            ethbtc_return=array("d", series.ethbtc_return[offset:]),
            ethusdt_ethusdc_basis=array(
                "d",
                series.ethusdt_ethusdc_basis[offset:],
            ),
            usdcusdt_deviation=array("d", series.usdcusdt_deviation[offset:]),
        )
    return result


def _context_market_values_for_candidate(
    evaluation,
    open_times,
    feature_series,
    metric,
):
    series = feature_series.get(evaluation.candidate.lookback_candles)
    if series is None:
        return [], []
    winners = []
    losers = []
    for trade in evaluation.result.trades:
        index = bisect_left(open_times, trade.entry_time)
        if index >= len(open_times) or open_times[index] != trade.entry_time:
            continue
        value = series.value_at(metric, index)
        if value is None:
            continue
        if trade.net_pnl > 0:
            winners.append(value)
        elif trade.net_pnl < 0:
            losers.append(value)
    return winners, losers


def _learn_context_market_filter_candidates(evaluations, candles, feature_store):
    """Learn one frozen context-market entry filter per eligible ETH setup."""
    eligible = [
        evaluation
        for evaluation in evaluations
        if _filter_learning_eligible(evaluation)
    ]
    feature_series = _context_market_feature_series_cache(
        candles,
        [evaluation.candidate for evaluation in eligible],
        feature_store=feature_store,
        include_base_lookbacks=True,
    )
    open_times = [candle.open_time for candle in candles]
    learned_candidates = []
    learned_rules = []
    for evaluation in eligible:
        best_rule = None
        for metric in CONTEXT_MARKET_METRICS:
            winners, losers = _context_market_values_for_candidate(
                evaluation,
                open_times,
                feature_series,
                metric,
            )
            if len(winners) < 20 or len(losers) < 20:
                continue
            winner_average = _average(winners)
            loser_average = _average(losers)
            if (
                winner_average is None
                or loser_average is None
                or winner_average == loser_average
            ):
                continue
            operator = ">=" if winner_average > loser_average else "<="
            threshold = (winner_average + loser_average) / 2.0
            winner_pass_rate = sum(
                value >= threshold if operator == ">=" else value <= threshold
                for value in winners
            ) / len(winners)
            loser_pass_rate = sum(
                value >= threshold if operator == ">=" else value <= threshold
                for value in losers
            ) / len(losers)
            separation = winner_pass_rate - loser_pass_rate
            if winner_pass_rate < 0.35 or separation < 0.05:
                continue
            rule = {
                "base_candidate_id": evaluation.candidate.candidate_id,
                "learning_scope": _filter_learning_scope(evaluation),
                "lookback_candles": evaluation.candidate.lookback_candles,
                "metric": metric,
                "operator": operator,
                "threshold": threshold,
                "training_winner_sample_count": len(winners),
                "training_loser_sample_count": len(losers),
                "training_winner_average": winner_average,
                "training_loser_average": loser_average,
                "training_winner_pass_rate": winner_pass_rate,
                "training_loser_pass_rate": loser_pass_rate,
                "training_pass_rate_separation": separation,
            }
            if best_rule is None or (
                rule["training_pass_rate_separation"],
                rule["training_winner_sample_count"]
                + rule["training_loser_sample_count"],
            ) > (
                best_rule["training_pass_rate_separation"],
                best_rule["training_winner_sample_count"]
                + best_rule["training_loser_sample_count"],
            ):
                best_rule = rule
        if best_rule is None:
            continue
        candidate = replace(
            evaluation.candidate,
            candidate_id=(
                f"{evaluation.candidate.candidate_id}"
                f"_context_{best_rule['metric']}_filter"
            ),
            search_pass=f"{evaluation.candidate.search_pass}_context_market_filter",
            context_filter_lookback=int(best_rule["lookback_candles"]),
            context_filter_metric=str(best_rule["metric"]),
            context_filter_operator=str(best_rule["operator"]),
            context_filter_threshold=float(best_rule["threshold"]),
            context_filter_training_winner_average=float(
                best_rule["training_winner_average"]
            ),
            context_filter_training_loser_average=float(
                best_rule["training_loser_average"]
            ),
            context_filter_training_winner_pass_rate=float(
                best_rule["training_winner_pass_rate"]
            ),
            context_filter_training_loser_pass_rate=float(
                best_rule["training_loser_pass_rate"]
            ),
        )
        learned_candidates.append(candidate)
        learned_rules.append(
            {
                **best_rule,
                "candidate_id": candidate.candidate_id,
                "learned_from": "training_only",
                "frozen_before_blindtest": True,
                "overfitting_risk": "candidate-specific training threshold; requires blindtest confirmation",
            }
        )
    return learned_candidates, learned_rules


def _evaluate_context_market_filter_candidates(
    candidates,
    candles,
    start_capital_reference,
    filters,
    feature_store,
    progress_callback=None,
):
    if not candidates:
        return []
    market = _r._MarketMetrics(candles)
    feature_series = _context_market_feature_series_cache(
        candles,
        candidates,
        feature_store=feature_store,
    )
    evaluations = []
    for done, candidate in enumerate(candidates, start=1):
        result = _r._run_candidate_on_candles(
            candles,
            candidate,
            start_capital_reference,
            filters,
            market,
            context_feature_series=feature_series,
        )
        rejection = _candidate_rejection(result)
        evaluations.append(
            _r._TrainingEvaluation(
                candidate,
                result,
                _r._activity_class(result.trades_per_day),
                rejection is None,
                rejection,
                _score(result),
                abs(_r.TARGET_QUOTE_PER_DAY - result.quote_per_day),
            )
        )
        _r._emit_router_progress(progress_callback, done, len(candidates))
    return evaluations


def _feature_series_cache(candles, candidates, warmup_candles=None):
    timeframes = sorted(
        {
            candidate.htf_filter_timeframe
            for candidate in candidates
            if candidate.htf_filter_timeframe is not None
        }
    )
    if not timeframes:
        return {}
    warmup = list(warmup_candles or [])
    combined = warmup + list(candles)
    offset = len(warmup)
    result = {}
    for timeframe in timeframes:
        series = build_closed_timeframe_feature_series(combined, timeframe)
        result[timeframe] = DerivedTimeframeFeatureSeries(
            timeframe=timeframe,
            close_return=series.close_return[offset:],
            range_pct=series.range_pct[offset:],
            volume=series.volume[offset:],
        )
    return result


def _evaluate_htf_filter_candidates(
    candidates,
    candles,
    start_capital_reference,
    filters,
    progress_callback=None,
):
    if not candidates:
        return []
    market = _r._MarketMetrics(candles)
    feature_series = _feature_series_cache(candles, candidates)
    evaluations = []
    total = len(candidates)
    for done, candidate in enumerate(candidates, start=1):
        result = _r._run_candidate_on_candles(
            candles,
            candidate,
            start_capital_reference,
            filters,
            market,
            feature_series,
        )
        rejection = _candidate_rejection(result)
        evaluations.append(
            _r._TrainingEvaluation(
                candidate,
                result,
                _r._activity_class(result.trades_per_day),
                rejection is None,
                rejection,
                _score(result),
                abs(_r.TARGET_QUOTE_PER_DAY - result.quote_per_day),
            )
        )
        _r._emit_router_progress(progress_callback, done, total)
    return evaluations


def _select_candidate_pool(evaluations):
    pool, _diagnostics = _select_candidate_pool_with_diagnostics(evaluations)
    return pool


def _base_candidate_key(candidate):
    candidate_id = candidate.candidate_id
    for marker in (
        "_htf_",
        "_orderflow_",
        "_aggtrade_",
        "_context_",
    ):
        if marker in candidate_id:
            candidate_id = candidate_id.split(marker, 1)[0]
            break
    return (candidate.family, candidate_id)


def _select_candidate_pool_with_diagnostics(evaluations):
    allowed = [evaluation for evaluation in evaluations if evaluation.trade_allowed]
    if not allowed:
        return [], {
            "pool_selection_version": WALKFORWARD_STABILITY_POOL_SELECTION_VERSION,
            "max_count": 0,
            "family_cap": 0,
            "allowed_input_count": 0,
            "selected_count": 0,
            "pool_rejected_by_family_cap": 0,
            "pool_rejected_by_base_candidate_duplication": 0,
        }
    max_count = max(1, min(8, _ceil(_run_days(evaluations) / 28.0)))
    ordered = sorted(
        allowed,
        key=lambda evaluation: (
            evaluation.balanced_score,
            evaluation.result.quote_per_day,
            evaluation.result.trades_per_day,
        ),
        reverse=True,
    )
    family_cap = 2
    pool = []
    family_counts = {}
    base_keys = set()
    rejected_by_family_cap = 0
    rejected_by_base_candidate_duplication = 0
    for evaluation in ordered:
        family = evaluation.candidate.family
        if family_counts.get(family, 0) >= family_cap:
            rejected_by_family_cap += 1
            continue
        base_key = _base_candidate_key(evaluation.candidate)
        if base_key in base_keys:
            rejected_by_base_candidate_duplication += 1
            continue
        pool.append(evaluation)
        family_counts[family] = family_counts.get(family, 0) + 1
        base_keys.add(base_key)
        if len(pool) >= max_count:
            break
    return pool, {
        "pool_selection_version": WALKFORWARD_STABILITY_POOL_SELECTION_VERSION,
        "max_count": max_count,
        "family_cap": family_cap,
        "allowed_input_count": len(allowed),
        "selected_count": len(pool),
        "pool_rejected_by_family_cap": rejected_by_family_cap,
        "pool_rejected_by_base_candidate_duplication": (
            rejected_by_base_candidate_duplication
        ),
    }


def _split_selection_train_validation(training_candles):
    """Split the official training window into learn and validation windows."""
    candles = list(training_candles)
    if len(candles) < 4:
        return candles, []
    validation_count = min(len(candles) // 4, 180 * 1440)
    validation_count = max(1, validation_count)
    train_count = len(candles) - validation_count
    if train_count <= 0:
        return candles, []
    return candles[:train_count], candles[train_count:]


def _compact_evaluation_metrics(evaluation):
    result = evaluation.result
    return {
        "trade_allowed": evaluation.trade_allowed,
        "rejection_reason": evaluation.rejection_reason,
        "quote_per_day": result.quote_per_day,
        "total_net_pnl": result.total_net_pnl,
        "total_gross_pnl": result.total_gross_pnl,
        "fees": result.total_fees,
        "trade_count": result.trade_count,
        "trades_per_day": result.trades_per_day,
        "winning_trades": result.winning_trades,
        "losing_trades": result.losing_trades,
        "active_days": _active_days(result.trades),
        "profit_factor": _r._profit_factor(result.trades),
        "fee_to_gross_ratio": _r._fee_to_gross_ratio(result),
        "max_drawdown": result.max_drawdown,
        "balanced_score": evaluation.balanced_score,
    }


def _evaluate_candidates_with_feature_caches(
    candidates,
    candles,
    start_capital_reference,
    filters,
    htf_warmup_candles=None,
    orderflow_warmup_candles=None,
    aggtrade_warmup_candles=None,
    context_warmup_candles=None,
    progress_callback=None,
):
    if not candidates:
        return []
    market = _r._MarketMetrics(candles)
    htf_feature_series = _feature_series_cache(
        candles,
        candidates,
        warmup_candles=htf_warmup_candles,
    )
    orderflow_feature_series = _orderflow_feature_series_cache(
        candles,
        candidates,
        warmup_candles=orderflow_warmup_candles,
    )
    aggtrade_feature_series = _aggtrade_feature_series_cache(
        candles,
        candidates,
        warmup_candles=aggtrade_warmup_candles,
    )
    context_feature_series = _context_market_feature_series_cache(
        candles,
        candidates,
        warmup_candles=context_warmup_candles,
    )
    evaluations = []
    total = len(candidates)
    ordered = sorted(
        candidates,
        key=lambda candidate: (
            candidate.lookback_candles,
            candidate.search_pass,
            candidate.family,
            candidate.candidate_id,
        ),
    )
    for done, candidate in enumerate(ordered, start=1):
        result = _r._run_candidate_on_candles(
            candles,
            candidate,
            start_capital_reference,
            filters,
            market,
            htf_feature_series,
            orderflow_feature_series,
            aggtrade_feature_series,
            context_feature_series,
        )
        rejection = _candidate_rejection(result)
        evaluations.append(
            _r._TrainingEvaluation(
                candidate,
                result,
                _r._activity_class(result.trades_per_day),
                rejection is None,
                rejection,
                _score(result),
                abs(_r.TARGET_QUOTE_PER_DAY - result.quote_per_day),
            )
        )
        _r._emit_router_progress(progress_callback, done, total)
    return evaluations


def _pool_validation_rejection(result):
    days = max(1.0, _result_days(result))
    min_trades = max(2, min(20, _ceil(days * 0.20)))
    min_active_days = max(1, min(10, _ceil(days * 0.10)))
    if result.trade_count < min_trades or _active_days(result.trades) < min_active_days:
        return "rejected_by_activity"
    if result.total_net_pnl <= 0:
        if result.total_gross_pnl > 0 and result.total_fees >= result.total_gross_pnl:
            return "rejected_by_fees"
        return "rejected_by_validation_net"
    ratio = _r._fee_to_gross_ratio(result)
    if ratio is not None and ratio > _r.MAX_FEE_TO_GROSS_RATIO:
        return "rejected_by_fees"
    profit_factor = _r._profit_factor(result.trades)
    if profit_factor is not None and profit_factor < _r.MIN_PROFIT_FACTOR:
        return "rejected_by_profit_factor"
    if result.max_drawdown > _r.MAX_DRAWDOWN_PCT:
        return "rejected_by_drawdown"
    return None


def _temporal_validation_stability_report(
    result,
    candles,
    segment_days=None,
):
    if segment_days is None:
        segment_days = TEMPORAL_VALIDATION_SEGMENT_DAYS
    segment_size = max(1, int(segment_days) * 1440)
    segments = []
    if not candles:
        return {
            "guard_used": True,
            "evaluated": False,
            "skip_reason": "no_validation_candles",
            "segment_days": segment_days,
            "minimum_segments": TEMPORAL_VALIDATION_MIN_SEGMENTS,
            "segment_count": 0,
            "active_segment_count": 0,
            "positive_active_segment_count": 0,
            "negative_material_segment_count": 0,
            "positive_active_segment_rate": None,
            "rejection_reason": None,
            "segments": [],
        }
    for start in range(0, len(candles), segment_size):
        segment_candles = candles[start : start + segment_size]
        if not segment_candles:
            continue
        if len(segment_candles) < 1440:
            continue
        start_time = segment_candles[0].open_time
        end_time = segment_candles[-1].open_time
        segment_trades = [
            trade
            for trade in result.trades
            if start_time <= trade.exit_time <= end_time
        ]
        net_pnl = sum(trade.net_pnl for trade in segment_trades)
        gross_pnl = sum(trade.gross_pnl for trade in segment_trades)
        fees = sum(trade.fees_paid for trade in segment_trades)
        segments.append(
            {
                "start": start_time,
                "end": end_time,
                "days": len(segment_candles) / 1440,
                "trade_count": len(segment_trades),
                "active_days": _active_days(segment_trades),
                "net_pnl": net_pnl,
                "gross_pnl": gross_pnl,
                "fees": fees,
                "positive": net_pnl > 0,
                "negative_material": (
                    net_pnl <= 0
                    and len(segment_trades)
                    >= TEMPORAL_VALIDATION_MIN_SEGMENT_TRADES
                ),
            }
        )
    active_segments = [segment for segment in segments if segment["trade_count"] > 0]
    positive_active_segments = [
        segment for segment in active_segments if segment["net_pnl"] > 0
    ]
    negative_material_segments = [
        segment for segment in segments if segment["negative_material"]
    ]
    positive_rate = (
        len(positive_active_segments) / len(active_segments)
        if active_segments
        else None
    )
    evaluated = len(segments) >= TEMPORAL_VALIDATION_MIN_SEGMENTS
    rejection = None
    if evaluated and len(active_segments) < TEMPORAL_VALIDATION_MIN_ACTIVE_SEGMENTS:
        rejection = "rejected_by_temporal_validation_activity"
    elif evaluated and negative_material_segments:
        rejection = "rejected_by_temporal_validation_stability"
    elif (
        evaluated
        and positive_rate is not None
        and positive_rate < TEMPORAL_VALIDATION_MIN_POSITIVE_ACTIVE_SEGMENT_RATE
    ):
        rejection = "rejected_by_temporal_validation_stability"
    return {
        "guard_used": True,
        "evaluated": evaluated,
        "skip_reason": None if evaluated else "insufficient_validation_segments",
        "segment_days": segment_days,
        "minimum_segments": TEMPORAL_VALIDATION_MIN_SEGMENTS,
        "minimum_active_segments": TEMPORAL_VALIDATION_MIN_ACTIVE_SEGMENTS,
        "minimum_segment_trades_for_negative_check": (
            TEMPORAL_VALIDATION_MIN_SEGMENT_TRADES
        ),
        "minimum_positive_active_segment_rate": (
            TEMPORAL_VALIDATION_MIN_POSITIVE_ACTIVE_SEGMENT_RATE
        ),
        "segment_count": len(segments),
        "active_segment_count": len(active_segments),
        "positive_active_segment_count": len(positive_active_segments),
        "negative_material_segment_count": len(negative_material_segments),
        "positive_active_segment_rate": positive_rate,
        "rejection_reason": rejection,
        "segments": segments,
    }


def _temporal_validation_stability_rejection(result, candles, segment_days=None):
    report = _temporal_validation_stability_report(
        result,
        candles,
        segment_days=segment_days,
    )
    return report["rejection_reason"]


def _walkforward_stability_rank(row):
    if row is None:
        return -1
    return {
        "training_stable_positive": 4,
        "training_mixed_positive": 2,
        "too_few_active_folds": 1,
        "training_unstable": 0,
        "training_window_negative": -1,
        "no_training_window_trades": -2,
    }.get(row.get("stability_label"), 0)


def _walkforward_stability_summary(row):
    if row is None:
        return {
            "available": False,
            "stability_label": "missing_walkforward_row",
            "rank": -1,
        }
    return {
        "available": True,
        "candidate_id": row["candidate_id"],
        "stability_label": row["stability_label"],
        "rank": _walkforward_stability_rank(row),
        "filter_source": row["filter_source"],
        "active_fold_count": row["active_fold_count"],
        "positive_active_fold_count": row["positive_active_fold_count"],
        "positive_active_fold_rate": row["positive_active_fold_rate"],
        "negative_material_fold_count": row["negative_material_fold_count"],
        "worst_fold_net_pnl": row["worst_fold_net_pnl"],
        "walkforward_total_net_pnl": row["total_net_pnl"],
        "walkforward_quote_per_day": row["quote_per_day"],
        "validation_trade_allowed": row["validation_trade_allowed"],
    }


def _walkforward_pool_order_key(evaluation, walkforward_stability_by_candidate_id):
    row = (walkforward_stability_by_candidate_id or {}).get(
        evaluation.candidate.candidate_id
    )
    return (
        _walkforward_stability_rank(row),
        -(row.get("negative_material_fold_count", 999) if row else 999),
        row.get("positive_active_fold_rate", 0.0) if row else 0.0,
        row.get("active_fold_count", 0) if row else 0,
        row.get("quote_per_day", 0.0) if row else 0.0,
        evaluation.result.quote_per_day,
        evaluation.balanced_score,
        -evaluation.result.max_drawdown,
        evaluation.result.trades_per_day,
    )


def _walkforward_stability_label_counts(
    evaluations,
    walkforward_stability_by_candidate_id,
):
    counts = {}
    missing = 0
    for evaluation in evaluations:
        row = (walkforward_stability_by_candidate_id or {}).get(
            evaluation.candidate.candidate_id
        )
        if row is None:
            missing += 1
            continue
        label = row["stability_label"]
        counts[label] = counts.get(label, 0) + 1
    if missing:
        counts["missing_walkforward_row"] = missing
    return counts


def _walkforward_stable_candidates_available(
    evaluations,
    walkforward_stability_by_candidate_id,
):
    return any(
        (
            (walkforward_stability_by_candidate_id or {})
            .get(evaluation.candidate.candidate_id, {})
            .get("stability_label")
            == WALKFORWARD_STABILITY_REQUIRED_LABEL
        )
        for evaluation in evaluations
    )


def _walkforward_all_positive_candidate(row):
    if row is None:
        return False
    active_fold_count = row.get("active_fold_count", 0)
    return (
        row.get("stability_label") == WALKFORWARD_STABILITY_REQUIRED_LABEL
        and active_fold_count >= WALKFORWARD_ALL_POSITIVE_MIN_ACTIVE_FOLDS
        and row.get("negative_material_fold_count", 0) == 0
        and row.get("positive_active_fold_count", 0) == active_fold_count
        and row.get("worst_fold_net_pnl", 0.0) > 0
    )


def _walkforward_all_positive_candidates_available(
    evaluations,
    walkforward_stability_by_candidate_id,
):
    return any(
        _walkforward_all_positive_candidate(
            (walkforward_stability_by_candidate_id or {}).get(
                evaluation.candidate.candidate_id
            )
        )
        for evaluation in evaluations
    )


def _walkforward_stability_policy_rejection(
    evaluation,
    walkforward_stability_by_candidate_id,
    stable_candidates_available,
    all_positive_candidates_available=False,
):
    row = (walkforward_stability_by_candidate_id or {}).get(
        evaluation.candidate.candidate_id
    )
    if all_positive_candidates_available and not (
        _walkforward_all_positive_candidate(row)
    ):
        return "rejected_by_walkforward_all_positive_policy"
    if not stable_candidates_available:
        return None
    if row is None:
        return "rejected_by_walkforward_stability_policy"
    if row.get("stability_label") != WALKFORWARD_STABILITY_REQUIRED_LABEL:
        return "rejected_by_walkforward_stability_policy"
    return None


def _optimize_validation_pool(
    validation_evaluations,
    candles,
    start_capital,
    filters,
    htf_warmup_candles=None,
    orderflow_warmup_candles=None,
    aggtrade_warmup_candles=None,
    context_warmup_candles=None,
    walkforward_stability_by_candidate_id=None,
):
    """Build a validation-safe shared-account pool without using blindtest data."""
    allowed = [evaluation for evaluation in validation_evaluations if evaluation.trade_allowed]
    if not allowed:
        empty = _r._empty_simulation_result(
            _r._diagnostic_placeholder_candidate(start_capital),
            start_capital,
        )
        return [], empty, {
            "pool_selection_version": WALKFORWARD_STABILITY_POOL_SELECTION_VERSION,
            "candidate_library_count": 0,
            "max_count": 0,
            "family_cap": 0,
            "selected_count": 0,
            "temporal_validation_guard_used": True,
            "walkforward_stability_pool_selection_used": bool(
                walkforward_stability_by_candidate_id
            ),
            "walkforward_stability_scope": (
                "selection_train_plus_selection_validation_only"
            ),
            "walkforward_stability_blindtest_learning": False,
            "walkforward_stability_policy": WALKFORWARD_STABILITY_POLICY,
            "walkforward_stability_required_label": (
                WALKFORWARD_STABILITY_REQUIRED_LABEL
            ),
            "walkforward_stable_candidates_available": False,
            "walkforward_all_positive_policy": WALKFORWARD_ALL_POSITIVE_POLICY,
            "walkforward_all_positive_min_active_folds": (
                WALKFORWARD_ALL_POSITIVE_MIN_ACTIVE_FOLDS
            ),
            "walkforward_all_positive_candidates_available": False,
            "temporal_validation_segment_days": TEMPORAL_VALIDATION_SEGMENT_DAYS,
            "rejection_counts": {
                "no_validation_allowed_candidates": 1,
                "rejected_by_walkforward_stability_policy": 0,
                "rejected_by_walkforward_all_positive_policy": 0,
            },
            "selected_candidate_ids": [],
            "rejected_walkforward_policy_samples": [],
            "rejected_walkforward_all_positive_policy_samples": [],
            "accepted_steps": [],
        }
    max_count = max(1, min(8, _ceil(_run_days(validation_evaluations) / 28.0)))
    family_cap = 1
    min_incremental_quote_per_day = 0.03
    stable_candidates_available = _walkforward_stable_candidates_available(
        allowed,
        walkforward_stability_by_candidate_id,
    )
    all_positive_candidates_available = (
        _walkforward_all_positive_candidates_available(
            allowed,
            walkforward_stability_by_candidate_id,
        )
    )
    ordered = sorted(
        allowed,
        key=lambda evaluation: _walkforward_pool_order_key(
            evaluation,
            walkforward_stability_by_candidate_id,
        ),
        reverse=True,
    )
    pool = []
    family_counts = {}
    base_keys = set()
    current_result = _r._empty_simulation_result(
        _r._diagnostic_placeholder_candidate(start_capital),
        start_capital,
    )
    rejection_counts = {
        "rejected_by_family_cap": 0,
        "rejected_by_base_candidate_duplication": 0,
        "rejected_by_pool_validation": 0,
        "rejected_by_pool_no_incremental_edge": 0,
        "rejected_by_pool_small_incremental_edge": 0,
        "rejected_by_temporal_validation_activity": 0,
        "rejected_by_temporal_validation_stability": 0,
        "rejected_by_walkforward_stability_policy": 0,
        "rejected_by_walkforward_all_positive_policy": 0,
    }
    accepted_steps = []
    rejected_pool_reasons = {}
    rejected_walkforward_policy_samples = []
    rejected_walkforward_all_positive_policy_samples = []
    for evaluation in ordered:
        if len(pool) >= max_count:
            break
        walkforward_rejection = _walkforward_stability_policy_rejection(
            evaluation,
            walkforward_stability_by_candidate_id,
            stable_candidates_available,
            all_positive_candidates_available=all_positive_candidates_available,
        )
        if walkforward_rejection is not None:
            rejection_counts[walkforward_rejection] += 1
            sample = {
                "candidate_id": evaluation.candidate.candidate_id,
                "family": evaluation.candidate.family,
                "walkforward_stability": _walkforward_stability_summary(
                    (walkforward_stability_by_candidate_id or {}).get(
                        evaluation.candidate.candidate_id
                    )
                ),
            }
            if (
                walkforward_rejection
                == "rejected_by_walkforward_all_positive_policy"
            ):
                if len(rejected_walkforward_all_positive_policy_samples) < 25:
                    rejected_walkforward_all_positive_policy_samples.append(sample)
            elif len(rejected_walkforward_policy_samples) < 25:
                rejected_walkforward_policy_samples.append(sample)
            continue
        family = evaluation.candidate.family
        if family_counts.get(family, 0) >= family_cap:
            rejection_counts["rejected_by_family_cap"] += 1
            continue
        base_key = _base_candidate_key(evaluation.candidate)
        if base_key in base_keys:
            rejection_counts["rejected_by_base_candidate_duplication"] += 1
            continue
        trial_pool = pool + [evaluation]
        trial_result = _aggregate_pool_result(
            candles,
            trial_pool,
            start_capital,
            filters,
            htf_warmup_candles=htf_warmup_candles,
            orderflow_warmup_candles=orderflow_warmup_candles,
            aggtrade_warmup_candles=aggtrade_warmup_candles,
            context_warmup_candles=context_warmup_candles,
        )
        rejection = _pool_validation_rejection(trial_result)
        if rejection is None:
            rejection = _temporal_validation_stability_rejection(
                trial_result,
                candles,
            )
        if rejection is not None:
            rejection_counts["rejected_by_pool_validation"] += 1
            if rejection in rejection_counts:
                rejection_counts[rejection] += 1
            rejected_pool_reasons[rejection] = rejected_pool_reasons.get(rejection, 0) + 1
            continue
        incremental_quote_per_day = (
            trial_result.quote_per_day - current_result.quote_per_day
        )
        if pool and trial_result.total_net_pnl <= current_result.total_net_pnl + 0.000001:
            rejection_counts["rejected_by_pool_no_incremental_edge"] += 1
            continue
        if pool and incremental_quote_per_day < min_incremental_quote_per_day:
            rejection_counts["rejected_by_pool_small_incremental_edge"] += 1
            continue
        pool = trial_pool
        current_result = trial_result
        family_counts[family] = family_counts.get(family, 0) + 1
        base_keys.add(base_key)
        accepted_steps.append(
            {
                "candidate_id": evaluation.candidate.candidate_id,
                "family": family,
                "pool_size_after_add": len(pool),
                "incremental_validation_quote_per_day": incremental_quote_per_day,
                "validation_pool_quote_per_day": current_result.quote_per_day,
                "validation_pool_total_net_pnl": current_result.total_net_pnl,
                "validation_pool_trade_count": current_result.trade_count,
                "validation_pool_max_drawdown": current_result.max_drawdown,
                "validation_pool_profit_factor": _r._profit_factor(
                    current_result.trades
                ),
                "validation_pool_fee_to_gross_ratio": _r._fee_to_gross_ratio(
                    current_result
                ),
                "walkforward_stability": _walkforward_stability_summary(
                    (walkforward_stability_by_candidate_id or {}).get(
                        evaluation.candidate.candidate_id
                    )
                ),
                "validation_pool_temporal_stability": (
                    _temporal_validation_stability_report(current_result, candles)
                ),
            }
        )
    diagnostics = {
        "pool_selection_version": WALKFORWARD_STABILITY_POOL_SELECTION_VERSION,
        "candidate_library_count": len(allowed),
        "max_count": max_count,
        "family_cap": family_cap,
        "min_incremental_quote_per_day": min_incremental_quote_per_day,
        "temporal_validation_guard_used": True,
        "walkforward_stability_pool_selection_used": bool(
            walkforward_stability_by_candidate_id
        ),
        "walkforward_stability_scope": (
            "selection_train_plus_selection_validation_only"
        ),
        "walkforward_stability_blindtest_learning": False,
        "walkforward_stability_policy": WALKFORWARD_STABILITY_POLICY,
        "walkforward_stability_required_label": (
            WALKFORWARD_STABILITY_REQUIRED_LABEL
        ),
        "walkforward_stable_candidates_available": stable_candidates_available,
        "walkforward_all_positive_policy": WALKFORWARD_ALL_POSITIVE_POLICY,
        "walkforward_all_positive_min_active_folds": (
            WALKFORWARD_ALL_POSITIVE_MIN_ACTIVE_FOLDS
        ),
        "walkforward_all_positive_candidates_available": (
            all_positive_candidates_available
        ),
        "walkforward_stability_label_counts": (
            _walkforward_stability_label_counts(
                allowed,
                walkforward_stability_by_candidate_id,
            )
        ),
        "temporal_validation_segment_days": TEMPORAL_VALIDATION_SEGMENT_DAYS,
        "selected_count": len(pool),
        "rejection_counts": rejection_counts,
        "pool_validation_rejection_reasons": rejected_pool_reasons,
        "selected_candidate_ids": [
            evaluation.candidate.candidate_id for evaluation in pool
        ],
        "rejected_walkforward_policy_samples": (
            rejected_walkforward_policy_samples
        ),
        "rejected_walkforward_all_positive_policy_samples": (
            rejected_walkforward_all_positive_policy_samples
        ),
        "selected_walkforward_stability": [
            _walkforward_stability_summary(
                (walkforward_stability_by_candidate_id or {}).get(
                    evaluation.candidate.candidate_id
                )
            )
            for evaluation in pool
        ],
        "accepted_steps": accepted_steps,
    }
    return pool, current_result, diagnostics


def _average(values):
    return sum(values) / len(values) if values else None


def _numeric_values(rows, metric_name):
    return [row[metric_name] for row in rows if isinstance(row.get(metric_name), int | float)]


def _metric_split(rows, metric_name):
    winners = [row for row in rows if row["net_pnl"] > 0]
    losers = [row for row in rows if row["net_pnl"] < 0]
    winner_values = _numeric_values(winners, metric_name)
    loser_values = _numeric_values(losers, metric_name)
    winner_average = _average(winner_values)
    loser_average = _average(loser_values)
    difference = (
        winner_average - loser_average
        if winner_average is not None and loser_average is not None
        else None
    )
    return {
        "winner_sample_count": len(winner_values),
        "loser_sample_count": len(loser_values),
        "winner_average": winner_average,
        "loser_average": loser_average,
        "winner_minus_loser": difference,
    }


def _orderflow_training_edge_analysis(evaluations, candles, learned_rules):
    """Report ETH candidates eligible for training-only order-flow filters."""
    eligible = [
        evaluation
        for evaluation in evaluations
        if _filter_learning_eligible(evaluation)
    ]
    feature_series = _orderflow_feature_series_cache(
        candles,
        [evaluation.candidate for evaluation in eligible],
        include_base_lookbacks=True,
    )
    open_times = [candle.open_time for candle in candles]
    learned_metrics = {rule["metric"] for rule in learned_rules}
    metrics = {}
    for metric in ORDERFLOW_METRICS:
        winner_values = []
        loser_values = []
        for evaluation in eligible:
            winners, losers = _orderflow_values_for_candidate(
                evaluation,
                open_times,
                feature_series,
                metric,
            )
            winner_values.extend(winners)
            loser_values.extend(losers)
        winner_average = _average(winner_values)
        loser_average = _average(loser_values)
        metrics[metric] = {
            "winner_sample_count": len(winner_values),
            "loser_sample_count": len(loser_values),
            "winner_average": winner_average,
            "loser_average": loser_average,
            "winner_minus_loser": (
                winner_average - loser_average
                if winner_average is not None and loser_average is not None
                else None
            ),
            "candidate_for_future_score_or_gate": metric in learned_metrics,
        }
    return {
        "scope": "net_positive_or_gross_edge_eth_training_candidate_entries",
        "usage_mode": (
            "training_only_learned_frozen_entry_filter"
            if learned_rules
            else "diagnostic_only_no_stable_candidate_rule"
        ),
        "changes_trade_gates_or_scores": False,
        "eligible_positive_eth_candidate_count": len(eligible),
        "eligible_filter_learning_candidate_count": len(eligible),
        "eligible_gross_edge_fee_rescue_candidate_count": sum(
            1
            for evaluation in eligible
            if _filter_learning_scope(evaluation)
            == "gross_edge_fee_rescue_eth_candidate"
        ),
        "learned_rule_count": len(learned_rules),
        "metrics": metrics,
    }


def _aggtrade_training_edge_analysis(evaluations, candles, learned_rules):
    eligible = [
        evaluation
        for evaluation in evaluations
        if _filter_learning_eligible(evaluation)
    ]
    feature_series = _aggtrade_feature_series_cache(
        candles,
        [evaluation.candidate for evaluation in eligible],
        include_base_lookbacks=True,
    )
    open_times = [candle.open_time for candle in candles]
    learned_metrics = {rule["metric"] for rule in learned_rules}
    metrics = {}
    for metric in AGG_TRADE_METRICS:
        winners_all = []
        losers_all = []
        for evaluation in eligible:
            winners, losers = _aggtrade_values_for_candidate(
                evaluation,
                open_times,
                feature_series,
                metric,
            )
            winners_all.extend(winners)
            losers_all.extend(losers)
        winner_average = _average(winners_all)
        loser_average = _average(losers_all)
        metrics[metric] = {
            "winner_sample_count": len(winners_all),
            "loser_sample_count": len(losers_all),
            "winner_average": winner_average,
            "loser_average": loser_average,
            "winner_minus_loser": (
                winner_average - loser_average
                if winner_average is not None and loser_average is not None
                else None
            ),
            "candidate_for_future_score_or_gate": metric in learned_metrics,
        }
    return {
        "scope": "net_positive_or_gross_edge_eth_training_candidate_entries",
        "usage_mode": (
            "training_only_learned_frozen_entry_filter"
            if learned_rules
            else "diagnostic_only_no_stable_candidate_rule"
        ),
        "changes_trade_gates_or_scores": False,
        "eligible_positive_eth_candidate_count": len(eligible),
        "eligible_filter_learning_candidate_count": len(eligible),
        "eligible_gross_edge_fee_rescue_candidate_count": sum(
            1
            for evaluation in eligible
            if _filter_learning_scope(evaluation)
            == "gross_edge_fee_rescue_eth_candidate"
        ),
        "learned_rule_count": len(learned_rules),
        "metrics": metrics,
    }


def _context_market_training_edge_analysis(
    evaluations,
    candles,
    feature_store,
    learned_rules,
):
    eligible = [
        evaluation
        for evaluation in evaluations
        if _filter_learning_eligible(evaluation)
    ]
    feature_series = _context_market_feature_series_cache(
        candles,
        [evaluation.candidate for evaluation in eligible],
        feature_store=feature_store,
        include_base_lookbacks=True,
    )
    open_times = [candle.open_time for candle in candles]
    learned_metrics = {rule["metric"] for rule in learned_rules}
    metrics = {}
    for metric in CONTEXT_MARKET_METRICS:
        winners_all = []
        losers_all = []
        for evaluation in eligible:
            winners, losers = _context_market_values_for_candidate(
                evaluation,
                open_times,
                feature_series,
                metric,
            )
            winners_all.extend(winners)
            losers_all.extend(losers)
        winner_average = _average(winners_all)
        loser_average = _average(losers_all)
        metrics[metric] = {
            "source": metric.split("_", 1)[0].upper(),
            "winner_sample_count": len(winners_all),
            "loser_sample_count": len(losers_all),
            "winner_average": winner_average,
            "loser_average": loser_average,
            "winner_minus_loser": (
                winner_average - loser_average
                if winner_average is not None and loser_average is not None
                else None
            ),
            "candidate_for_future_score_or_gate": metric in learned_metrics,
        }
    return {
        "scope": "net_positive_or_gross_edge_eth_training_candidate_entries",
        "usage_mode": (
            "training_only_learned_frozen_entry_filter"
            if learned_rules
            else "diagnostic_only_no_stable_candidate_rule"
        ),
        "changes_trade_gates_or_scores": False,
        "eligible_positive_eth_candidate_count": len(eligible),
        "eligible_filter_learning_candidate_count": len(eligible),
        "eligible_gross_edge_fee_rescue_candidate_count": sum(
            1
            for evaluation in eligible
            if _filter_learning_scope(evaluation)
            == "gross_edge_fee_rescue_eth_candidate"
        ),
        "learned_rule_count": len(learned_rules),
        "source_coverage": {
            symbol: round(coverage, 6)
            for symbol, coverage in feature_store.source_coverage.items()
        },
        "metrics": metrics,
    }


def _trade_rows_with_features(evaluations, derived_features, timeframe):
    rows = []
    for evaluation in evaluations:
        for trade in evaluation.result.trades:
            feature = derived_features.snapshots.get(trade.entry_time, {}).get(timeframe)
            if feature is None:
                continue
            rows.append(
                {
                    "candidate_id": evaluation.candidate.candidate_id,
                    "search_pass": evaluation.candidate.search_pass,
                    "family": evaluation.candidate.family,
                    "net_pnl": trade.net_pnl,
                    "close_return": feature.get("close_return"),
                    "range_pct": feature.get("range_pct"),
                    "volume": feature.get("volume"),
                }
            )
    return rows


def _candidate_for_future_feature(rows, close_return_split, range_pct_split):
    if len(rows) < 20:
        return False
    if close_return_split["winner_minus_loser"] is not None and abs(close_return_split["winner_minus_loser"]) >= 0.001:
        return True
    if range_pct_split["winner_minus_loser"] is not None and abs(range_pct_split["winner_minus_loser"]) >= 0.001:
        return True
    return False


def _htf_training_edge_analysis(evaluations, derived_features):
    """Training-only separation report for HTF diagnostics.

    This intentionally does not change gates, scores, selected candidates or trades. It only
    answers whether winners and losers had visibly different closed higher-timeframe context.
    """
    timeframes = {}
    best_candidates = []
    for timeframe in derived_features.used_timeframes:
        rows = _trade_rows_with_features(evaluations, derived_features, timeframe)
        close_return = _metric_split(rows, "close_return")
        range_pct = _metric_split(rows, "range_pct")
        volume = _metric_split(rows, "volume")
        candidate_flag = _candidate_for_future_feature(rows, close_return, range_pct)
        timeframes[timeframe] = {
            "training_entry_sample_count": len(rows),
            "winning_entries": sum(1 for row in rows if row["net_pnl"] > 0),
            "losing_entries": sum(1 for row in rows if row["net_pnl"] < 0),
            "neutral_entries": sum(1 for row in rows if row["net_pnl"] == 0),
            "close_return": close_return,
            "range_pct": range_pct,
            "volume": volume,
            "candidate_for_future_score_or_gate": candidate_flag,
        }
        if candidate_flag:
            best_candidates.append(timeframe)
    return {
        "scope": "training_only_candidate_entries",
        "usage_mode": "diagnostic_only_no_gate_or_score_change",
        "changes_trade_gates_or_scores": False,
        "used_timeframes": derived_features.used_timeframes,
        "candidate_timeframes_for_future_review": best_candidates,
        "timeframes": timeframes,
    }


def _derived_feature_summary(evaluation, derived_features):
    entry_times = [trade.entry_time for trade in evaluation.result.trades]
    timeframes = {}
    for timeframe in derived_features.used_timeframes:
        rows = [
            derived_features.snapshots[entry_time][timeframe]
            for entry_time in entry_times
            if timeframe in derived_features.snapshots.get(entry_time, {})
        ]
        returns = [row["close_return"] for row in rows if row["close_return"] is not None]
        timeframes[timeframe] = {
            "entry_feature_count": len(rows),
            "entry_feature_coverage": len(rows) / len(entry_times) if entry_times else 0.0,
            "average_closed_candle_return": _average(returns),
            "positive_closed_candle_return_rate": (
                sum(1 for value in returns if value > 0) / len(returns)
                if returns
                else None
            ),
        }
    return {
        "usage_mode": "candidate_entry_diagnostics_only",
        "changes_trade_gates_or_scores": False,
        "timeframes": timeframes,
    }


def _candidate_summary(evaluation, derived_features):
    summary = _r._candidate_summary(evaluation)
    summary["derived_timeframe_features"] = _derived_feature_summary(
        evaluation,
        derived_features,
    )
    candidate = evaluation.candidate
    summary["kline_orderflow_filter"] = {
        "enabled": candidate.orderflow_filter_lookback is not None,
        "lookback_candles": candidate.orderflow_filter_lookback,
        "metric": candidate.orderflow_filter_metric,
        "operator": candidate.orderflow_filter_operator,
        "threshold": candidate.orderflow_filter_threshold,
        "training_winner_average": candidate.orderflow_filter_training_winner_average,
        "training_loser_average": candidate.orderflow_filter_training_loser_average,
        "training_winner_pass_rate": candidate.orderflow_filter_training_winner_pass_rate,
        "training_loser_pass_rate": candidate.orderflow_filter_training_loser_pass_rate,
        "learned_from": (
            "training_only_frozen_before_blindtest"
            if candidate.orderflow_filter_lookback is not None
            else None
        ),
    }
    summary["aggtrade_filter"] = {
        "enabled": candidate.aggtrade_filter_lookback is not None,
        "lookback_candles": candidate.aggtrade_filter_lookback,
        "metric": candidate.aggtrade_filter_metric,
        "operator": candidate.aggtrade_filter_operator,
        "threshold": candidate.aggtrade_filter_threshold,
        "training_winner_average": candidate.aggtrade_filter_training_winner_average,
        "training_loser_average": candidate.aggtrade_filter_training_loser_average,
        "training_winner_pass_rate": candidate.aggtrade_filter_training_winner_pass_rate,
        "training_loser_pass_rate": candidate.aggtrade_filter_training_loser_pass_rate,
        "learned_from": (
            "training_only_frozen_before_blindtest"
            if candidate.aggtrade_filter_lookback is not None
            else None
        ),
    }
    summary["context_market_filter"] = {
        "enabled": candidate.context_filter_lookback is not None,
        "lookback_candles": candidate.context_filter_lookback,
        "metric": candidate.context_filter_metric,
        "operator": candidate.context_filter_operator,
        "threshold": candidate.context_filter_threshold,
        "training_winner_average": candidate.context_filter_training_winner_average,
        "training_loser_average": candidate.context_filter_training_loser_average,
        "training_winner_pass_rate": candidate.context_filter_training_winner_pass_rate,
        "training_loser_pass_rate": candidate.context_filter_training_loser_pass_rate,
        "learned_from": (
            "training_only_frozen_before_blindtest"
            if candidate.context_filter_lookback is not None
            else None
        ),
    }
    return summary


def _aggregate_pool_result(
    candles,
    selected_pool,
    start_capital,
    filters,
    htf_warmup_candles=None,
    orderflow_warmup_candles=None,
    aggtrade_warmup_candles=None,
    context_warmup_candles=None,
):
    if not selected_pool:
        return _r._empty_simulation_result(
            _r._diagnostic_placeholder_candidate(start_capital),
            start_capital,
        )
    market = _r._MarketMetrics(candles)
    feature_series = _feature_series_cache(
        candles,
        [evaluation.candidate for evaluation in selected_pool],
        warmup_candles=htf_warmup_candles,
    )
    orderflow_feature_series = _orderflow_feature_series_cache(
        candles,
        [evaluation.candidate for evaluation in selected_pool],
        warmup_candles=orderflow_warmup_candles,
    )
    aggtrade_feature_series = _aggtrade_feature_series_cache(
        candles,
        [evaluation.candidate for evaluation in selected_pool],
        warmup_candles=aggtrade_warmup_candles,
    )
    context_feature_series = _context_market_feature_series_cache(
        candles,
        [evaluation.candidate for evaluation in selected_pool],
        warmup_candles=context_warmup_candles,
    )
    proposals = []
    pool_feature_filtered_signal_count = 0
    for evaluation in selected_pool:
        result = _r._run_candidate_on_candles(
            candles,
            evaluation.candidate,
            start_capital,
            filters,
            market,
            feature_series,
            orderflow_feature_series,
            aggtrade_feature_series,
            context_feature_series,
        )
        pool_feature_filtered_signal_count += result.feature_filtered_signal_count
        for trade in result.trades:
            proposals.append(
                (
                    trade.entry_time,
                    -evaluation.balanced_score,
                    trade.exit_time,
                    trade.candidate_id,
                    trade,
                )
            )
    proposals.sort()
    chosen = []
    current_busy_until = ""
    skipped = 0
    for entry_time, _neg_score, exit_time, _candidate_id, trade in proposals:
        if entry_time < current_busy_until:
            skipped += 1
            continue
        chosen.append(trade)
        current_busy_until = exit_time
    total_gross = sum(trade.gross_pnl for trade in chosen)
    total_fees = sum(trade.fees_paid for trade in chosen)
    total_net = sum(trade.net_pnl for trade in chosen)
    equity = start_capital
    peak = start_capital
    max_drawdown = 0.0
    for trade in chosen:
        equity += trade.net_pnl
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak * 100)
    days = max(1.0, len(candles) / 1440)
    pool_candidate = _r.ActivityFirstCandidate(
        "multi_candidate_pool",
        "activity_first_router_pool",
        1,
        0.0,
        0.0,
        0.0,
        0,
        0,
        start_capital,
        "multi_candidate_pool",
    )
    return _r.ActivityFirstSimulationResult(
        pool_candidate,
        start_capital,
        start_capital + total_net,
        total_gross,
        total_fees,
        total_net,
        total_net / days,
        len(chosen),
        len(chosen) / days,
        sum(1 for trade in chosen if trade.net_pnl > 0),
        sum(1 for trade in chosen if trade.net_pnl < 0),
        sum(1 for trade in chosen if trade.net_pnl == 0),
        max_drawdown,
        len(proposals),
        skipped,
        sum(evaluation.result.blocked_signal_count for evaluation in selected_pool),
        chosen,
        pool_feature_filtered_signal_count,
    )


def _search_pass_summary(evaluations, derived_features):
    rows = []
    for search_pass in sorted({evaluation.candidate.search_pass for evaluation in evaluations}):
        current = [evaluation for evaluation in evaluations if evaluation.candidate.search_pass == search_pass]
        best = max(current, key=lambda evaluation: evaluation.result.quote_per_day, default=None)
        rows.append(
            {
                "pass_name": search_pass,
                "candidates_generated": len(current),
                "setup_tests_run": len(current),
                "candidates_positive_net": sum(
                    1 for evaluation in current if evaluation.result.total_net_pnl > 0
                ),
                "candidates_active_enough": sum(
                    1 for evaluation in current if _activity_ok(evaluation.result)
                ),
                "candidates_trade_allowed": sum(
                    1 for evaluation in current if evaluation.trade_allowed
                ),
                "best_candidate": _candidate_summary(best, derived_features) if best else None,
            }
        )
    return rows


def _candidate_space_status(evaluations):
    if not evaluations:
        return "activity_search_failed", "no activity-first candidates were generated"
    if any(evaluation.trade_allowed for evaluation in evaluations):
        return "trade_allowed_found", "at least one active after-fee positive setup exists"
    if any(evaluation.result.total_net_pnl > 0 for evaluation in evaluations):
        return (
            "trade_allowed_blocked",
            "positive candidates exist but failed activity/cost/risk gates",
        )
    if any(evaluation.result.total_gross_pnl > 0 for evaluation in evaluations):
        return "edge_after_fees_failed", "gross-positive candidates exist, but fees removed the edge"
    if any(_activity_ok(evaluation.result) for evaluation in evaluations):
        return "target_edge_missing", "active candidates exist, but no gross edge was found"
    if any(evaluation.result.trade_count > 0 for evaluation in evaluations):
        return "target_activity_missing", "signals exist, but activity is below scaled activity gate"
    return "no_active_candidates", "no candidate produced training trades"


def build_activity_first_router_report(run_id, split, stake_quote_amount=100.0, profile="normal", progress_callback=None):
    if split.symbol != _r.CONFIG.symbol:
        raise ValueError(f"symbol must be {_r.CONFIG.symbol}")
    start_capital = float(stake_quote_amount)
    filters = _r.load_exchange_info_filters()
    selection_train_candles, selection_validation_candles = (
        _split_selection_train_validation(split.training_candles)
    )
    candidates = _r._generate_activity_first_candidates(stake_quote_amount, profile)
    baseline_evaluations = _evaluate_training_candidates(
        candidates,
        selection_train_candles,
        start_capital,
        filters,
        progress_callback,
    )
    decision_open_times = {
        trade.entry_time
        for evaluation in baseline_evaluations
        for trade in evaluation.result.trades
    }
    derived_features = build_closed_timeframe_feature_snapshots(
        selection_train_candles,
        decision_open_times,
    )
    derived_timeframes_available = bool(derived_features.available_timeframes)
    derived_timeframes_used_by_router = bool(derived_features.used_timeframes)
    if not derived_timeframes_available:
        missing_timeframe_reason = "no complete higher-timeframe candles in training window"
    elif not derived_timeframes_used_by_router:
        missing_timeframe_reason = "no candidate training entry had a closed higher-timeframe feature"
    else:
        missing_timeframe_reason = None
    baseline_htf_analysis = _htf_training_edge_analysis(
        baseline_evaluations,
        derived_features,
    )
    htf_candidates, learned_htf_rules = _learn_htf_filter_candidates(
        baseline_evaluations,
        derived_features,
        baseline_htf_analysis,
    )
    orderflow_source_available = any(
        candle.quote_volume > 0
        and candle.trade_count > 0
        and candle.taker_buy_quote_volume > 0
        for candle in selection_train_candles
    )
    orderflow_candidates, learned_orderflow_rules = _learn_orderflow_filter_candidates(
        baseline_evaluations,
        selection_train_candles,
    )
    orderflow_training_edge_analysis = _orderflow_training_edge_analysis(
        baseline_evaluations,
        selection_train_candles,
        learned_orderflow_rules,
    )
    aggtrade_status = load_agg_trade_data_status()
    aggtrade_source_available = bool(aggtrade_status and aggtrade_status.success)
    aggtrade_candidates, learned_aggtrade_rules = _learn_aggtrade_filter_candidates(
        baseline_evaluations,
        selection_train_candles,
    )
    aggtrade_training_edge_analysis = _aggtrade_training_edge_analysis(
        baseline_evaluations,
        selection_train_candles,
        learned_aggtrade_rules,
    )
    context_feature_store = build_closed_context_market_feature_store(
        selection_train_candles
    )
    context_sources_available = context_feature_store.available_sources
    context_candidates, learned_context_rules = _learn_context_market_filter_candidates(
        baseline_evaluations,
        selection_train_candles,
        context_feature_store,
    )
    context_market_training_edge_analysis = _context_market_training_edge_analysis(
        baseline_evaluations,
        selection_train_candles,
        context_feature_store,
        learned_context_rules,
    )
    htf_evaluations = _evaluate_htf_filter_candidates(
        htf_candidates,
        selection_train_candles,
        start_capital,
        filters,
        progress_callback,
    )
    orderflow_evaluations = _evaluate_orderflow_filter_candidates(
        orderflow_candidates,
        selection_train_candles,
        start_capital,
        filters,
        progress_callback,
    )
    aggtrade_evaluations = _evaluate_aggtrade_filter_candidates(
        aggtrade_candidates,
        selection_train_candles,
        start_capital,
        filters,
        progress_callback,
    )
    context_evaluations = _evaluate_context_market_filter_candidates(
        context_candidates,
        selection_train_candles,
        start_capital,
        filters,
        context_feature_store,
        progress_callback,
    )
    evaluations = (
        baseline_evaluations
        + htf_evaluations
        + orderflow_evaluations
        + aggtrade_evaluations
        + context_evaluations
    )
    all_candidate_ids = {candidate.candidate_id for candidate in candidates}
    all_candidate_ids.update(candidate.candidate_id for candidate in htf_candidates)
    all_candidate_ids.update(candidate.candidate_id for candidate in orderflow_candidates)
    all_candidate_ids.update(candidate.candidate_id for candidate in aggtrade_candidates)
    all_candidate_ids.update(candidate.candidate_id for candidate in context_candidates)
    decision_open_times.update(
        trade.entry_time
        for evaluation in htf_evaluations
        for trade in evaluation.result.trades
    )
    if htf_evaluations:
        derived_features = build_closed_timeframe_feature_snapshots(
            selection_train_candles,
            decision_open_times,
        )
    allowed = [evaluation for evaluation in evaluations if evaluation.trade_allowed]
    allowed_candidates = [evaluation.candidate for evaluation in allowed]
    validation_evaluations = _evaluate_candidates_with_feature_caches(
        allowed_candidates,
        selection_validation_candles,
        start_capital,
        filters,
        htf_warmup_candles=selection_train_candles[-2880:],
        orderflow_warmup_candles=selection_train_candles[-2880:],
        aggtrade_warmup_candles=selection_train_candles[-2880:],
        context_warmup_candles=selection_train_candles[-2880:],
        progress_callback=progress_callback,
    )
    validation_allowed = [
        evaluation for evaluation in validation_evaluations if evaluation.trade_allowed
    ]
    walkforward_folds, walkforward_candidate_rows = _build_walkforward_candidate_rows(
        split.training_candles,
        selection_train_candles,
        selection_validation_candles,
        evaluations,
        validation_evaluations,
    )
    walkforward_stability_by_candidate_id = {
        row["candidate_id"]: row for row in walkforward_candidate_rows
    }
    optimized_pool, validation_pool_result, pool_selection_diagnostics = (
        _optimize_validation_pool(
            validation_evaluations,
            selection_validation_candles,
            start_capital,
            filters,
            htf_warmup_candles=selection_train_candles[-2880:],
            orderflow_warmup_candles=selection_train_candles[-2880:],
            aggtrade_warmup_candles=selection_train_candles[-2880:],
            context_warmup_candles=selection_train_candles[-2880:],
            walkforward_stability_by_candidate_id=(
                walkforward_stability_by_candidate_id
            ),
        )
    )
    validation_pool_rejection = (
        _pool_validation_rejection(validation_pool_result)
        if optimized_pool
        else "no_validation_pool_candidate"
    )
    validation_pool_passed = validation_pool_rejection is None
    selected_pool = optimized_pool if validation_pool_passed else []
    training_evaluation_by_candidate_id = {
        evaluation.candidate.candidate_id: evaluation for evaluation in evaluations
    }
    validation_evaluation_by_candidate_id = {
        evaluation.candidate.candidate_id: evaluation
        for evaluation in validation_evaluations
    }
    best_activity = max(evaluations, key=lambda evaluation: evaluation.result.trades_per_day, default=None)
    best_edge = max(evaluations, key=lambda evaluation: evaluation.result.quote_per_day, default=None)
    best_balanced = max(evaluations, key=lambda evaluation: evaluation.balanced_score, default=None)
    fee_survivors = [evaluation for evaluation in evaluations if evaluation.result.total_net_pnl > 0]
    best_fee_survivor = max(fee_survivors, key=lambda evaluation: evaluation.result.quote_per_day, default=None)
    best_target = min(evaluations, key=lambda evaluation: evaluation.target_distance, default=None)
    training_status, training_reason = _candidate_space_status(evaluations)
    if selected_pool:
        status = "trade_allowed_found"
        reason = "internal validation plus walkforward stability found a pool candidate"
    elif allowed:
        status = "trade_allowed_blocked"
        reason = (
            "training-positive candidates failed internal selection validation "
            "or validation-pool stress"
        )
    else:
        status, reason = training_status, training_reason
    if selected_pool:
        selected_result = _aggregate_pool_result(
            split.blindtest_candles,
            selected_pool,
            start_capital,
            filters,
            htf_warmup_candles=split.training_candles[-2880:],
            orderflow_warmup_candles=split.training_candles[-2880:],
            aggtrade_warmup_candles=split.training_candles[-2880:],
            context_warmup_candles=split.training_candles[-2880:],
        )
        selected_setups = []
        for validation_evaluation in selected_pool:
            training_evaluation = training_evaluation_by_candidate_id.get(
                validation_evaluation.candidate.candidate_id,
                validation_evaluation,
            )
            setup = _candidate_summary(training_evaluation, derived_features)
            setup["selection_training_metrics"] = _compact_evaluation_metrics(
                training_evaluation
            )
            setup["selection_validation_metrics"] = _compact_evaluation_metrics(
                validation_evaluation
            )
            setup["selected_by"] = (
                "selection_train_plus_internal_validation_plus_walkforward_stability"
            )
            selected_setups.append(setup)
        selection_reason = (
            "selection_train_validation_walkforward_stability_pool_one_shared_account_context"
        )
    else:
        selected_result = _r._empty_simulation_result(
            _r._diagnostic_placeholder_candidate(stake_quote_amount),
            start_capital,
        )
        selected_setups = []
        if allowed and validation_allowed:
            selection_reason = "validation_pool_stress_blocked_no_blindtest"
        elif allowed:
            selection_reason = "internal_selection_validation_blocked_no_blindtest"
        else:
            selection_reason = "diagnostic_only_no_trade_allowed_candidate"
    daily = _r._daily_pnls(selected_result.trades)
    best_training_quote_per_day = max(
        (evaluation.result.quote_per_day for evaluation in evaluations),
        default=0.0,
    )
    target_ratio = selected_result.quote_per_day / _r.TARGET_QUOTE_PER_DAY
    target_status = (
        "blindtest_target_reached"
        if selected_pool and selected_result.quote_per_day >= _r.TARGET_QUOTE_PER_DAY
        else "target_not_reached"
    )
    target_feasibility_audit = _build_target_feasibility_audit(
        split,
        stake_quote_amount,
        selected_result,
        best_training_quote_per_day,
        len(evaluations),
        len(allowed),
        len(validation_allowed),
        len(selected_pool),
    )
    walkforward_regime_research = _build_walkforward_regime_research(
        split.training_candles,
        selection_train_candles,
        selection_validation_candles,
        evaluations,
        validation_evaluations,
        selected_pool,
        folds=walkforward_folds,
        candidate_rows=walkforward_candidate_rows,
        used_for_pool_selection=True,
    )
    if progress_callback is not None:
        progress_callback(
            {
                "phase": "activity_first_router_diagnostics",
                "progress_pct": 88.7,
                "detail": "ETHUSDC-Regime-Diagnose wird erstellt",
            }
        )
    htf_training_edge_analysis = baseline_htf_analysis
    baseline_status, baseline_reason = _candidate_space_status(baseline_evaluations)
    filtered_allowed_count = sum(
        evaluation.trade_allowed for evaluation in htf_evaluations
    )
    htf_filter_integration = {
        "source": "derived_timeframes",
        "source_available": derived_timeframes_available,
        "source_used": bool(htf_candidates),
        "usage_mode": (
            "training_only_learned_frozen_entry_filter"
            if htf_candidates
            else "diagnostic_only_no_stable_candidate_rule"
        ),
        "training_only_winner_loser_separation": True,
        "changes_score": False,
        "changes_entry_filter": bool(htf_candidates),
        "changes_trade_gates": False,
        "blindtest_learning": False,
        "baseline_candidate_count": len(baseline_evaluations),
        "generated_filter_candidate_count": len(htf_candidates),
        "evaluated_filter_candidate_count": len(htf_evaluations),
        "baseline_trade_allowed_count": sum(
            evaluation.trade_allowed for evaluation in baseline_evaluations
        ),
        "filter_trade_allowed_count": filtered_allowed_count,
        "additional_trade_allowed_count": filtered_allowed_count,
        "candidate_space_before": baseline_status,
        "candidate_space_before_reason": baseline_reason,
        "candidate_space_after": status,
        "trade_allowed_blocked_resolved": (
            baseline_status == "trade_allowed_blocked" and bool(allowed)
        ),
        "learned_rules": learned_htf_rules,
        "selected_filter_candidate_count": sum(
            evaluation.candidate.htf_filter_timeframe is not None
            for evaluation in selected_pool
        ),
        "blindtest_trade_count": selected_result.trade_count,
        "blindtest_quote_per_day": selected_result.quote_per_day,
        "target_quote_per_day": _r.TARGET_QUOTE_PER_DAY,
        "target_ratio": target_ratio,
    }
    orderflow_allowed_count = sum(
        evaluation.trade_allowed for evaluation in orderflow_evaluations
    )
    orderflow_filter_integration = {
        "source": "ethusdc_kline_orderflow",
        "source_available": orderflow_source_available,
        "source_used": orderflow_source_available,
        "source_used_for_trade_decision": bool(orderflow_candidates),
        "usage_mode": (
            "training_only_learned_frozen_entry_filter"
            if orderflow_candidates
            else "diagnostic_only_no_stable_candidate_rule"
        ),
        "training_only_winner_loser_separation": bool(learned_orderflow_rules),
        "changes_score": False,
        "changes_entry_filter": bool(orderflow_candidates),
        "changes_trade_gates": False,
        "blindtest_learning": False,
        "baseline_candidate_count": len(baseline_evaluations),
        "generated_filter_candidate_count": len(orderflow_candidates),
        "evaluated_filter_candidate_count": len(orderflow_evaluations),
        "baseline_trade_allowed_count": sum(
            evaluation.trade_allowed for evaluation in baseline_evaluations
        ),
        "filter_trade_allowed_count": orderflow_allowed_count,
        "additional_trade_allowed_count": orderflow_allowed_count,
        "candidate_space_before": baseline_status,
        "candidate_space_before_reason": baseline_reason,
        "candidate_space_after": status,
        "trade_allowed_blocked_resolved": (
            baseline_status == "trade_allowed_blocked" and bool(allowed)
        ),
        "learned_rules": learned_orderflow_rules,
        "selected_filter_candidate_count": sum(
            evaluation.candidate.orderflow_filter_lookback is not None
            for evaluation in selected_pool
        ),
        "blindtest_trade_count": selected_result.trade_count,
        "blindtest_quote_per_day": selected_result.quote_per_day,
        "target_quote_per_day": _r.TARGET_QUOTE_PER_DAY,
        "target_ratio": target_ratio,
    }
    aggtrade_allowed_count = sum(
        evaluation.trade_allowed for evaluation in aggtrade_evaluations
    )
    aggtrade_filter_integration = {
        "source": "ethusdc_agg_trade_minutes",
        "source_available": aggtrade_source_available,
        "source_used": aggtrade_source_available,
        "source_used_for_trade_decision": bool(aggtrade_candidates),
        "usage_mode": (
            "training_only_learned_frozen_entry_filter"
            if aggtrade_candidates
            else "diagnostic_only_no_stable_candidate_rule"
        ),
        "training_only_winner_loser_separation": bool(learned_aggtrade_rules),
        "changes_score": False,
        "changes_entry_filter": bool(aggtrade_candidates),
        "changes_trade_gates": False,
        "blindtest_learning": False,
        "baseline_candidate_count": len(baseline_evaluations),
        "generated_filter_candidate_count": len(aggtrade_candidates),
        "evaluated_filter_candidate_count": len(aggtrade_evaluations),
        "baseline_trade_allowed_count": sum(
            evaluation.trade_allowed for evaluation in baseline_evaluations
        ),
        "filter_trade_allowed_count": aggtrade_allowed_count,
        "additional_trade_allowed_count": aggtrade_allowed_count,
        "candidate_space_before": baseline_status,
        "candidate_space_before_reason": baseline_reason,
        "candidate_space_after": status,
        "trade_allowed_blocked_resolved": (
            baseline_status == "trade_allowed_blocked" and bool(allowed)
        ),
        "learned_rules": learned_aggtrade_rules,
        "selected_filter_candidate_count": sum(
            evaluation.candidate.aggtrade_filter_lookback is not None
            for evaluation in selected_pool
        ),
        "blindtest_trade_count": selected_result.trade_count,
        "blindtest_quote_per_day": selected_result.quote_per_day,
        "target_quote_per_day": _r.TARGET_QUOTE_PER_DAY,
        "target_ratio": target_ratio,
    }
    context_allowed_count = sum(
        evaluation.trade_allowed for evaluation in context_evaluations
    )
    context_market_filter_integration = {
        "sources": ("BTCUSDC", "ETHBTC", "ETHUSDT", "USDCUSDT"),
        "available_sources": context_sources_available,
        "source_coverage": {
            symbol: round(coverage, 6)
            for symbol, coverage in context_feature_store.source_coverage.items()
        },
        "source_available": bool(context_sources_available),
        "source_used": bool(context_sources_available),
        "source_used_for_trade_decision": bool(context_candidates),
        "usage_mode": (
            "training_only_learned_frozen_entry_filter"
            if context_candidates
            else "diagnostic_only_no_stable_candidate_rule"
        ),
        "training_only_winner_loser_separation": bool(learned_context_rules),
        "changes_score": False,
        "changes_entry_filter": bool(context_candidates),
        "changes_trade_gates": False,
        "blindtest_learning": False,
        "baseline_candidate_count": len(baseline_evaluations),
        "generated_filter_candidate_count": len(context_candidates),
        "evaluated_filter_candidate_count": len(context_evaluations),
        "baseline_trade_allowed_count": sum(
            evaluation.trade_allowed for evaluation in baseline_evaluations
        ),
        "filter_trade_allowed_count": context_allowed_count,
        "additional_trade_allowed_count": context_allowed_count,
        "candidate_space_before": baseline_status,
        "candidate_space_before_reason": baseline_reason,
        "candidate_space_after": status,
        "trade_allowed_blocked_resolved": (
            baseline_status == "trade_allowed_blocked" and bool(allowed)
        ),
        "learned_rules": learned_context_rules,
        "selected_filter_candidate_count": sum(
            evaluation.candidate.context_filter_lookback is not None
            for evaluation in selected_pool
        ),
        "blindtest_trade_count": selected_result.trade_count,
        "blindtest_quote_per_day": selected_result.quote_per_day,
        "target_quote_per_day": _r.TARGET_QUOTE_PER_DAY,
        "target_ratio": target_ratio,
    }
    selection_validation_summary = {
        "selection_validation_used": bool(selection_validation_candles),
        "selection_train_start": (
            selection_train_candles[0].open_time if selection_train_candles else None
        ),
        "selection_train_end": (
            selection_train_candles[-1].open_time if selection_train_candles else None
        ),
        "selection_validation_start": (
            selection_validation_candles[0].open_time
            if selection_validation_candles
            else None
        ),
        "selection_validation_end": (
            selection_validation_candles[-1].open_time
            if selection_validation_candles
            else None
        ),
        "selection_train_candle_count": len(selection_train_candles),
        "selection_validation_candle_count": len(selection_validation_candles),
        "learning_scope": "selection_train_only",
        "validation_leakage_risk": "none_known",
        "pre_validation_trade_allowed_count": len(allowed),
        "validated_candidate_count": len(validation_evaluations),
        "post_validation_trade_allowed_count": len(validation_allowed),
        "validation_rejection_counts": _r._rejection_counts(validation_evaluations),
        "pool_selection": pool_selection_diagnostics,
        "validation_pool_quote_per_day": validation_pool_result.quote_per_day,
        "validation_pool_total_net_pnl": validation_pool_result.total_net_pnl,
        "validation_pool_trade_count": validation_pool_result.trade_count,
        "validation_pool_max_drawdown": validation_pool_result.max_drawdown,
        "validation_pool_profit_factor": _r._profit_factor(
            validation_pool_result.trades
        ),
        "validation_pool_fee_to_gross_ratio": _r._fee_to_gross_ratio(
            validation_pool_result
        ),
        "validation_pool_temporal_stability": (
            _temporal_validation_stability_report(
                validation_pool_result,
                selection_validation_candles,
            )
        ),
        "validation_pool_passed": validation_pool_passed,
        "validation_pool_rejection_reason": validation_pool_rejection,
        "final_blindtest_pool_size": len(selected_pool),
    }
    rejection_summary = {
        "router_name": "activity_first_router",
        "candidate_space_status": status,
        "candidate_space_reason": reason,
        "training_candidate_space_status": training_status,
        "training_candidate_space_reason": training_reason,
        "rejection_counts": _r._rejection_counts(evaluations),
        "selection_validation": selection_validation_summary,
        "search_pass_summary": _search_pass_summary(evaluations, derived_features),
        "eth_regime_diagnostics": _r._eth_regime_diagnostics(split.training_candles),
        "derived_timeframes_available": derived_timeframes_available,
        "derived_timeframes_used_by_router": derived_timeframes_used_by_router,
        "used_timeframes": derived_features.used_timeframes,
        "missing_timeframe_reason": missing_timeframe_reason,
        "derived_timeframe_closed_candle_counts": derived_features.closed_candle_counts,
        "derived_timeframe_usage_mode": (
            "training_only_frozen_entry_filter_plus_diagnostics"
            if htf_candidates
            else "candidate_entry_diagnostics_only_no_gate_or_score_change"
        ),
        "derived_timeframe_training_edge_analysis": htf_training_edge_analysis,
        "kline_orderflow_training_edge_analysis": orderflow_training_edge_analysis,
        "kline_orderflow_filter_integration": orderflow_filter_integration,
        "aggtrade_training_edge_analysis": aggtrade_training_edge_analysis,
        "aggtrade_filter_integration": aggtrade_filter_integration,
        "context_market_training_edge_analysis": context_market_training_edge_analysis,
        "context_market_filter_integration": context_market_filter_integration,
        "htf_filter_integration": htf_filter_integration,
        "target_feasibility_audit": target_feasibility_audit,
        "walkforward_regime_research": walkforward_regime_research,
        "walkforward_regime_research_version": WALKFORWARD_REGIME_RESEARCH_VERSION,
        "walkforward_stability_pool_selection_version": (
            WALKFORWARD_STABILITY_POOL_SELECTION_VERSION
        ),
        "walkforward_regime_research_used_for_trade_decision": True,
        "walkforward_stability_used_for_pool_selection": True,
        "best_activity_candidate": _candidate_summary(best_activity, derived_features) if best_activity else None,
        "best_edge_candidate": _candidate_summary(best_edge, derived_features) if best_edge else None,
        "best_balanced_candidate": _candidate_summary(best_balanced, derived_features) if best_balanced else None,
        "best_fee_survivor_candidate": _candidate_summary(best_fee_survivor, derived_features) if best_fee_survivor else None,
        "best_target_candidate": _candidate_summary(best_target, derived_features) if best_target else None,
        "selected_trade_allowed_candidates": selected_setups,
        "selected_trade_allowed_candidate": selected_setups[0] if selected_setups else None,
        "selected_pool_size": len(selected_pool),
        "pool_raw_proposals": selected_result.signal_count,
        "pool_executed_trades": selected_result.trade_count,
        "pool_skipped_overlaps": selected_result.no_trade_count,
        "target_feasibility_status": target_status,
        "target_feasibility_assessment": target_feasibility_audit["assessment"],
        "best_training_quote_per_day": best_training_quote_per_day,
        "diagnostic_only": not selected_pool,
        "selection_reason": selection_reason,
    }
    artifact = {
        "run_type": "unknown",
        "smoke_test_not_performance_proof": False,
        "live_release_allowed": False,
        "diagnostic_only": not selected_pool,
        "trade_allowed": bool(selected_pool),
        "blindtest_strategy_executed": bool(selected_pool),
        "selection_policy": (
            "selection_train_validation_walkforward_stability_pool_one_shared_account_context"
        ),
        "selection_reason": selection_reason,
        "exchange_info_filters_used": filters is not None,
        "candidate_generation_version": WALKFORWARD_STABILITY_POOL_SELECTION_VERSION,
        "base_candidate_generation_version": "activity_first_v11_eth_regime_expanded",
        "eth_specific_strategy_scope": True,
        "historical_news_labels_used": False,
        "historical_orderbook_used": False,
        "fast_rolling_metrics_used": True,
        "scaled_eth_activity_gate_used": True,
        "eth_selection_penalty_used": True,
        "multi_candidate_pool_used": True,
        "pool_overlap_guard_used": True,
        "selection_validation_guard_used": True,
        "validation_optimized_pool_used": True,
        "conservative_regime_pool_used": True,
        "walkforward_stability_pool_selection_used": True,
        "pool_execution_policy": "one_position_at_a_time",
        "selected_pool_size": len(selected_pool),
        "pool_raw_proposals": selected_result.signal_count,
        "pool_executed_trades": selected_result.trade_count,
        "pool_skipped_overlaps": selected_result.no_trade_count,
        "selection_validation": selection_validation_summary,
        "target_feasibility_audit": target_feasibility_audit,
        "target_feasibility_audit_version": TARGET_FEASIBILITY_AUDIT_VERSION,
        "target_feasibility_assessment": target_feasibility_audit["assessment"],
        "walkforward_regime_research": walkforward_regime_research,
        "walkforward_regime_research_version": WALKFORWARD_REGIME_RESEARCH_VERSION,
        "walkforward_stability_pool_selection_version": (
            WALKFORWARD_STABILITY_POOL_SELECTION_VERSION
        ),
        "walkforward_regime_research_used_for_trade_decision": True,
        "walkforward_stability_used_for_pool_selection": True,
        "derived_timeframes_available": derived_timeframes_available,
        "derived_timeframes_used_by_router": derived_timeframes_used_by_router,
        "used_timeframes": derived_features.used_timeframes,
        "missing_timeframe_reason": missing_timeframe_reason,
        "derived_timeframe_usage_mode": (
            "training_only_frozen_entry_filter_plus_diagnostics"
            if htf_candidates
            else "candidate_entry_diagnostics_only_no_gate_or_score_change"
        ),
        "derived_timeframe_training_edge_analysis_available": bool(derived_features.used_timeframes),
        "derived_timeframes_used_for_trade_decision": bool(htf_candidates),
        "htf_filter_integration": htf_filter_integration,
        "kline_orderflow_available": orderflow_source_available,
        "kline_orderflow_used_by_router": orderflow_source_available,
        "kline_orderflow_used_for_trade_decision": bool(orderflow_candidates),
        "kline_orderflow_training_edge_analysis_available": True,
        "kline_orderflow_filter_integration": orderflow_filter_integration,
        "aggtrade_available": aggtrade_source_available,
        "aggtrade_used_by_router": aggtrade_source_available,
        "aggtrade_used_for_trade_decision": bool(aggtrade_candidates),
        "aggtrade_training_edge_analysis_available": True,
        "aggtrade_filter_integration": aggtrade_filter_integration,
        "context_markets_available": bool(context_sources_available),
        "context_markets_available_sources": context_sources_available,
        "context_markets_used_by_router": bool(context_sources_available),
        "context_markets_used_for_trade_decision": bool(context_candidates),
        "context_market_training_edge_analysis_available": True,
        "context_market_filter_integration": context_market_filter_integration,
    }
    return _r.ActivityFirstRouterReport(
        run_id,
        "activity_first_router",
        _r.CONFIG.symbol,
        _r.CONFIG.quote_asset,
        start_capital,
        stake_quote_amount,
        profile,
        split.training_start,
        split.training_end,
        split.blindtest_start,
        split.blindtest_end,
        status,
        reason,
        len(all_candidate_ids),
        len(evaluations),
        len(validation_allowed) if validation_pool_passed else 0,
        len(selected_pool),
        sum(1 for evaluation in evaluations if evaluation.rejection_reason),
        selected_setups,
        rejection_summary,
        _candidate_summary(best_activity, derived_features) if best_activity else None,
        _candidate_summary(best_edge, derived_features) if best_edge else None,
        _candidate_summary(best_balanced, derived_features) if best_balanced else None,
        _candidate_summary(best_fee_survivor, derived_features) if best_fee_survivor else None,
        _candidate_summary(best_target, derived_features) if best_target else None,
        selected_result.final_capital_reference,
        selected_result.total_gross_pnl,
        selected_result.total_fees,
        selected_result.total_net_pnl,
        selected_result.total_net_pnl / start_capital * 100 if start_capital else 0.0,
        selected_result.quote_per_day,
        selected_result.trade_count,
        selected_result.winning_trades,
        selected_result.losing_trades,
        selected_result.neutral_trades,
        selected_result.max_drawdown,
        sum(1 for value in daily.values() if value > 0),
        sum(1 for value in daily.values() if value < 0),
        sum(1 for value in daily.values() if value == 0),
        max(daily.values(), default=0.0),
        min(daily.values(), default=0.0),
        best_training_quote_per_day,
        _r.TARGET_QUOTE_PER_DAY,
        target_ratio,
        target_status,
        artifact,
        [asdict(trade) for trade in selected_result.trades[:250]],
    )


_r._candidate_rejection = _candidate_rejection
_r._evaluate_training_candidates = _evaluate_training_candidates
_r._search_pass_summary = _search_pass_summary
_r._candidate_space_status = _candidate_space_status
_r.build_activity_first_router_report = build_activity_first_router_report
_r._scaled_eth_activity_gate_used = True
_r._eth_selection_penalty_used = True
_r._multi_candidate_pool_used = True
_r._pool_overlap_guard_used = True
