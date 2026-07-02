"""Training-only AFP-v1 aggregate-flow persistence scan.

AFP-v1 = Aggregate Flow Persistence Long.

This research-only module tests the next Arena.ai recommendation after VEC-v1:
use the real ETHUSDC aggTrade minute features for a frequency-first, persistent
buy-flow hypothesis instead of another rare climax/reclaim setup.

The scan has three deliberate stop layers:

1. aggTrade completeness audit over the full 730d/365d local window.
2. training-only sanity check: does higher 5m buy-flow persistence predict
   better 15m forward returns after costs inside walkforward folds?
3. only if sanity passes, run a tiny fixed variant grid in training only.

No blindtest is executed here, no router integration is performed and no UI
backtest is started.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import REPORTS_DIR
from src.data.agg_trade_data_ensure import AGG_TRADE_FEATURE_DIR
from src.research.brh_v1 import _to_jsonable
from src.research.brh_v1_diagnostics import concentration_metrics
from src.research.erh_v1 import (
    ErhConfig,
    _max_drawdown,
    _net_return,
    _profit_factor,
    build_walkforward_windows,
    latest_train_blind_window,
    load_1m_candles,
)

AFP_V1_FLOW_PERSISTENCE_VERSION = "afp_l_v1_flow_persistence_scan_20260702"


@dataclass(frozen=True)
class AfpVariant:
    """One fixed AFP-v1 persistence variant."""

    variant_id: str
    window_minutes: int
    ofi_persistence_min: float
    consistency_min: float


@dataclass(frozen=True)
class AfpThresholds:
    """Training-only thresholds for one AFP fold."""

    breadth_min: float
    whale_z_max: float


@dataclass(frozen=True)
class AfpTrade:
    """One simulated AFP validation trade."""

    variant_id: str
    fold_index: str
    signal_time: str
    entry_time: str
    exit_time: str
    exit_reason: str
    hold_minutes: int
    entry_price: float
    exit_price: float
    net_return: float
    net_pnl_usdc: float
    fees_and_slippage_ret: float
    ofi_persistence_at_signal: float
    consistency_at_signal: float
    raw_to_agg_ratio_at_signal: float
    whale_z_at_signal: float
    close_vs_vwap_at_signal: float


@dataclass(frozen=True)
class AfpConfig:
    """Configuration for AFP-v1 training-only scan."""

    output_dir: Path = REPORTS_DIR / "research" / "afp_v1_flow_persistence_scan"
    position_size_usdc: float = 100.0
    val_days: int = 120
    purge_days: int = 7
    fold_count: int = 6
    max_missing_ratio: float = 0.01
    max_contiguous_missing_minutes: int = 360
    sanity_forward_minutes: int = 15
    min_sanity_passing_folds: int = 5
    target_min_training_signals: int = 60
    target_max_training_signals: int = 150
    min_validation_trades: int = 60
    min_positive_folds: int = 5
    min_profit_factor: float = 1.30
    min_median_trade_pnl_usdc: float = 0.03
    min_leave_two_out_profit_factor: float = 1.20
    max_top2_pnl_share: float = 0.30
    min_cost_robust_profit_factor: float = 1.15
    min_worst_fold_pnl_usdc: float = -10.0
    min_hold_minutes: int = 30
    max_hold_minutes: int = 360
    hard_sl: float = 0.012
    flow_reversal_threshold: float = 0.0
    extra_cost_robustness_slippage_per_side: float = 0.0002
    trading_cost_config: ErhConfig = field(
        default_factory=lambda: ErhConfig(position_size_usdc=100.0)
    )


def build_afp_variants() -> list[AfpVariant]:
    """Return the fixed frequency-first AFP-v1 scan grid."""
    variants: list[AfpVariant] = []
    for window_minutes in (30, 45):
        for ofi_persistence_min in (0.06, 0.10):
            for consistency_min in (0.60, 0.70):
                variants.append(
                    AfpVariant(
                        variant_id=(
                            f"afp_w{window_minutes}"
                            f"_ofi{int(ofi_persistence_min * 100)}"
                            f"_cons{int(consistency_min * 100)}"
                        ),
                        window_minutes=window_minutes,
                        ofi_persistence_min=ofi_persistence_min,
                        consistency_min=consistency_min,
                    )
                )
    return variants


def _agg_trade_feature_paths(start: pd.Timestamp, end: pd.Timestamp) -> list[Path]:
    if not AGG_TRADE_FEATURE_DIR.exists():
        return []
    paths: list[Path] = []
    for path in sorted(AGG_TRADE_FEATURE_DIR.glob("*.csv")):
        stem = path.stem
        if len(stem) == 7:
            period_start = pd.Timestamp(f"{stem}-01T00:00:00Z")
            period_end = period_start + pd.offsets.MonthBegin(1)
        elif len(stem) == 10:
            period_start = pd.Timestamp(f"{stem}T00:00:00Z")
            period_end = period_start + pd.Timedelta(days=1)
        else:
            continue
        if period_end > start and period_start <= end:
            paths.append(path)
    return paths


def load_agg_trade_minutes(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Load local ETHUSDC aggTrade minute features for the requested interval."""
    paths = _agg_trade_feature_paths(start, end)
    if not paths:
        msg = f"missing ETHUSDC aggTrade minute features in {AGG_TRADE_FEATURE_DIR}"
        raise FileNotFoundError(msg)
    usecols = [
        "open_time",
        "agg_trade_count",
        "raw_trade_count",
        "quote_volume",
        "taker_buy_quote_volume",
        "taker_sell_quote_volume",
        "vwap",
        "max_agg_trade_quote",
    ]
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_csv(path, usecols=usecols)
        frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
        frame = frame.loc[
            (frame["open_time"] >= start) & (frame["open_time"] <= end)
        ]
        if not frame.empty:
            frames.append(frame)
    if not frames:
        msg = f"no ETHUSDC aggTrade rows between {start} and {end}"
        raise ValueError(msg)
    result = pd.concat(frames, ignore_index=True)
    result = result.sort_values("open_time").drop_duplicates("open_time", keep="last")
    numeric_columns = [column for column in result.columns if column != "open_time"]
    result[numeric_columns] = result[numeric_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )
    return result.set_index("open_time")


