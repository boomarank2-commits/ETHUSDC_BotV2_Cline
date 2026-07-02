from __future__ import annotations

import pytest

from src.research.erem_frozen_blindtest import _decision_summary, _gatekeeper_candidate


def _source_report(status: str = "erem_training_edge_found") -> dict:
    return {
        "status": status,
        "decision_summary": {"erem_frozen_blindtest_conditionally_allowed": True},
        "best_training_only_variant": {
            "variant_id": "erem_btc_drawdown_q35_or_ema_below0",
            "aggregate": {},
        },
    }


def test_gatekeeper_candidate_requires_training_edge_status() -> None:
    variant = _gatekeeper_candidate(_source_report())

    assert variant.variant_id == "erem_btc_drawdown_q35_or_ema_below0"

    with pytest.raises(ValueError, match="did not find"):
        _gatekeeper_candidate(_source_report("no_erem_training_edge"))


def test_decision_summary_requires_return_drawdown_concentration_and_ratio() -> None:
    decision = _decision_summary(
        {
            "erem_pnl_usdc": 20.0,
            "buy_hold_pnl_usdc": 10.0,
            "erem_maxdd_usdc": 5.0,
            "buy_hold_maxdd_usdc": 10.0,
            "top1_avoided_block_share": 0.30,
        },
        config=type("Config", (), {"max_top1_avoided_block_share": 0.50})(),
    )

    assert decision["robust_blindtest_edge"] is True
    assert decision["router_integration_allowed_now"] is True
    assert decision["ui_full_backtest_allowed_now"] is False


def test_decision_summary_blocks_concentrated_avoided_loss() -> None:
    decision = _decision_summary(
        {
            "erem_pnl_usdc": 20.0,
            "buy_hold_pnl_usdc": 10.0,
            "erem_maxdd_usdc": 5.0,
            "buy_hold_maxdd_usdc": 10.0,
            "top1_avoided_block_share": 0.75,
        },
        config=type("Config", (), {"max_top1_avoided_block_share": 0.50})(),
    )

    assert decision["robust_blindtest_edge"] is False
    assert decision["router_integration_allowed_now"] is False
