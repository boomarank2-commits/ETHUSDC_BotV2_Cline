from __future__ import annotations

import pandas as pd

import src.research.erem_hysteresis_minhold_scan as hysteresis
from src.research.erem_exposure_edge_check import EremThresholds, EremVariant
from src.research.erem_hysteresis_minhold_scan import (
    EremHysteresisConfig,
    EremHysteresisVariant,
    hysteresis_exposure_changes,
    run_erem_hysteresis_minhold_scan,
)


def _execution_frame(hours: int = 80) -> pd.DataFrame:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=hours, freq="h", tz="UTC")
    opens = [100.0]
    for offset in range(1, hours):
        opens.append(opens[-1] * (1.004 if offset % 5 else 0.985))
    return pd.DataFrame(
        {
            "open": opens,
            "close": opens,
            "brh_signal_update_bar": [True] * hours,
            "btc_4h_drawdown_from_20d_high": [-0.01] * hours,
            "btc_4h_close_vs_ema20": [0.01] * hours,
        },
        index=index,
    )


def test_hysteresis_exposure_changes_filters_fast_flips(monkeypatch) -> None:
    execution = _execution_frame(12)
    index = list(execution.index)
    raw_changes = {
        index[0]: True,
        index[2]: False,
        index[3]: True,
        index[7]: False,
        index[10]: True,
    }
    monkeypatch.setattr(
        hysteresis,
        "_desired_exposure_changes",
        lambda *_args, **_kwargs: raw_changes,
    )

    filtered = hysteresis_exposure_changes(
        execution,
        index[0],
        index[-1],
        EremVariant("base", 0.35, use_btc_ema_filter=True),
        EremThresholds(-0.02),
        EremHysteresisVariant("overlay", min_exposed_hours=4, min_flat_hours=4),
    )

    assert filtered == {index[0]: True, index[7]: False}


def test_erem_hysteresis_minhold_scan_is_training_only(monkeypatch, tmp_path) -> None:
    execution = _execution_frame(160)
    training_start = execution.index[0]
    blindtest_start = execution.index[120]
    blindtest_end = execution.index[-1]

    monkeypatch.setattr(
        hysteresis,
        "_load_full_execution",
        lambda: (execution, training_start, blindtest_start, blindtest_end),
    )
    monkeypatch.setattr(
        hysteresis,
        "build_walkforward_windows",
        lambda *_args, **_kwargs: [
            {
                "train_end": execution.index[40].isoformat(),
                "validation_start": execution.index[50].isoformat(),
                "validation_end": execution.index[80].isoformat(),
            },
            {
                "train_end": execution.index[80].isoformat(),
                "validation_start": execution.index[90].isoformat(),
                "validation_end": execution.index[119].isoformat(),
            },
        ],
    )

    report = run_erem_hysteresis_minhold_scan(
        EremHysteresisConfig(
            output_dir=tmp_path,
            min_positive_folds=1,
            min_beats_base_folds=1,
            max_top2_avoided_block_share=1.0,
        )
    )

    assert report["research_only"] is True
    assert report["training_only"] is True
    assert report["runs_new_blindtest"] is False
    assert report["runs_ui_backtest"] is False
    assert report["uses_blindtest_for_selection"] is False
    assert report["variant_count"] == 16
    assert (tmp_path / "erem_hysteresis_minhold_scan_report.json").is_file()