def _missing_ranges(missing_mask: pd.Series) -> list[dict[str, Any]]:
    ranges: list[dict[str, Any]] = []
    current_start: pd.Timestamp | None = None
    current_end: pd.Timestamp | None = None
    current_count = 0
    for timestamp, is_missing in missing_mask.items():
        if bool(is_missing):
            if current_start is None:
                current_start = timestamp
                current_count = 0
            current_end = timestamp
            current_count += 1
            continue
        if current_start is not None and current_end is not None:
            ranges.append(
                {
                    "start": current_start.isoformat(),
                    "end": current_end.isoformat(),
                    "minutes": current_count,
                }
            )
        current_start = None
        current_end = None
        current_count = 0
    if current_start is not None and current_end is not None:
        ranges.append(
            {
                "start": current_start.isoformat(),
                "end": current_end.isoformat(),
                "minutes": current_count,
            }
        )
    return ranges


def audit_agg_trade_completeness(frame: pd.DataFrame) -> dict[str, Any]:
    """Return completeness diagnostics for the joined ETH/aggTrade frame."""
    required_columns = [
        "agg_trade_count",
        "raw_trade_count",
        "agg_quote_volume",
        "agg_taker_buy_quote_volume",
        "agg_taker_sell_quote_volume",
        "vwap",
        "max_agg_trade_quote",
    ]
    missing_mask = frame[required_columns].isna().any(axis=1)
    zero_trade_filled = frame.get(
        "agg_zero_trade_filled",
        pd.Series(False, index=frame.index),
    ).fillna(False)
    ranges = _missing_ranges(missing_mask)
    total_minutes = int(len(frame))
    missing_minutes = int(missing_mask.sum())
    zero_trade_minutes = int(zero_trade_filled.sum())
    completeness_ratio = (
        (total_minutes - missing_minutes) / total_minutes
        if total_minutes > 0
        else 0.0
    )
    longest_gap = max((item["minutes"] for item in ranges), default=0)
    return {
        "total_minutes": total_minutes,
        "available_minutes": total_minutes - missing_minutes,
        "missing_minutes": missing_minutes,
        "zero_trade_minutes_without_agg_rows": zero_trade_minutes,
        "completeness_ratio": completeness_ratio,
        "missing_ratio": 1.0 - completeness_ratio,
        "longest_missing_gap_minutes": int(longest_gap),
        "missing_range_count": len(ranges),
        "first_missing_ranges": ranges[:20],
    }


