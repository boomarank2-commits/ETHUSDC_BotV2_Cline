"""ETHUSDC router package patch layer."""

from dataclasses import asdict

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
    score = result.quote_per_day + min(result.trades_per_day, 6.0) * 0.05 + min(profit_factor, 2.0) * 0.03 - result.max_drawdown * 0.01 - target_distance * 0.03
    if _is_eth(result) and result.trades_per_day < 1.0:
        score -= 0.20 + (1.0 - result.trades_per_day) * 0.10
    return score


def _evaluate_training_candidates(candidates, candles, start_capital_reference, filters, progress_callback=None):
    market = _r._MarketMetrics(candles)
    ordered = sorted(candidates, key=lambda candidate: (candidate.lookback_candles, candidate.search_pass, candidate.family, candidate.candidate_id))
    evaluations = []
    total = len(ordered)
    for done, candidate in enumerate(ordered, start=1):
        result = _r._run_candidate_on_candles(candles, candidate, start_capital_reference, filters, market)
        rejection = _candidate_rejection(result)
        activity = _r._activity_class(result.trades_per_day)
        distance = abs(_r.TARGET_QUOTE_PER_DAY - result.quote_per_day)
        evaluations.append(_r._TrainingEvaluation(candidate, result, activity, rejection is None, rejection, _score(result), distance))
        _r._emit_router_progress(progress_callback, done, total)
    return evaluations


def _select_candidate_pool(evaluations):
    allowed = [evaluation for evaluation in evaluations if evaluation.trade_allowed]
    if not allowed:
        return []
    max_count = max(2, min(25, _ceil(_run_days(evaluations) / 14.0)))
    ordered = sorted(allowed, key=lambda evaluation: (evaluation.balanced_score, evaluation.result.quote_per_day, evaluation.result.trades_per_day), reverse=True)
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


def _aggregate_pool_result(candles, selected_pool, start_capital, filters):
    if not selected_pool:
        return _r._empty_simulation_result(_r._diagnostic_placeholder_candidate(start_capital), start_capital)
    market = _r._MarketMetrics(candles)
    proposals = []
    for evaluation in selected_pool:
        result = _r._run_candidate_on_candles(candles, evaluation.candidate, start_capital, filters, market)
        for trade in result.trades:
            proposals.append((trade.entry_time, -evaluation.balanced_score, trade.exit_time, trade.candidate_id, trade))
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
    pool_candidate = _r.ActivityFirstCandidate("multi_candidate_pool", "activity_first_router_pool", 1, 0.0, 0.0, 0.0, 0, 0, start_capital, "multi_candidate_pool")
    return _r.ActivityFirstSimulationResult(pool_candidate, start_capital, start_capital + total_net, total_gross, total_fees, total_net, total_net / days, len(chosen), len(chosen) / days, sum(1 for trade in chosen if trade.net_pnl > 0), sum(1 for trade in chosen if trade.net_pnl < 0), sum(1 for trade in chosen if trade.net_pnl == 0), max_drawdown, len(proposals), skipped, sum(evaluation.result.blocked_signal_count for evaluation in selected_pool), chosen)


def _search_pass_summary(evaluations):
    rows = []
    for search_pass in sorted({evaluation.candidate.search_pass for evaluation in evaluations}):
        current = [evaluation for evaluation in evaluations if evaluation.candidate.search_pass == search_pass]
        best = max(current, key=lambda evaluation: evaluation.result.quote_per_day, default=None)
        rows.append({"pass_name": search_pass, "candidates_generated": len(current), "setup_tests_run": len(current), "candidates_positive_net": sum(1 for evaluation in current if evaluation.result.total_net_pnl > 0), "candidates_active_enough": sum(1 for evaluation in current if _activity_ok(evaluation.result)), "candidates_trade_allowed": sum(1 for evaluation in current if evaluation.trade_allowed), "best_candidate": _r._candidate_summary(best) if best else None})
    return rows


