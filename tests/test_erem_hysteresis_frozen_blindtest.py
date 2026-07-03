from __future__ import annotations

import pytest

from src.research.erem_hysteresis_frozen_blindtest import (
    _decision_summary,
    _overlay_from_report,
)


def _source_report(status: str = "erem_hysteresis_training_candidate_found") -> dict:
    return {
        "status": status,
        "decision_summary": {"frozen_research_blindtest_conditionally_allowed": True},
        "best_training_only_variant": {
            "overlay": {
                "variant_id": "erem_minhold_exp48_flat12",
                "min_exposed_hours": 48,
                "min_flat_hours": 12,
            },
            "aggregate": {},
        },
    }


def test_overlay_from_report_requires_training_candidate() -> None:
    overlay = _overlay_from_report(_source_report())

    assert overlay.variant_id == "erem_minhold_exp48_flat12"
    assert overlay.min_exposed_hours == 48
    assert overlay.min_flat_hours == 12

    with pytest.raises(ValueError, match="did not find"):
        _overlay_from_report(_source_report("no_erem_hysteresis_training_candidate"))


def test_decision_summary_requires_positive_base_improvement_and_concentration() -> None:
    decision = _decision_summary(
        {
            "erem_pnl_usdc": 10.0,
            "switch_count": 40,
            "top2_avoided_block_share": 0.25,
        },
        {
            "erem_pnl_usdc": -2.0,
            "switch_count": 100,
        },
        config=type("Config", (), {"max_top2_avoided_block_share": 0.65})(),
    )

    assert decision["robust_frozen_edge"] is True
    assert decision["router_integration_allowed_now"] is True
    assert decision["ui_full_backtest_allowed_now"] is False


def test_decision_summary_blocks_negative_or_concentrated_result() -> None:
    decision = _decision_summary(
        {
            "erem_pnl_usdc": -1.0,
            "switch_count": 40,
            "top2_avoided_block_share": 0.80,
        },
        {
            "erem_pnl_usdc": -2.0,
            "switch_count": 100,
        },
        config=type("Config", (), {"max_top2_avoided_block_share": 0.65})(),
    )

    assert decision["robust_frozen_edge"] is False
    assert decision["router_integration_allowed_now"] is False
