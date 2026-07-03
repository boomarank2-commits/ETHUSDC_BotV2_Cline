from __future__ import annotations

import pandas as pd

import src.research.erem_postmortem_cycle_scan as postmortem
from src.research.erem_exposure_edge_check import EremThresholds, EremVariant
from src.research.erem_postmortem_cycle_scan import (
    EremPostmortemConfig,
    fixed_erem_variant,
    flat_period_attribution,
    run_erem_postmortem_cycle_scan,
)


def _execution_frame() -> pd.DataFrame:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=60, freq="h", tz="UTC")
    opens = [
        100.0,
        98.0,
        96.0,
        95.0,
        97.0,
        100.0,
        104.0,
        108.0,
        106.0,
        102.0,
    ]
    while len(opens) < len(index):
        opens.append(opens[-1] * (1.003 if len(opens) % 7 else 0.992))
    return pd.DataFrame(
        {
            "open": opens,
            "close": opens,
            "brh_signal_update_bar": [True] * len(index),
            "btc_4h_drawdown_from_20d_high": [-0.01] * len(index),
            "btc_4h_close_vs_ema20": [0.01] * len(index),
        },
        index=index,
    )


def test_flat_period_attribution_splits_avoided_losses_and_missed_gains(
    monkeypatch,
) -> None:
    execution = _execution_frame().iloc[:8].copy()
    execution["open"] = [100.0, 96.0, 90.0, 95.0, 100.0, 110.0, 108.0, 107.0]
    index = list(execution.index)

    monkeypatch.setattr(
        postmortem,
        "_desired_exposure_changes",
        lambda *_args, **_kwargs: {index[2]: True, index[3]: False, index[5]: True},
    )

    attribution = flat_period_attribution(
        execution,
        EremVariant("test", 0.35),
        EremThresholds(-0.02),
        index[0],
        index[-1],
        100.0,
    )

    assert attribution["flat_block_count"] == 2
    assert attribution["avoided_losses_usdc"] > 0
    assert attribution["missed_gains_usdc"] > 0


def test_erem_postmortem_cycle_scan_is_research_only(monkeypatch, tmp_path) -> None:
    execution = _execution_frame()
    training_start = execution.index[0]
    blindtest_start = execution.index[30]
    blindtest_end = execution.index[-1]

    monkeypatch.setattr(
        postmortem,
        "_load_full_execution",
        lambda: (execution, training_start, blindtest_start, blindtest_end),
    )

    report = run_erem_postmortem_cycle_scan(
        EremPostmortemConfig(
            output_dir=tmp_path,
            phase_lookback_hours=2,
        )
    )

    assert report["research_only"] is True
    assert report["runs_ui_backtest"] is False
    assert report["runs_new_blindtest"] is False
    assert report["searches_variants"] is False
    assert report["candidate_variant"]["variant_id"] == fixed_erem_variant().variant_id
    assert "cycle_metrics" in report
    assert "full_period_switch_cost_attribution" in report
    assert "blindtest_switch_cost_attribution" in report
    assert "recommended_next_step" in report["decision_summary"]
    assert (tmp_path / "erem_postmortem_cycle_scan_report.json").is_file()
