"""Router package patches for ETHUSDC activity-first selection.

Contract: 1d/7d/14d/30d smoke and full backtest use the same engine,
search space, filters, costs and scoring. Only the train/blind window length
changes. Selection is a training-only Top-N candidate pool, not a single winner.
"""

from dataclasses import asdict

from . import activity_first_router_report as _report


def _ceil_positive(value: float) -> int:
    whole = int(value)
    return whole if value <= whole else whole + 1


def _training_days_from_result(result: _report.ActivityFirstSimulationResult) -> float:
    if result.trade_count <= 0 or result.trades_per_day <= 0:
        return 0.0
    return max(1.0, result.trade_count / result.trades_per_day)


def _training_days_from_evaluations(evaluations) -> float:
    return max((_training_days_from_result(e.result) for e in evaluations), default=1.0)


def _active_day_count(trades: list[_report.ActivityFirstTrade]) -> int:
    return len({trade.exit_time[:10] for trade in trades})


def _is_eth_regime_candidate(result: _report.ActivityFirstSimulationResult) -> bool:
    return result.candidate.search_pass.startswith("eth_")


def _eth_regime_activity_minimums(result: _report.ActivityFirstSimulationResult) -> tuple[int, int]:
    training_days = _training_days_from_result(result)
    min_trades = max(2, min(20, _ceil_positive(training_days * 0.20)))
    min_active_days = max(1, min(10, _ceil_positive(training_days * 0.10)))
    return min_trades, min_active_days


def _passes_activity_gate(result: _report.ActivityFirstSimulationResult) -> bool:
    if result.trade_count == 0:
        return False
    if _is_eth_regime_candidate(result):
        min_trades, min_active_days = _eth_regime_activity_minimums(result)
        return result.trade_count >= min_trades and _active_day_count(result.trades) >= min_active_days
    return result.trades_per_day >= 1.0


def _candidate_rejection(result: _report.ActivityFirstSimulationResult) -> str | None:
    if not _passes_activity_gate(result):
        return "rejected_by_activity"
    if result.trades_per_day > 10.0:
        return "rejected_by_overactivity"
    if result.total_net_pnl <= 0:
        if result.total_gross_pnl > 0 and result.total_fees >= result.total_gross_pnl:
            return "rejected_by_fees"
        return "rejected_by_training_net"
    ratio = _report._fee_to_gross_ratio(result)
    if ratio is not None and ratio > _report.MAX_FEE_TO_GROSS_RATIO:
        return "rejected_by_fees"
    profit_factor = _report._profit_factor(result.trades)
    if profit_factor is not None and profit_factor < _report.MIN_PROFIT_FACTOR:
        return "rejected_by_profit_factor"
    if result.max_drawdown > _report.MAX_DRAWDOWN_PCT:
        return "rejected_by_drawdown"
    return None


def _selection_score(result: _report.ActivityFirstSimulationResult) -> float:
    target_distance = abs(_report.TARGET_QUOTE_PER_DAY - result.quote_per_day)
    pf = _report._profit_factor(result.trades) or 0.0
    score = (
        result.quote_per_day
        + min(result.trades_per_day, 6.0) * 0.05
        + min(pf, 2.0) * 0.03
        - result.max_drawdown * 0.01
        - target_distance * 0.03
    )
    if _is_eth_regime_candidate(result) and result.trades_per_day < 1.0:
        score -= 0.20 + (1.0 - result.trades_per_day) * 0.10
    return score


def _evaluate_training_candidates(candidates, candles, start_capital_reference, filters, progress_callback=None):
    evaluations = []
    market = _report._MarketMetrics(candles)
    ordered = sorted(candidates, key=lambda c: (c.lookback_candles, c.search_pass, c.family, c.candidate_id))
    total = len(ordered)
    for done, candidate in enumerate(ordered, start=1):
        result = _report._run_candidate_on_candles(candles, candidate, start_capital_reference, filters, market)
        rejection = _candidate_rejection(result)
        activity = _report._activity_class(result.trades_per_day)
        target_distance = abs(_report.TARGET_QUOTE_PER_DAY - result.quote_per_day)
        evaluations.append(_report._TrainingEvaluation(candidate, result, activity, rejection is None, rejection, _selection_score(result), target_distance))
        _report._emit_router_progress(progress_callback, done, total)
    return evaluations


def _select_candidate_pool(evaluations) -> list:
    allowed = [e for e in evaluations if e.trade_allowed]
    if not allowed:
        return []
    training_days = _training_days_from_evaluations(evaluations)
    max_count = max(2, min(25, _ceil_positive(training_days / 14.0)))
    ordered = sorted(allowed, key=lambda e: (e.balanced_score, e.result.quote_per_day, e.result.trades_per_day), reverse=True)
    family_cap = max(2, _ceil_positive(max_count / 5.0))
    pool = []
    used_ids = set()
    family_counts = {}
    for evaluation in ordered:
        family = evaluation.candidate.family
        if family_counts.get(family, 0) >= family_cap:
            continue
        pool.append(evaluation)
        used_ids.add(evaluation.candidate.candidate_id)
        family_counts[family] = family_counts.get(family, 0) + 1
        if len(pool) >= max_count:
            return pool
    for evaluation in ordered:
        if evaluation.candidate.candidate_id in used_ids:
            continue
        pool.append(evaluation)
        used_ids.add(evaluation.candidate.candidate_id)
        if len(pool) >= max_count:
            break
    return pool


