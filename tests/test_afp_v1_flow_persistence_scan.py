from __future__ import annotations

import pandas as pd
import pytest

from src.research.afp_v1_flow_persistence_scan import (
    AfpConfig,
    AfpThresholds,
    AfpVariant,
    afp_signal_mask,
    audit_agg_trade_completeness,
    simulate_afp_variant,
)
from src.research.erh_v1 import ErhConfig


def _base_frame(rows: int = 12) -> pd.DataFrame:
    index = pd.date_range("2026-01-01T00:00:00Z", periods=rows, freq="min", tz="UTC")
    return pd.DataFrame(
        {
            "open": [100.0 + offset for offset in range(rows)],
            "high": [101.0 + offset for offset in range(rows)],
            "low": [99.5 + offset for offset in range(rows)],
            "close": [100.5 + offset for offset in range(rows)],
            "trade_count": [20] * rows,
            "agg_trade_count": [10.0] * rows,
            "raw_trade_count": [15.0] * rows,
            "agg_quote_volume": [1000.0] * rows,
            "agg_taker_buy_quote_volume": [600.0] * rows,
            "agg_taker_sell_quote_volume": [400.0] * rows,
            "vwap": [100.0 + offset for offset in range(rows)],
            "max_agg_trade_quote": [100.0] * rows,
            "agg_zero_trade_filled": [False] * rows,
            "agg_no_signal_zone": [False] * rows,
            "persistence_ofi_30m": [0.01] * rows,
            "consistency_30m": [0.40] * rows,
            "raw_to_agg_ratio_30m_mean": [1.5] * rows,
            "max_agg_trade_quote_z60": [0.0] * rows,
            "close_vs_vwap_30m": [0.001] * rows,
        },
        index=index,
    )


def test_audit_agg_trade_completeness_reports_missing_ranges() -> None:
    frame = _base_frame(5)
    frame.loc[frame.index[1:3], "agg_trade_count"] = pd.NA

    audit = audit_agg_trade_completeness(frame)

    assert audit["total_minutes"] == 5
    assert audit["missing_minutes"] == 2
    assert audit["longest_missing_gap_minutes"] == 2
    assert audit["first_missing_ranges"][0]["start"] == frame.index[1].isoformat()
    assert audit["first_missing_ranges"][0]["end"] == frame.index[2].isoformat()


def test_afp_signal_mask_requires_persistence_breadth_and_whale_filter() -> None:
    frame = _base_frame(3)
    frame.loc[frame.index[1], "persistence_ofi_30m"] = 0.08
    frame.loc[frame.index[1], "consistency_30m"] = 0.70

    mask = afp_signal_mask(
        frame,
        AfpVariant(
            "afp_test",
            window_minutes=30,
            ofi_persistence_min=0.06,
            consistency_min=0.60,
        ),
        AfpThresholds(breadth_min=1.0, whale_z_max=2.0),
    )

    assert mask.tolist() == [False, True, False]

    frame.loc[frame.index[1], "max_agg_trade_quote_z60"] = 3.0
    mask_after_whale_spike = afp_signal_mask(
        frame,
        AfpVariant(
            "afp_test",
            window_minutes=30,
            ofi_persistence_min=0.06,
            consistency_min=0.60,
        ),
        AfpThresholds(breadth_min=1.0, whale_z_max=2.0),
    )

    assert not bool(mask_after_whale_spike.loc[frame.index[1]])


def test_simulate_afp_variant_enters_next_open_and_exits_after_flow_reversal() -> None:
    frame = _base_frame(12)
    signal_time = frame.index[5]
    frame.loc[signal_time, "persistence_ofi_30m"] = 0.08
    frame.loc[signal_time, "consistency_30m"] = 0.70
    frame.loc[frame.index[7], "persistence_ofi_30m"] = -0.01
    zero_cost = ErhConfig(
        position_size_usdc=100.0,
        fee_rate_per_side=0.0,
        slippage_rate_per_side=0.0,
        extra_slippage_robustness_per_side=0.0,
    )

    trades = simulate_afp_variant(
        frame,
        AfpVariant(
            "afp_test",
            window_minutes=30,
            ofi_persistence_min=0.06,
            consistency_min=0.60,
        ),
        AfpThresholds(breadth_min=1.0, whale_z_max=2.0),
        AfpConfig(
            min_hold_minutes=2,
            max_hold_minutes=5,
            hard_sl=0.50,
            trading_cost_config=zero_cost,
        ),
        frame.index[0],
        frame.index[-1],
    )

    assert len(trades) == 1
    assert trades[0].signal_time == signal_time.isoformat()
    assert trades[0].entry_time == frame.index[6].isoformat()
    assert trades[0].exit_time == frame.index[8].isoformat()
    assert trades[0].exit_reason == "flow_reversal"
    assert trades[0].entry_price == pytest.approx(float(frame.iloc[6]["open"]))
    assert trades[0].exit_price == pytest.approx(float(frame.iloc[8]["open"]))