def build_afp_feature_frame(
    eth_1m: pd.DataFrame,
    agg_minutes: pd.DataFrame,
) -> pd.DataFrame:
    """Join ETHUSDC 1m execution candles with real aggTrade minute features."""
    agg = agg_minutes.rename(
        columns={
            "quote_volume": "agg_quote_volume",
            "taker_buy_quote_volume": "agg_taker_buy_quote_volume",
            "taker_sell_quote_volume": "agg_taker_sell_quote_volume",
        }
    )
    frame = eth_1m.join(agg, how="left")
    agg_columns = [
        "agg_trade_count",
        "raw_trade_count",
        "agg_quote_volume",
        "agg_taker_buy_quote_volume",
        "agg_taker_sell_quote_volume",
        "vwap",
        "max_agg_trade_quote",
    ]
    raw_missing_mask = frame[agg_columns].isna().any(axis=1)
    zero_trade_missing = raw_missing_mask & (frame["trade_count"].fillna(0) == 0)
    zero_fill_columns = [
        "agg_trade_count",
        "raw_trade_count",
        "agg_quote_volume",
        "agg_taker_buy_quote_volume",
        "agg_taker_sell_quote_volume",
        "max_agg_trade_quote",
    ]
    frame.loc[zero_trade_missing, zero_fill_columns] = 0.0
    frame.loc[zero_trade_missing, "vwap"] = frame.loc[zero_trade_missing, "close"]
    frame["agg_zero_trade_filled"] = zero_trade_missing
    total_taker = (
        frame["agg_taker_buy_quote_volume"] + frame["agg_taker_sell_quote_volume"]
    )
    frame["agg_buy_share_1m"] = np.where(
        total_taker > 0,
        frame["agg_taker_buy_quote_volume"] / total_taker,
        0.5,
    )
    frame["agg_ofi_1m"] = np.where(
        total_taker > 0,
        (frame["agg_taker_buy_quote_volume"] - frame["agg_taker_sell_quote_volume"])
        / total_taker,
        0.0,
    )
    frame["raw_to_agg_ratio_1m"] = np.where(
        frame["agg_trade_count"] > 0,
        frame["raw_trade_count"] / frame["agg_trade_count"],
        0.0,
    )
    whale_mean = frame["max_agg_trade_quote"].rolling(60).mean().shift(1)
    whale_std = frame["max_agg_trade_quote"].rolling(60).std(ddof=0).shift(1)
    frame["max_agg_trade_quote_z60"] = np.where(
        whale_std > 0,
        (frame["max_agg_trade_quote"] - whale_mean) / whale_std,
        np.nan,
    )
    for window in (5, 15, 30, 45):
        frame[f"persistence_ofi_{window}m"] = (
            frame["agg_ofi_1m"].rolling(window).mean()
        )
        frame[f"consistency_{window}m"] = (
            (frame["agg_ofi_1m"] > 0).astype(float).rolling(window).mean()
        )
        frame[f"raw_to_agg_ratio_{window}m_mean"] = (
            frame["raw_to_agg_ratio_1m"].rolling(window).mean()
        )
        weighted_vwap = (frame["vwap"] * frame["agg_quote_volume"]).rolling(
            window
        ).sum()
        quote_sum = frame["agg_quote_volume"].rolling(window).sum()
        frame[f"vwap_{window}m"] = np.where(
            quote_sum > 0,
            weighted_vwap / quote_sum,
            np.nan,
        )
        frame[f"close_vs_vwap_{window}m"] = np.where(
            frame[f"vwap_{window}m"] > 0,
            frame["close"] / frame[f"vwap_{window}m"] - 1.0,
            np.nan,
        )
    frame["agg_no_signal_zone"] = frame[agg_columns].isna().any(axis=1)
    return frame


def _net_return_from_prices(
    entry_price: float,
    exit_price: float,
    config: AfpConfig,
    extra_slippage_per_side: float = 0.0,
) -> tuple[float, float]:
    return _net_return(
        entry_price,
        exit_price,
        config.trading_cost_config,
        extra_slippage_per_side,
    )


def _forward_return_after_cost(
    frame: pd.DataFrame,
    signal_pos: int,
    horizon_minutes: int,
    config: AfpConfig,
) -> float | None:
    entry_pos = signal_pos + 1
    exit_pos = entry_pos + horizon_minutes
    if exit_pos >= len(frame):
        return None
    entry_price = float(frame.iloc[entry_pos]["open"])
    exit_price = float(frame.iloc[exit_pos]["open"])
    net_return, _ = _net_return_from_prices(entry_price, exit_price, config)
    return net_return


def _vector_net_returns(
    entry_prices: pd.Series,
    exit_prices: pd.Series,
    config: AfpConfig,
) -> pd.Series:
    slip = config.trading_cost_config.slippage_rate_per_side
    entry_exec = entry_prices * (1.0 + slip)
    exit_exec = exit_prices * (1.0 - slip)
    gross_return = exit_exec / entry_exec - 1.0
    fee_return = 2.0 * config.trading_cost_config.fee_rate_per_side
    return gross_return - fee_return


