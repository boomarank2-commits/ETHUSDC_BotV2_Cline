from __future__ import annotations

import pytest

from src.research.brh_btc_risk_on_frozen_blindtest import (
    _decision_summary,
    _gatekeeper_candidate,
)


def _gatekeeper_report(variant_id: str = "brh_btc_risk_on_72h") -> dict:
    return {
        "status": "new_training_only_candidate_found",
        "decision_summary": {"research_blindtest_conditionally_allowed": True},
        "best_training_only_variant_after_robustness_gatekeeper": {
            "variant_id": variant_id,
            "already_blindtested_in_v1": False,
            "aggregate": {},
        },
    }


def test_gatekeeper_candidate_requires_exact_authorized_variant() -> None:
    candidate = _gatekeeper_candidate(_gatekeeper_report(), "brh_btc_risk_on_72h")

    assert candidate["variant_id"] == "brh_btc_risk_on_72h"

    with pytest.raises(ValueError, match="different candidate"):
        _gatekeeper_candidate(_gatekeeper_report("other_variant"), "brh_btc_risk_on_72h")


def test_gatekeeper_candidate_blocks_already_blindtested_variant() -> None:
    report = _gatekeeper_report()
    report["best_training_only_variant_after_robustness_gatekeeper"][
        "already_blindtested_in_v1"
    ] = True

    with pytest.raises(ValueError, match="already blindtested"):
        _gatekeeper_candidate(report, "brh_btc_risk_on_72h")


def test_decision_summary_never_directly_allows_ui_full_backtest() -> None:
    summary = _decision_summary(
        {
            "pnl_usdc": 10.0,
            "usdc_per_day": 0.1,
            "trades": 20,
            "median_trade_net_pnl": 0.2,
        },
        {
            "leave_two_out_profit_factor": 1.2,
            "top_trade_pnl_share": {"2": 0.4},
        },
        strategy_minus_buy_hold_usdc_per_day=0.05,
    )

    assert summary["positive_blindtest_edge"] is True
    assert summary["robust_blindtest_edge"] is True
    assert summary["router_integration_allowed_now"] is True
    assert summary["ui_full_backtest_allowed_now"] is False