def _candidate_space_status(evaluations):
    if not evaluations:
        return "activity_search_failed", "no activity-first candidates were generated"
    if any(evaluation.trade_allowed for evaluation in evaluations):
        return "trade_allowed_found", "at least one active after-fee positive setup exists"
    if any(evaluation.result.total_net_pnl > 0 for evaluation in evaluations):
        return "trade_allowed_blocked", "positive candidates exist but failed robustness/activity filters"
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
    evaluations = _evaluate_training_candidates(candidates, split.training_candles, start_capital, filters, progress_callback)
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
        selected_result = _aggregate_pool_result(split.blindtest_candles, selected_pool, start_capital, filters)
        selected_setups = [_r._candidate_summary(evaluation) for evaluation in selected_pool]
        selection_reason = "training_pool_one_shared_account_context"
    else:
        selected_result = _r._empty_simulation_result(_r._diagnostic_placeholder_candidate(stake_quote_amount), start_capital)
        selected_setups = []
        selection_reason = "diagnostic_only_no_trade_allowed_candidate"
    daily = _r._daily_pnls(selected_result.trades)
    best_training_quote_per_day = max((evaluation.result.quote_per_day for evaluation in evaluations), default=0.0)
    target_ratio = selected_result.quote_per_day / _r.TARGET_QUOTE_PER_DAY
    target_status = "blindtest_target_reached" if selected_pool and selected_result.quote_per_day >= _r.TARGET_QUOTE_PER_DAY else "target_not_reached"
    if progress_callback is not None:
        progress_callback({"phase": "activity_first_router_diagnostics", "progress_pct": 88.7, "detail": "ETHUSDC-Regime-Diagnose wird erstellt"})
    rejection_summary = {"router_name": "activity_first_router", "candidate_space_status": status, "candidate_space_reason": reason, "rejection_counts": _r._rejection_counts(evaluations), "search_pass_summary": _search_pass_summary(evaluations), "eth_regime_diagnostics": _r._eth_regime_diagnostics(split.training_candles), "best_activity_candidate": _r._candidate_summary(best_activity) if best_activity else None, "best_edge_candidate": _r._candidate_summary(best_edge) if best_edge else None, "best_balanced_candidate": _r._candidate_summary(best_balanced) if best_balanced else None, "best_fee_survivor_candidate": _r._candidate_summary(best_fee_survivor) if best_fee_survivor else None, "best_target_candidate": _r._candidate_summary(best_target) if best_target else None, "selected_trade_allowed_candidates": selected_setups, "selected_trade_allowed_candidate": selected_setups[0] if selected_setups else None, "selected_pool_size": len(selected_pool), "pool_raw_proposals": selected_result.signal_count, "pool_executed_trades": selected_result.trade_count, "pool_skipped_overlaps": selected_result.no_trade_count, "target_feasibility_status": target_status, "best_training_quote_per_day": best_training_quote_per_day, "diagnostic_only": not selected_pool, "selection_reason": selection_reason}
    artifact = {"run_type": "unknown", "smoke_test_not_performance_proof": False, "live_release_allowed": False, "legacy_cluster_router_used": False, "diagnostic_only": not selected_pool, "trade_allowed": bool(selected_pool), "blindtest_strategy_executed": bool(selected_pool), "selection_policy": "training_top_n_pool_one_shared_account_context", "selection_reason": selection_reason, "exchange_info_filters_used": filters is not None, "candidate_generation_version": "activity_first_v6_multi_candidate_pool", "eth_specific_strategy_scope": True, "historical_news_labels_used": False, "historical_orderbook_used": False, "fast_rolling_metrics_used": True, "scaled_eth_activity_gate_used": True, "eth_selection_penalty_used": True, "multi_candidate_pool_used": True, "pool_overlap_guard_used": True, "pool_execution_policy": "one_position_at_a_time", "selected_pool_size": len(selected_pool), "pool_raw_proposals": selected_result.signal_count, "pool_executed_trades": selected_result.trade_count, "pool_skipped_overlaps": selected_result.no_trade_count}
    return _r.ActivityFirstRouterReport(run_id, "activity_first_router", _r.CONFIG.symbol, _r.CONFIG.quote_asset, start_capital, stake_quote_amount, profile, split.training_start, split.training_end, split.blindtest_start, split.blindtest_end, status, reason, len(candidates), len(evaluations), len(allowed), len(selected_pool), sum(1 for evaluation in evaluations if evaluation.rejection_reason), selected_setups, rejection_summary, _r._candidate_summary(best_activity) if best_activity else None, _r._candidate_summary(best_edge) if best_edge else None, _r._candidate_summary(best_balanced) if best_balanced else None, _r._candidate_summary(best_fee_survivor) if best_fee_survivor else None, _r._candidate_summary(best_target) if best_target else None, selected_result.final_capital_reference, selected_result.total_gross_pnl, selected_result.total_fees, selected_result.total_net_pnl, selected_result.total_net_pnl / start_capital * 100 if start_capital else 0.0, selected_result.quote_per_day, selected_result.trade_count, selected_result.winning_trades, selected_result.losing_trades, selected_result.neutral_trades, selected_result.max_drawdown, sum(1 for value in daily.values() if value > 0), sum(1 for value in daily.values() if value < 0), sum(1 for value in daily.values() if value == 0), max(daily.values(), default=0.0), min(daily.values(), default=0.0), best_training_quote_per_day, _r.TARGET_QUOTE_PER_DAY, target_ratio, target_status, artifact, [asdict(trade) for trade in selected_result.trades[:250]])


_r._candidate_rejection = _candidate_rejection
_r._evaluate_training_candidates = _evaluate_training_candidates
_r._search_pass_summary = _search_pass_summary
_r._candidate_space_status = _candidate_space_status
_r.build_activity_first_router_report = build_activity_first_router_report
_r._scaled_eth_activity_gate_used = True
_r._eth_selection_penalty_used = True
_r._multi_candidate_pool_used = True
_r._pool_overlap_guard_used = True