def _aggregate_pool_result(candles, selected_pool, start_capital, filters) -> _report.ActivityFirstSimulationResult:
    if not selected_pool:
        return _report._empty_simulation_result(_report._diagnostic_placeholder_candidate(start_capital), start_capital)
    blindtest_market = _report._MarketMetrics(candles)
    trades = []
    gross = fees = net = 0.0
    for evaluation in selected_pool:
        result = _report._run_candidate_on_candles(candles, evaluation.candidate, start_capital, filters, blindtest_market)
        trades.extend(result.trades)
        gross += result.total_gross_pnl
        fees += result.total_fees
        net += result.total_net_pnl
    trades.sort(key=lambda t: (t.entry_time, t.exit_time, t.candidate_id))
    equity = start_capital
    peak = start_capital
    max_dd = 0.0
    for trade in trades:
        equity += trade.net_pnl
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * 100)
    days = max(1.0, len(candles) / 1440)
    pool_candidate = _report.ActivityFirstCandidate(
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
    return _report.ActivityFirstSimulationResult(
        pool_candidate,
        start_capital,
        start_capital + net,
        gross,
        fees,
        net,
        net / days,
        len(trades),
        len(trades) / days,
        sum(1 for t in trades if t.net_pnl > 0),
        sum(1 for t in trades if t.net_pnl < 0),
        sum(1 for t in trades if t.net_pnl == 0),
        max_dd,
        sum(e.result.signal_count for e in selected_pool),
        0,
        sum(e.result.blocked_signal_count for e in selected_pool),
        trades,
    )


def _search_pass_summary(evaluations) -> list[dict]:
    result = []
    for search_pass in sorted({e.candidate.search_pass for e in evaluations}):
        rows = [e for e in evaluations if e.candidate.search_pass == search_pass]
        best = max(rows, key=lambda e: e.result.quote_per_day, default=None)
        result.append({
            "pass_name": search_pass,
            "candidates_generated": len(rows),
            "setup_tests_run": len(rows),
            "candidates_positive_net": sum(1 for e in rows if e.result.total_net_pnl > 0),
            "candidates_active_enough": sum(1 for e in rows if _passes_activity_gate(e.result)),
            "candidates_trade_allowed": sum(1 for e in rows if e.trade_allowed),
            "best_candidate": _report._candidate_summary(best) if best else None,
        })
    return result


def _candidate_space_status(evaluations) -> tuple[str, str]:
    if not evaluations:
        return "activity_search_failed", "no activity-first candidates were generated"
    if any(e.trade_allowed for e in evaluations):
        return "trade_allowed_found", "at least one active after-fee positive setup exists"
    if any(e.result.total_net_pnl > 0 for e in evaluations):
        return "trade_allowed_blocked", "positive candidates exist but failed robustness/activity filters"
    if any(e.result.total_gross_pnl > 0 for e in evaluations):
        return "edge_after_fees_failed", "gross-positive candidates exist, but fees removed the edge"
    if any(_passes_activity_gate(e.result) for e in evaluations):
        return "target_edge_missing", "active candidates exist, but no gross edge was found"
    if any(e.result.trade_count > 0 for e in evaluations):
        return "target_activity_missing", "signals exist, but activity is below scaled activity gate"
    return "no_active_candidates", "no candidate produced training trades"


def build_activity_first_router_report(run_id, split, stake_quote_amount=100.0, profile="normal", progress_callback=None):
    if split.symbol != _report.CONFIG.symbol:
        raise ValueError(f"symbol must be {_report.CONFIG.symbol}")
    start_capital = float(stake_quote_amount)
    filters = _report.load_exchange_info_filters()
    candidates = _report._generate_activity_first_candidates(stake_quote_amount, profile)
    evaluations = _evaluate_training_candidates(candidates, split.training_candles, start_capital, filters, progress_callback)
    allowed = [e for e in evaluations if e.trade_allowed]
    selected_pool = _select_candidate_pool(evaluations)
    best_activity = max(evaluations, key=lambda e: e.result.trades_per_day, default=None)
    best_edge = max(evaluations, key=lambda e: e.result.quote_per_day, default=None)
    best_balanced = max(evaluations, key=lambda e: e.balanced_score, default=None)
    fee_survivors = [e for e in evaluations if e.result.total_net_pnl > 0]
    best_fee_survivor = max(fee_survivors, key=lambda e: e.result.quote_per_day, default=None)
    best_target = min(evaluations, key=lambda e: e.target_distance, default=None)
    status, reason = _candidate_space_status(evaluations)
    if selected_pool:
        selected_result = _aggregate_pool_result(split.blindtest_candles, selected_pool, start_capital, filters)
        selected_setups = [_report._candidate_summary(e) for e in selected_pool]
        selection_reason = "training_only_top_n_trade_allowed_candidate_pool_executed_on_blindtest"
    else:
        selected_result = _report._empty_simulation_result(_report._diagnostic_placeholder_candidate(stake_quote_amount), start_capital)
        selected_setups = []
        selection_reason = "diagnostic_only_no_trade_allowed_candidate"
    daily = _report._daily_pnls(selected_result.trades)
    best_training_quote_per_day = max((e.result.quote_per_day for e in evaluations), default=0.0)
    target_ratio = selected_result.quote_per_day / _report.TARGET_QUOTE_PER_DAY
    target_status = "blindtest_target_reached" if selected_pool and selected_result.quote_per_day >= _report.TARGET_QUOTE_PER_DAY else "target_not_reached"
    if progress_callback is not None:
        progress_callback({"phase": "activity_first_router_diagnostics", "progress_pct": 88.7, "detail": "ETHUSDC-Regime-Diagnose wird erstellt"})
    eth_diagnostics = _report._eth_regime_diagnostics(split.training_candles)
    rejection_summary = {
        "router_name": "activity_first_router",
        "candidate_space_status": status,
        "candidate_space_reason": reason,
        "rejection_counts": _report._rejection_counts(evaluations),
        "search_pass_summary": _search_pass_summary(evaluations),
        "eth_regime_diagnostics": eth_diagnostics,
        "best_activity_candidate": _report._candidate_summary(best_activity) if best_activity else None,
        "best_edge_candidate": _report._candidate_summary(best_edge) if best_edge else None,
        "best_balanced_candidate": _report._candidate_summary(best_balanced) if best_balanced else None,
        "best_fee_survivor_candidate": _report._candidate_summary(best_fee_survivor) if best_fee_survivor else None,
        "best_target_candidate": _report._candidate_summary(best_target) if best_target else None,
        "selected_trade_allowed_candidates": selected_setups,
        "selected_trade_allowed_candidate": selected_setups[0] if selected_setups else None,
        "selected_pool_size": len(selected_pool),
        "target_feasibility_status": target_status,
        "best_training_quote_per_day": best_training_quote_per_day,
        "diagnostic_only": not selected_pool,
        "selection_reason": selection_reason,
    }
    return _report.ActivityFirstRouterReport(
        run_id,
        "activity_first_router",
        _report.CONFIG.symbol,
        _report.CONFIG.quote_asset,
        start_capital,
        stake_quote_amount,
        profile,
        split.training_start,
        split.training_end,
        split.blindtest_start,
        split.blindtest_end,
        status,
        reason,
        len(candidates),
        len(evaluations),
        len(allowed),
        len(selected_pool),
        sum(1 for e in evaluations if e.rejection_reason),
        selected_setups,
        rejection_summary,
        _report._candidate_summary(best_activity) if best_activity else None,
        _report._candidate_summary(best_edge) if best_edge else None,
        _report._candidate_summary(best_balanced) if best_balanced else None,
        _report._candidate_summary(best_fee_survivor) if best_fee_survivor else None,
        _report._candidate_summary(best_target) if best_target else None,
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
        sum(1 for v in daily.values() if v > 0),
        sum(1 for v in daily.values() if v < 0),
        sum(1 for v in daily.values() if v == 0),
        max(daily.values(), default=0.0),
        min(daily.values(), default=0.0),
        best_training_quote_per_day,
        _report.TARGET_QUOTE_PER_DAY,
        target_ratio,
        target_status,
        {
            "run_type": "unknown",
            "smoke_test_not_performance_proof": False,
            "live_release_allowed": False,
            "legacy_cluster_router_used": False,
            "diagnostic_only": not selected_pool,
            "trade_allowed": bool(selected_pool),
            "blindtest_strategy_executed": bool(selected_pool),
            "selection_policy": "training_only_top_n_trade_allowed_candidate_pool_same_backtest_contract",
            "selection_reason": selection_reason,
            "exchange_info_filters_used": filters is not None,
            "candidate_generation_version": "activity_first_v6_multi_candidate_pool",
            "eth_specific_strategy_scope": True,
            "historical_news_labels_used": False,
            "historical_orderbook_used": False,
            "fast_rolling_metrics_used": True,
            "scaled_eth_activity_gate_used": True,
            "eth_selection_penalty_used": True,
            "multi_candidate_pool_used": True,
            "selected_pool_size": len(selected_pool),
            "selected_pool_max_size_rule": "max(2, min(25, ceil(training_days / 14)))",
        },
        [asdict(t) for t in selected_result.trades[:250]],
    )


_report._candidate_rejection = _candidate_rejection
_report._evaluate_training_candidates = _evaluate_training_candidates
_report._search_pass_summary = _search_pass_summary
_report._candidate_space_status = _candidate_space_status
_report.build_activity_first_router_report = build_activity_first_router_report
_report._scaled_eth_activity_gate_used = True
_report._eth_selection_penalty_used = True
_report._multi_candidate_pool_used = True
