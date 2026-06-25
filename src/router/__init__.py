"""ETHUSDC router package patch layer."""

from dataclasses import asdict, replace

from src.data.derived_timeframes import (
    DerivedTimeframeFeatureSeries,
    build_closed_timeframe_feature_series,
    build_closed_timeframe_feature_snapshots,
)

from . import activity_first_router_report as _r


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
    """Learn at most one deterministic HTF range filter per positive ETH candidate."""
    candidate_timeframes = [
        timeframe
        for timeframe in ("1h", "4h", "1d")
        if timeframe in htf_analysis["candidate_timeframes_for_future_review"]
    ]
    learned_candidates = []
    learned_rules = []
    for evaluation in evaluations:
        if evaluation.result.total_net_pnl <= 0 or not _is_eth(evaluation.result):
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
    allowed = [evaluation for evaluation in evaluations if evaluation.trade_allowed]
    if not allowed:
        return []
    max_count = max(2, min(25, _ceil(_run_days(evaluations) / 14.0)))
    ordered = sorted(
        allowed,
        key=lambda evaluation: (
            evaluation.balanced_score,
            evaluation.result.quote_per_day,
            evaluation.result.trades_per_day,
        ),
        reverse=True,
    )
    family_cap = max(2, _ceil(max_count / 5.0))
    pool = []
    family_counts = {}
    for evaluation in ordered:
        family = evaluation.candidate.family
        if family_counts.get(family, 0) >= family_cap:
            continue
        pool.append(evaluation)
        family_counts[family] = family_counts.get(family, 0) + 1
        if len(pool) >= max_count:
            break
    return pool


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
    return summary


def _aggregate_pool_result(
    candles,
    selected_pool,
    start_capital,
    filters,
    htf_warmup_candles=None,
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
    candidates = _r._generate_activity_first_candidates(stake_quote_amount, profile)
    baseline_evaluations = _evaluate_training_candidates(
        candidates,
        split.training_candles,
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
        split.training_candles,
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
    htf_evaluations = _evaluate_htf_filter_candidates(
        htf_candidates,
        split.training_candles,
        start_capital,
        filters,
        progress_callback,
    )
    evaluations = baseline_evaluations + htf_evaluations
    all_candidate_ids = {candidate.candidate_id for candidate in candidates}
    all_candidate_ids.update(candidate.candidate_id for candidate in htf_candidates)
    decision_open_times.update(
        trade.entry_time
        for evaluation in htf_evaluations
        for trade in evaluation.result.trades
    )
    if htf_evaluations:
        derived_features = build_closed_timeframe_feature_snapshots(
            split.training_candles,
            decision_open_times,
        )
    allowed = [evaluation for evaluation in evaluations if evaluation.trade_allowed]
    selected_pool = _select_candidate_pool(evaluations)
    best_activity = max(evaluations, key=lambda evaluation: evaluation.result.trades_per_day, default=None)
    best_edge = max(evaluations, key=lambda evaluation: evaluation.result.quote_per_day, default=None)
    best_balanced = max(evaluations, key=lambda evaluation: evaluation.balanced_score, default=None)
    fee_survivors = [evaluation for evaluation in evaluations if evaluation.result.total_net_pnl > 0]
    best_fee_survivor = max(fee_survivors, key=lambda evaluation: evaluation.result.quote_per_day, default=None)
    best_target = min(evaluations, key=lambda evaluation: evaluation.target_distance, default=None)
    status, reason = _candidate_space_status(evaluations)
    if selected_pool:
        selected_result = _aggregate_pool_result(
            split.blindtest_candles,
            selected_pool,
            start_capital,
            filters,
            htf_warmup_candles=split.training_candles[-2880:],
        )
        selected_setups = [
            _candidate_summary(evaluation, derived_features)
            for evaluation in selected_pool
        ]
        selection_reason = "training_pool_one_shared_account_context"
    else:
        selected_result = _r._empty_simulation_result(
            _r._diagnostic_placeholder_candidate(stake_quote_amount),
            start_capital,
        )
        selected_setups = []
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
    rejection_summary = {
        "router_name": "activity_first_router",
        "candidate_space_status": status,
        "candidate_space_reason": reason,
        "rejection_counts": _r._rejection_counts(evaluations),
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
        "htf_filter_integration": htf_filter_integration,
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
        "best_training_quote_per_day": best_training_quote_per_day,
        "diagnostic_only": not selected_pool,
        "selection_reason": selection_reason,
    }
    artifact = {
        "run_type": "unknown",
        "smoke_test_not_performance_proof": False,
        "live_release_allowed": False,
        "legacy_cluster_router_used": False,
        "diagnostic_only": not selected_pool,
        "trade_allowed": bool(selected_pool),
        "blindtest_strategy_executed": bool(selected_pool),
        "selection_policy": "training_top_n_pool_one_shared_account_context",
        "selection_reason": selection_reason,
        "exchange_info_filters_used": filters is not None,
        "candidate_generation_version": "activity_first_v7_htf_training_filter",
        "eth_specific_strategy_scope": True,
        "historical_news_labels_used": False,
        "historical_orderbook_used": False,
        "fast_rolling_metrics_used": True,
        "scaled_eth_activity_gate_used": True,
        "eth_selection_penalty_used": True,
        "multi_candidate_pool_used": True,
        "pool_overlap_guard_used": True,
        "pool_execution_policy": "one_position_at_a_time",
        "selected_pool_size": len(selected_pool),
        "pool_raw_proposals": selected_result.signal_count,
        "pool_executed_trades": selected_result.trade_count,
        "pool_skipped_overlaps": selected_result.no_trade_count,
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
        len(allowed),
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
