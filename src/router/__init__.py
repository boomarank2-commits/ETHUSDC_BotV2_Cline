"""Router package patches.

Keep this package initializer small. It patches the activity-first router so
ETH-specific regime candidates are not rejected by a rigid one-trade-per-day
rule. The same scaled rule is applied for 1d/7d/14d/30d smoke and full runs;
only the training-window length changes the required evidence.
"""

from . import activity_first_router_report as _report


def _ceil_positive(value: float) -> int:
    whole = int(value)
    return whole if value <= whole else whole + 1


def _training_days_from_result(result: _report.ActivityFirstSimulationResult) -> float:
    if result.trade_count <= 0 or result.trades_per_day <= 0:
        return 0.0
    return max(1.0, result.trade_count / result.trades_per_day)


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


def _search_pass_summary(evaluations: list[_report._TrainingEvaluation]) -> list[dict]:
    result = []
    for search_pass in sorted({e.candidate.search_pass for e in evaluations}):
        rows = [e for e in evaluations if e.candidate.search_pass == search_pass]
        best = max(rows, key=lambda e: e.result.quote_per_day, default=None)
        result.append(
            {
                "pass_name": search_pass,
                "candidates_generated": len(rows),
                "setup_tests_run": len(rows),
                "candidates_positive_net": sum(1 for e in rows if e.result.total_net_pnl > 0),
                "candidates_active_enough": sum(1 for e in rows if _passes_activity_gate(e.result)),
                "candidates_trade_allowed": sum(1 for e in rows if e.trade_allowed),
                "best_candidate": _report._candidate_summary(best) if best else None,
            }
        )
    return result


def _candidate_space_status(evaluations: list[_report._TrainingEvaluation]) -> tuple[str, str]:
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


_report._candidate_rejection = _candidate_rejection
_report._search_pass_summary = _search_pass_summary
_report._candidate_space_status = _candidate_space_status
_report._scaled_eth_activity_gate_used = True