def _sanity_fold_report(
    frame: pd.DataFrame,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    validation_start: pd.Timestamp,
    validation_end: pd.Timestamp,
    config: AfpConfig,
) -> dict[str, Any]:
    train_values = (
        frame.loc[(frame.index >= train_start) & (frame.index <= train_end)]
        ["persistence_ofi_5m"]
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    validation = frame.loc[
        (frame.index >= validation_start) & (frame.index <= validation_end)
    ]
    if train_values.empty or validation.empty:
        return {
            "status": "insufficient_data",
            "quintile_means": {},
            "quintile_counts": {},
            "top_quintile_positive": False,
            "top_quintile_beats_bottom": False,
            "strict_monotonic": False,
            "fold_pass": False,
        }
    q20, q40, q60, q80 = train_values.quantile([0.2, 0.4, 0.6, 0.8]).tolist()
    bins = [-math.inf, q20, q40, q60, q80, math.inf]
    if len(set(round(value, 12) for value in bins[1:-1])) < 4:
        return {
            "status": "degenerate_quintile_edges",
            "quintile_edges": bins[1:-1],
            "quintile_means": {},
            "quintile_counts": {},
            "top_quintile_positive": False,
            "top_quintile_beats_bottom": False,
            "strict_monotonic": False,
            "fold_pass": False,
        }
    entry_open = frame["open"].shift(-1)
    exit_open = frame["open"].shift(-(1 + config.sanity_forward_minutes))
    net_return = _vector_net_returns(entry_open, exit_open, config)
    validation = validation.assign(
        forward_pnl_usdc=(
            net_return.loc[validation.index] * config.position_size_usdc
        )
    )
    validation = validation.loc[
        validation["persistence_ofi_5m"].notna()
        & ~validation["agg_no_signal_zone"].fillna(True).astype(bool)
        & validation["forward_pnl_usdc"].notna()
    ].copy()
    if validation.empty:
        return {
            "status": "no_validation_rows",
            "quintile_edges": bins[1:-1],
            "quintile_means": {},
            "quintile_counts": {},
            "top_quintile_positive": False,
            "top_quintile_beats_bottom": False,
            "strict_monotonic": False,
            "fold_pass": False,
        }
    validation["quintile"] = pd.cut(
        validation["persistence_ofi_5m"],
        bins=bins,
        labels=[1, 2, 3, 4, 5],
        include_lowest=True,
    ).astype("int64")
    result = validation[["quintile", "forward_pnl_usdc"]]
    grouped = result.groupby("quintile")["forward_pnl_usdc"]
    means = {str(key): float(value) for key, value in grouped.mean().items()}
    counts = {str(key): int(value) for key, value in grouped.count().items()}
    complete_means = [means.get(str(index)) for index in range(1, 6)]
    strict_monotonic = (
        all(value is not None for value in complete_means)
        and all(
            float(complete_means[index]) >= float(complete_means[index - 1])
            for index in range(1, 5)
        )
    )
    top = means.get("5")
    bottom = means.get("1")
    top_positive = top is not None and top > 0.0
    top_beats_bottom = (
        top is not None and bottom is not None and float(top) > float(bottom)
    )
    return {
        "status": "completed",
        "quintile_edges": bins[1:-1],
        "quintile_means": means,
        "quintile_counts": counts,
        "top_quintile_positive": top_positive,
        "top_quintile_beats_bottom": top_beats_bottom,
        "strict_monotonic": strict_monotonic,
        "fold_pass": bool(top_positive and top_beats_bottom and strict_monotonic),
    }


def run_afp_sanity_check(
    frame: pd.DataFrame,
    windows: list[dict[str, str]],
    training_start: pd.Timestamp,
    config: AfpConfig,
) -> dict[str, Any]:
    """Check whether buy-flow persistence has a basic training edge."""
    folds: list[dict[str, Any]] = []
    passing_folds = 0
    for window in windows:
        report = _sanity_fold_report(
            frame,
            training_start,
            pd.Timestamp(window["train_end"]),
            pd.Timestamp(window["validation_start"]),
            pd.Timestamp(window["validation_end"]),
            config,
        )
        report = {**window, **report}
        passing_folds += int(bool(report["fold_pass"]))
        folds.append(report)
    sanity_pass = passing_folds >= config.min_sanity_passing_folds
    return {
        "status": "sanity_passed" if sanity_pass else "sanity_failed",
        "passing_folds": passing_folds,
        "required_passing_folds": config.min_sanity_passing_folds,
        "sanity_pass": sanity_pass,
        "folds": folds,
    }


def calibrate_afp_thresholds(
    frame: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    variant: AfpVariant,
) -> AfpThresholds:
    """Calibrate fold thresholds without looking past the fold train interval."""
    training = frame.loc[(frame.index >= start) & (frame.index <= end)]
    breadth_column = f"raw_to_agg_ratio_{variant.window_minutes}m_mean"
    breadth_values = (
        training[breadth_column].replace([np.inf, -np.inf], np.nan).dropna()
    )
    breadth_min = float(breadth_values.median()) if not breadth_values.empty else math.inf
    return AfpThresholds(breadth_min=breadth_min, whale_z_max=2.0)


def afp_signal_mask(
    frame: pd.DataFrame,
    variant: AfpVariant,
    thresholds: AfpThresholds,
) -> pd.Series:
    """Return the AFP setup mask for closed decision minutes."""
    window = variant.window_minutes
    required = [
        f"persistence_ofi_{window}m",
        f"consistency_{window}m",
        f"raw_to_agg_ratio_{window}m_mean",
        "max_agg_trade_quote_z60",
        f"close_vs_vwap_{window}m",
    ]
    valid = ~frame["agg_no_signal_zone"].fillna(True).astype(bool)
    for column in required:
        valid &= frame[column].notna()
    return (
        valid
        & (frame[f"persistence_ofi_{window}m"] >= variant.ofi_persistence_min)
        & (frame[f"consistency_{window}m"] >= variant.consistency_min)
        & (frame[f"raw_to_agg_ratio_{window}m_mean"] >= thresholds.breadth_min)
        & (frame["max_agg_trade_quote_z60"] <= thresholds.whale_z_max)
        & (frame[f"close_vs_vwap_{window}m"] >= 0.0)
    )


def _trade_from_exit(
    frame: pd.DataFrame,
    variant: AfpVariant,
    fold_index: str,
    signal_pos: int,
    entry_pos: int,
    exit_pos: int,
    exit_price: float,
    exit_reason: str,
    config: AfpConfig,
    extra_slippage_per_side: float = 0.0,
) -> AfpTrade:
    row = frame.iloc[signal_pos]
    entry_time = frame.index[entry_pos]
    exit_time = frame.index[exit_pos]
    entry_price = float(frame.iloc[entry_pos]["open"])
    net_return, cost_ret = _net_return_from_prices(
        entry_price,
        exit_price,
        config,
        extra_slippage_per_side,
    )
    window = variant.window_minutes
    return AfpTrade(
        variant_id=variant.variant_id,
        fold_index=fold_index,
        signal_time=frame.index[signal_pos].isoformat(),
        entry_time=entry_time.isoformat(),
        exit_time=exit_time.isoformat(),
        exit_reason=exit_reason,
        hold_minutes=int((exit_time - entry_time).total_seconds() // 60),
        entry_price=entry_price,
        exit_price=exit_price,
        net_return=net_return,
        net_pnl_usdc=net_return * config.position_size_usdc,
        fees_and_slippage_ret=cost_ret,
        ofi_persistence_at_signal=float(row[f"persistence_ofi_{window}m"]),
        consistency_at_signal=float(row[f"consistency_{window}m"]),
        raw_to_agg_ratio_at_signal=float(row[f"raw_to_agg_ratio_{window}m_mean"]),
        whale_z_at_signal=float(row["max_agg_trade_quote_z60"]),
        close_vs_vwap_at_signal=float(row[f"close_vs_vwap_{window}m"]),
    )


def simulate_afp_variant(
    frame: pd.DataFrame,
    variant: AfpVariant,
    thresholds: AfpThresholds,
    config: AfpConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
    fold_index: str = "",
    extra_slippage_per_side: float = 0.0,
) -> list[AfpTrade]:
    """Simulate one AFP variant over a validation interval without overlap."""
    signal_mask = afp_signal_mask(frame, variant, thresholds)
    full_index = frame.index
    interval_mask = (frame.index >= start) & (frame.index <= end)
    signal_times = frame.index[interval_mask & signal_mask]
    trades: list[AfpTrade] = []
    next_entry_allowed_at = start
    for signal_time in signal_times:
        if signal_time < next_entry_allowed_at:
            continue
        signal_pos = int(full_index.get_loc(signal_time))
        entry_pos = signal_pos + 1
        max_exit_pos = entry_pos + config.max_hold_minutes
        if max_exit_pos >= len(frame):
            continue
        entry_time = full_index[entry_pos]
        if entry_time < start:
            continue
        entry_price = float(frame.iloc[entry_pos]["open"])
        stop_price = entry_price * (1.0 - config.hard_sl)
        exit_pos: int | None = None
        exit_price: float | None = None
        exit_reason = ""
        for position in range(entry_pos, max_exit_pos + 1):
            if full_index[position] > end:
                break
            if float(frame.iloc[position]["low"]) <= stop_price:
                exit_pos = position
                exit_price = stop_price
                exit_reason = "hard_stop"
                break
            held_minutes = position - entry_pos + 1
            if held_minutes < config.min_hold_minutes:
                continue
            flow_value = frame.iloc[position][
                f"persistence_ofi_{variant.window_minutes}m"
            ]
            flow_exit_pos = position + 1
            if (
                not pd.isna(flow_value)
                and float(flow_value) <= config.flow_reversal_threshold
                and flow_exit_pos < len(frame)
                and full_index[flow_exit_pos] <= end
            ):
                exit_pos = flow_exit_pos
                exit_price = float(frame.iloc[flow_exit_pos]["open"])
                exit_reason = "flow_reversal"
                break
        if exit_pos is None:
            if full_index[max_exit_pos] > end:
                continue
            exit_pos = max_exit_pos
            exit_price = float(frame.iloc[max_exit_pos]["open"])
            exit_reason = "max_hold"
        trades.append(
            _trade_from_exit(
                frame,
                variant,
                fold_index,
                signal_pos,
                entry_pos,
                exit_pos,
                float(exit_price),
                exit_reason,
                config,
                extra_slippage_per_side,
            )
        )
        next_entry_allowed_at = full_index[exit_pos]
    return trades


def _remove_largest_winners(pnls: list[float], count: int) -> list[float]:
    positive_indices = [
        index
        for index, value in sorted(
            enumerate(pnls),
            key=lambda item: item[1],
            reverse=True,
        )
        if value > 0
    ][:count]
    remove = set(positive_indices)
    return [value for index, value in enumerate(pnls) if index not in remove]


def summarize_afp_trades(
    trades: list[AfpTrade],
    start: pd.Timestamp,
    end: pd.Timestamp,
    config: AfpConfig,
    extra_slippage_per_side: float = 0.0,
) -> dict[str, Any]:
    """Summarize AFP validation trades."""
    pnls: list[float] = []
    for trade in trades:
        net_return, _ = _net_return_from_prices(
            trade.entry_price,
            trade.exit_price,
            config,
            extra_slippage_per_side,
        )
        pnls.append(net_return * config.position_size_usdc)
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    total_pnl = float(sum(pnls))
    max_dd, max_dd_pct = _max_drawdown(pnls, config.position_size_usdc)
    trade_rows = [asdict(trade) for trade in trades]
    if extra_slippage_per_side:
        for row, pnl in zip(trade_rows, pnls, strict=True):
            row["net_pnl_usdc"] = pnl
    concentration = concentration_metrics(pd.DataFrame(trade_rows))
    return {
        "trades": len(trades),
        "pnl_usdc": total_pnl,
        "usdc_per_day": total_pnl / days,
        "profit_factor": _to_jsonable(_profit_factor(pnls)),
        "median_trade_pnl_usdc": float(np.median(pnls)) if pnls else None,
        "max_drawdown_usdc": max_dd,
        "max_drawdown_pct": max_dd_pct,
        "positive_trade_count": sum(1 for pnl in pnls if pnl > 0),
        "negative_trade_count": sum(1 for pnl in pnls if pnl < 0),
        "concentration": concentration,
        "leave_one_out_profit_factor": _to_jsonable(
            _profit_factor(_remove_largest_winners(pnls, 1))
        ),
        "leave_two_out_profit_factor": _to_jsonable(
            _profit_factor(_remove_largest_winners(pnls, 2))
        ),
    }


def _training_signal_count(
    frame: pd.DataFrame,
    variant: AfpVariant,
    training_start: pd.Timestamp,
    blindtest_start: pd.Timestamp,
) -> int:
    thresholds = calibrate_afp_thresholds(
        frame,
        training_start,
        blindtest_start - pd.Timedelta(minutes=1),
        variant,
    )
    mask = afp_signal_mask(frame, variant, thresholds)
    return int(
        mask.loc[(frame.index >= training_start) & (frame.index < blindtest_start)].sum()
    )


def _eligibility_reasons(
    aggregate: dict[str, Any],
    training_signal_count: int,
    positive_folds: int,
    worst_fold_pnl: float,
    cost_robust_pf: Any,
    config: AfpConfig,
) -> list[str]:
    reasons: list[str] = []
    if training_signal_count < config.target_min_training_signals:
        reasons.append("training_signal_count_below_frequency_target")
    if training_signal_count > config.target_max_training_signals:
        reasons.append("training_signal_count_above_frequency_target")
    if aggregate["trades"] < config.min_validation_trades:
        reasons.append("validation_trades_below_minimum")
    if positive_folds < config.min_positive_folds:
        reasons.append("positive_folds_below_minimum")
    pf = aggregate["profit_factor"]
    if not isinstance(pf, (int, float)) or pf < config.min_profit_factor:
        reasons.append("profit_factor_below_minimum")
    median = aggregate["median_trade_pnl_usdc"]
    if median is None or median <= config.min_median_trade_pnl_usdc:
        reasons.append("median_trade_pnl_below_minimum")
    leave_two = aggregate["leave_two_out_profit_factor"]
    if (
        not isinstance(leave_two, (int, float))
        or leave_two < config.min_leave_two_out_profit_factor
    ):
        reasons.append("leave_two_out_profit_factor_below_minimum")
    top2 = (aggregate["concentration"].get("top_trade_pnl_share") or {}).get("2")
    if top2 is None or top2 > config.max_top2_pnl_share:
        reasons.append("top2_pnl_share_above_limit")
    if not isinstance(cost_robust_pf, (int, float)) or (
        cost_robust_pf < config.min_cost_robust_profit_factor
    ):
        reasons.append("cost_robust_profit_factor_below_minimum")
    if worst_fold_pnl < config.min_worst_fold_pnl_usdc:
        reasons.append("worst_fold_pnl_below_minimum")
    return reasons


def evaluate_afp_variant(
    frame: pd.DataFrame,
    variant: AfpVariant,
    windows: list[dict[str, str]],
    training_start: pd.Timestamp,
    blindtest_start: pd.Timestamp,
    config: AfpConfig,
) -> dict[str, Any]:
    """Evaluate one AFP variant over training-only walkforward folds."""
    fold_reports: list[dict[str, Any]] = []
    all_trades: list[AfpTrade] = []
    positive_folds = 0
    for window in windows:
        train_end = pd.Timestamp(window["train_end"])
        validation_start = pd.Timestamp(window["validation_start"])
        validation_end = pd.Timestamp(window["validation_end"])
        thresholds = calibrate_afp_thresholds(
            frame,
            training_start,
            train_end,
            variant,
        )
        trades = simulate_afp_variant(
            frame,
            variant,
            thresholds,
            config,
            validation_start,
            validation_end,
            fold_index=window["fold_index"],
        )
        all_trades.extend(trades)
        summary = summarize_afp_trades(trades, validation_start, validation_end, config)
        if summary["pnl_usdc"] > 0:
            positive_folds += 1
        fold_reports.append(
            {
                **window,
                "thresholds": asdict(thresholds),
                "summary": summary,
                "trade_count": len(trades),
            }
        )
    validation_start = pd.Timestamp(windows[0]["validation_start"])
    validation_end = pd.Timestamp(windows[-1]["validation_end"])
    aggregate = summarize_afp_trades(all_trades, validation_start, validation_end, config)
    cost_robust = summarize_afp_trades(
        all_trades,
        validation_start,
        validation_end,
        config,
        config.extra_cost_robustness_slippage_per_side,
    )
    training_signal_count = _training_signal_count(
        frame,
        variant,
        training_start,
        blindtest_start,
    )
    worst_fold_pnl = min(
        (fold["summary"]["pnl_usdc"] for fold in fold_reports),
        default=0.0,
    )
    reasons = _eligibility_reasons(
        aggregate,
        training_signal_count,
        positive_folds,
        worst_fold_pnl,
        cost_robust["profit_factor"],
        config,
    )
    aggregate.update(
        {
            "training_signal_count": training_signal_count,
            "target_signal_count_range": [
                config.target_min_training_signals,
                config.target_max_training_signals,
            ],
            "positive_folds": positive_folds,
            "worst_fold_pnl_usdc": worst_fold_pnl,
            "cost_robust_profit_factor": cost_robust["profit_factor"],
            "eligible_for_frozen_blindtest": not reasons,
            "rejection_reasons": reasons,
            "selection_score": (
                aggregate["usdc_per_day"]
                + (aggregate["median_trade_pnl_usdc"] or 0.0) / 100.0
                - ((aggregate["concentration"].get("top_trade_pnl_share") or {}).get(
                    "2"
                )
                or 0.0)
                if not reasons
                else None
            ),
        }
    )
    return {
        "variant": asdict(variant),
        "folds": fold_reports,
        "aggregate": aggregate,
        "validation_trades": [asdict(trade) for trade in all_trades],
    }


def _load_full_afp_frame() -> tuple[
    pd.DataFrame,
    pd.Timestamp,
    pd.Timestamp,
    pd.Timestamp,
    dict[str, Any],
]:
    eth_1m = load_1m_candles("ETHUSDC")
    training_start, blindtest_start, blindtest_end = latest_train_blind_window(eth_1m)
    selected_eth = eth_1m.loc[
        (eth_1m.index >= training_start) & (eth_1m.index <= blindtest_end)
    ].copy()
    agg = load_agg_trade_minutes(training_start, blindtest_end)
    frame = build_afp_feature_frame(selected_eth, agg)
    completeness = audit_agg_trade_completeness(frame)
    return frame, training_start, blindtest_start, blindtest_end, completeness


def run_afp_v1_flow_persistence_scan(
    config: AfpConfig | None = None,
) -> dict[str, Any]:
    """Run the training-only AFP-v1 aggregate-flow persistence scan."""
    active_config = config or AfpConfig()
    (
        frame,
        training_start,
        blindtest_start,
        blindtest_end,
        completeness,
    ) = _load_full_afp_frame()
    missing_too_high = completeness["missing_ratio"] > active_config.max_missing_ratio
    missing_gap_too_long = (
        completeness["longest_missing_gap_minutes"]
        > active_config.max_contiguous_missing_minutes
    )
    windows = build_walkforward_windows(training_start, blindtest_start, active_config)
    report_out: dict[str, Any] = {
        "strategy_version": AFP_V1_FLOW_PERSISTENCE_VERSION,
        "research_only": True,
        "training_only": True,
        "runs_new_blindtest": False,
        "runs_ui_backtest": False,
        "uses_blindtest_for_selection": False,
        "data_sources_used": [
            "ETHUSDC 1m Klines for execution OHLC",
            (
                "ETHUSDC aggTrade minute features: agg_trade_count, "
                "raw_trade_count, taker_buy_quote_volume, "
                "taker_sell_quote_volume, vwap, max_agg_trade_quote"
            ),
        ],
        "data_range": {
            "training_start": training_start.isoformat(),
            "blindtest_start_not_used": blindtest_start.isoformat(),
            "blindtest_end_not_used": blindtest_end.isoformat(),
        },
        "config": {
            key: str(value) if isinstance(value, Path) else _to_jsonable(value)
            for key, value in asdict(active_config).items()
        },
        "agg_trade_completeness": completeness,
    }
    variant_reports: list[dict[str, Any]] = []
    if missing_too_high or missing_gap_too_long:
        status = "aggtrade_data_incomplete"
        sanity = {
            "status": "not_run_data_incomplete",
            "sanity_pass": False,
            "folds": [],
        }
        recommended_next_step = (
            "Repair or refresh ETHUSDC aggTrade minute features before any AFP "
            "scan. Do not interpolate missing microstructure data."
        )
    else:
        sanity = run_afp_sanity_check(
            frame.loc[frame.index < blindtest_start],
            windows,
            training_start,
            active_config,
        )
        if not sanity["sanity_pass"]:
            status = "afp_sanity_failed"
            recommended_next_step = (
                "Do not run variants or UI backtest. The basic training-only "
                "buy-flow persistence sanity check failed."
            )
        else:
            variant_reports = [
                evaluate_afp_variant(
                    frame.loc[frame.index < blindtest_start],
                    variant,
                    windows,
                    training_start,
                    blindtest_start,
                    active_config,
                )
                for variant in build_afp_variants()
            ]
            passing = [
                report
                for report in variant_reports
                if report["aggregate"]["eligible_for_frozen_blindtest"]
            ]
            if passing:
                status = "new_training_only_candidate_found"
                recommended_next_step = (
                    "Review the selected AFP training-only candidate, then build "
                    "exactly one frozen research blindtest. No UI/router yet."
                )
            else:
                status = "no_afp_training_candidate_found"
                recommended_next_step = (
                    "Archive AFP-v1. It passed sanity but no variant survived "
                    "training-only frequency, robustness and concentration gates."
                )
    passing_reports = [
        report
        for report in variant_reports
        if report["aggregate"]["eligible_for_frozen_blindtest"]
    ]
    best = None
    if passing_reports:
        best = max(
            passing_reports,
            key=lambda report: (
                report["aggregate"]["selection_score"],
                report["aggregate"]["worst_fold_pnl_usdc"],
            ),
        )
    report_out.update(
        {
            "status": status,
            "sanity_check": sanity,
            "variant_count": len(variant_reports),
            "passing_variant_count": len(passing_reports),
            "best_training_only_variant": {
                "variant_id": best["variant"]["variant_id"],
                "aggregate": best["aggregate"],
            }
            if best is not None
            else None,
            "variants": [
                {
                    "variant": report["variant"],
                    "folds": report["folds"],
                    "aggregate": report["aggregate"],
                }
                for report in variant_reports
            ],
            "decision_summary": {
                "afp_is_first_real_aggtrade_core_scan": True,
                "vec_v1_not_rescued": True,
                "frozen_blindtest_conditionally_allowed": best is not None,
                "ui_full_backtest_allowed_now": False,
                "recommended_next_step": recommended_next_step,
            },
        }
    )
    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "afp_v1_flow_persistence_report.json"
    trades_path = active_config.output_dir / "afp_v1_validation_trades.csv"
    report_out["output_paths"] = {
        "report": str(report_path),
        "validation_trades": str(trades_path),
    }
    all_trades = [
        trade
        for report in variant_reports
        for trade in report["validation_trades"]
    ]
    pd.DataFrame(all_trades).to_csv(trades_path, index=False)
    report_path.write_text(
        json.dumps(report_out, indent=2, sort_keys=True, default=_to_jsonable) + "\n",
        encoding="utf-8",
    )
    return report_out
