"""Research-only BELL-v1 BTC->ETH lead-lag/catch-up scan.

BELL-v1 asks a new profit-alpha question without touching the router:

    Does ETHUSDC tend to catch up after BTC has already moved constructively
    while ETH/ETHBTC still lag?

The scan uses only the 730-day training window.  The 365-day blindtest is not
used here.  If no candidate survives the training/walkforward gates, no frozen
blindtest and no UI/full run are allowed.
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
from src.research.erh_v1 import (
    ErhConfig,
    _ema,
    _net_return,
    build_walkforward_windows,
    latest_train_blind_window,
    load_1m_candles,
    resample_closed_candles,
)

BELL_V1_VERSION = "bell_v1_btc_eth_leadlag_scan_20260703"


@dataclass(frozen=True)
class BellVariant:
    """One fixed BELL-v1 lead-lag rule candidate."""

    variant_id: str
    family: str
    hold_hours: int


@dataclass(frozen=True)
class BellThresholds:
    """Training-only thresholds for one BELL-v1 fold."""

    btc_eth_impulse_gap_1h_q80: float
    btc_eth_impulse_gap_4h_q80: float
    btc_4h_ret_2_q60: float
    btc_4h_drawdown_q70: float
    eth_4h_dist_to_20d_high_q70: float
    ethbtc_4h_ret_2_q40: float


@dataclass(frozen=True)
class BellTrade:
    """Captured BELL-v1 research trade."""

    variant_id: str
    signal_time: str
    entry_time: str
    exit_time: str
    hold_hours: int
    entry_price: float
    exit_price: float
    net_return: float
    net_pnl_usdc: float
    fees_and_slippage_ret: float
    exit_reason: str
    btc_eth_impulse_gap_1h_at_signal: float
    btc_eth_impulse_gap_4h_at_signal: float
    btc_4h_ret_2_at_signal: float
    eth_4h_ret_2_at_signal: float
    ethbtc_4h_ret_2_at_signal: float
    btc_4h_drawdown_at_signal: float
    eth_4h_dist_to_high_at_signal: float


@dataclass(frozen=True)
class BellMetricSummary:
    """Compact BELL-v1 performance summary."""

    trades: int
    pnl_usdc: float
    usdc_per_day: float
    profit_factor: float | None
    median_trade_net_pnl: float | None
    max_drawdown_usdc: float
    max_drawdown_pct: float
    top1_pnl_share: float | None
    top2_pnl_share: float | None
    leave_one_out_profit_factor: float | None
    leave_two_out_profit_factor: float | None
    positive_trade_count: int
    negative_trade_count: int


@dataclass(frozen=True)
class BellConfig:
    """Configuration for the BELL-v1 training-only scan."""

    output_dir: Path = REPORTS_DIR / "research" / "bell_v1_leadlag_scan"
    position_size_usdc: float = 100.0
    val_days: int = 120
    purge_days: int = 7
    fold_count: int = 6
    min_sanity_positive_folds: int = 5
    min_validation_trades: int = 48
    min_positive_folds: int = 5
    min_profit_factor: float = 1.20
    max_profit_factor: float = 3.00
    min_leave_one_out_profit_factor: float = 1.10
    min_leave_two_out_profit_factor: float = 1.05
    max_top1_pnl_share: float = 0.30
    max_top2_pnl_share: float = 0.45
    max_usdc_dev: float = 0.0015
    max_basis_abs: float = 0.0015
    extra_slippage_robustness_per_side: float = 0.0002
    trading_cost_config: ErhConfig = field(
        default_factory=lambda: ErhConfig(position_size_usdc=100.0)
    )


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, float) and math.isinf(value):
        return "inf"
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    return value


def build_bell_variants() -> list[BellVariant]:
    """Return the intentionally tiny BELL-v1 variant grid."""
    variants: list[BellVariant] = []
    for hold_hours in (24, 36, 48):
        variants.append(
            BellVariant(
                variant_id=f"bell_btcimp_ethlag_{hold_hours}h",
                family="btc_impulse_eth_lag",
                hold_hours=hold_hours,
            )
        )
        variants.append(
            BellVariant(
                variant_id=f"bell_riskon_ethbtclag_{hold_hours}h",
                family="btc_riskon_ethbtc_lag",
                hold_hours=hold_hours,
            )
        )
    return variants


def _safe_quantile(frame: pd.DataFrame, column: str, quantile: float) -> float:
    values = frame[column].replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        msg = f"cannot calibrate BELL threshold; no valid values for {column}"
        raise ValueError(msg)
    return float(values.quantile(quantile))


def build_bell_feature_frame(
    eth_1m: pd.DataFrame,
    btc_1m: pd.DataFrame,
    ethbtc_1m: pd.DataFrame,
    ethusdt_1m: pd.DataFrame,
    usdcusdt_1m: pd.DataFrame,
) -> pd.DataFrame:
    """Build lookahead-safe BELL-v1 1h execution/features.

    Closed 4h features are indexed by availability time and forward-filled only
    after that availability time.  Entries always occur at the next 1h open.
    """
    eth_1h = resample_closed_candles(eth_1m, "1h")
    btc_1h = resample_closed_candles(btc_1m, "1h")
    ethbtc_1h = resample_closed_candles(ethbtc_1m, "1h")
    eth_4h = resample_closed_candles(eth_1m, "4h")
    btc_4h = resample_closed_candles(btc_1m, "4h")
    ethbtc_4h = resample_closed_candles(ethbtc_1m, "4h")
    ethusdt_4h = resample_closed_candles(ethusdt_1m, "4h")
    usdcusdt_4h = resample_closed_candles(usdcusdt_1m, "4h")

    execution = eth_1h[["open", "high", "low", "close"]].copy()
    execution["eth_1h_ret_3"] = eth_1h["close"] / eth_1h["close"].shift(3) - 1.0
    btc_1h_close = btc_1h["close"].reindex(execution.index)
    ethbtc_1h_close = ethbtc_1h["close"].reindex(execution.index)
    execution["btc_1h_ret_3"] = btc_1h_close / btc_1h_close.shift(3) - 1.0
    execution["ethbtc_1h_ret_3"] = (
        ethbtc_1h_close / ethbtc_1h_close.shift(3) - 1.0
    )

    regime = pd.DataFrame(index=eth_4h.index)
    regime["eth_4h_close"] = eth_4h["close"]
    regime["eth_4h_ret_2"] = eth_4h["close"] / eth_4h["close"].shift(2) - 1.0
    regime["eth_4h_ret_6"] = eth_4h["close"] / eth_4h["close"].shift(6) - 1.0
    regime["eth_4h_close_vs_ema20"] = eth_4h["close"] / _ema(
        eth_4h["close"],
        20,
    ) - 1.0
    regime["eth_4h_dist_to_20d_high"] = (
        eth_4h["close"] / eth_4h["close"].rolling(120, min_periods=60).max()
        - 1.0
    )

    btc_close = btc_4h["close"].reindex(regime.index)
    regime["btc_4h_ret_2"] = btc_close / btc_close.shift(2) - 1.0
    regime["btc_4h_ret_6"] = btc_close / btc_close.shift(6) - 1.0
    regime["btc_4h_close_vs_ema20"] = btc_close / _ema(btc_close, 20) - 1.0
    regime["btc_4h_drawdown_from_20d_high"] = (
        btc_close / btc_close.rolling(120, min_periods=60).max() - 1.0
    )
    regime["btc_4h_rv_20"] = btc_close.pct_change().rolling(20, min_periods=20).std()

    ethbtc_close = ethbtc_4h["close"].reindex(regime.index)
    regime["ethbtc_4h_ret_2"] = ethbtc_close / ethbtc_close.shift(2) - 1.0
    regime["ethbtc_4h_ret_6"] = ethbtc_close / ethbtc_close.shift(6) - 1.0
    regime["ethbtc_4h_close_vs_ema20"] = (
        ethbtc_close / _ema(ethbtc_close, 20) - 1.0
    )
    regime["btc_eth_impulse_gap_4h"] = (
        regime["btc_4h_ret_2"] - regime["eth_4h_ret_2"]
    )
    regime["btc_impulse_with_ethbtc_lag"] = (
        regime["btc_4h_ret_2"] - regime["ethbtc_4h_ret_2"]
    )

    usdc_close = usdcusdt_4h["close"].reindex(regime.index)
    ethusdt_close = ethusdt_4h["close"].reindex(regime.index)
    regime["usdc_dev"] = (usdc_close - 1.0).abs()
    regime["basis_usdt_4h"] = np.log(regime["eth_4h_close"] * usdc_close / ethusdt_close)

    regime_for_1h = regime.reindex(execution.index, method="ffill")
    for column in regime_for_1h.columns:
        execution[column] = regime_for_1h[column]
    execution["btc_eth_impulse_gap_1h"] = (
        execution["btc_1h_ret_3"] - execution["eth_1h_ret_3"]
    )
    execution["bell_signal_update_bar"] = execution.index.isin(regime.index)
    return execution.dropna(subset=["open", "high", "low", "close"])


def calibrate_bell_thresholds(
    execution: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> BellThresholds:
    """Calibrate BELL-v1 thresholds on a fold-training interval only."""
    calibration = execution.loc[(execution.index >= start) & (execution.index <= end)]
    calibration = calibration[calibration["bell_signal_update_bar"].astype(bool)]
    return BellThresholds(
        btc_eth_impulse_gap_1h_q80=_safe_quantile(
            calibration,
            "btc_eth_impulse_gap_1h",
            0.80,
        ),
        btc_eth_impulse_gap_4h_q80=_safe_quantile(
            calibration,
            "btc_eth_impulse_gap_4h",
            0.80,
        ),
        btc_4h_ret_2_q60=_safe_quantile(calibration, "btc_4h_ret_2", 0.60),
        btc_4h_drawdown_q70=_safe_quantile(
            calibration,
            "btc_4h_drawdown_from_20d_high",
            0.70,
        ),
        eth_4h_dist_to_20d_high_q70=_safe_quantile(
            calibration,
            "eth_4h_dist_to_20d_high",
            0.70,
        ),
        ethbtc_4h_ret_2_q40=_safe_quantile(calibration, "ethbtc_4h_ret_2", 0.40),
    )


def bell_signal_passes(
    row: pd.Series,
    variant: BellVariant,
    thresholds: BellThresholds,
    config: BellConfig,
) -> bool:
    """Return whether a closed feature row proposes one BELL-v1 long entry."""
    required_columns = [
        "btc_eth_impulse_gap_1h",
        "btc_eth_impulse_gap_4h",
        "btc_4h_ret_2",
        "btc_4h_close_vs_ema20",
        "btc_4h_drawdown_from_20d_high",
        "eth_4h_dist_to_20d_high",
        "ethbtc_4h_ret_2",
        "usdc_dev",
        "basis_usdt_4h",
    ]
    if any(pd.isna(row[column]) for column in required_columns):
        return False
    if float(row["usdc_dev"]) > config.max_usdc_dev:
        return False
    if abs(float(row["basis_usdt_4h"])) > config.max_basis_abs:
        return False
    eth_not_chased = (
        float(row["eth_4h_dist_to_20d_high"])
        <= thresholds.eth_4h_dist_to_20d_high_q70
    )
    ethbtc_lag = float(row["ethbtc_4h_ret_2"]) <= thresholds.ethbtc_4h_ret_2_q40
    if variant.family == "btc_impulse_eth_lag":
        return (
            float(row["btc_eth_impulse_gap_1h"])
            >= thresholds.btc_eth_impulse_gap_1h_q80
            and float(row["btc_eth_impulse_gap_4h"])
            >= thresholds.btc_eth_impulse_gap_4h_q80
            and float(row["btc_4h_ret_2"]) >= thresholds.btc_4h_ret_2_q60
            and ethbtc_lag
            and eth_not_chased
        )
    if variant.family == "btc_riskon_ethbtc_lag":
        return (
            float(row["btc_4h_drawdown_from_20d_high"])
            >= thresholds.btc_4h_drawdown_q70
            and float(row["btc_4h_close_vs_ema20"]) > 0.0
            and ethbtc_lag
            and eth_not_chased
        )
    return False


def _profit_factor(pnls: list[float]) -> float | None:
    wins = sum(pnl for pnl in pnls if pnl > 0)
    losses = -sum(pnl for pnl in pnls if pnl < 0)
    if losses <= 0:
        return math.inf if wins > 0 else None
    return wins / losses


def _max_drawdown(pnls: list[float], initial_equity: float) -> tuple[float, float]:
    equity = initial_equity
    peak = initial_equity
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd, max_dd / initial_equity if initial_equity > 0 else math.nan


def _top_share(pnls: list[float], count: int) -> float | None:
    positive = sorted([pnl for pnl in pnls if pnl > 0], reverse=True)
    total = float(sum(positive))
    if total <= 0:
        return None
    return float(sum(positive[:count]) / total)


def _leave_out_profit_factor(pnls: list[float], remove_winners: int) -> float | None:
    remaining = list(pnls)
    for _ in range(remove_winners):
        winners = [pnl for pnl in remaining if pnl > 0]
        if not winners:
            break
        remaining.remove(max(winners))
    return _profit_factor(remaining)


def summarize_bell_trades(
    trades: list[BellTrade],
    start: pd.Timestamp,
    end: pd.Timestamp,
    initial_equity: float,
) -> BellMetricSummary:
    """Summarize BELL-v1 trades over a calendar interval."""
    pnls = [trade.net_pnl_usdc for trade in trades]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    total_pnl = float(sum(pnls))
    max_dd_usdc, max_dd_pct = _max_drawdown(pnls, initial_equity)
    return BellMetricSummary(
        trades=len(trades),
        pnl_usdc=total_pnl,
        usdc_per_day=total_pnl / days,
        profit_factor=_profit_factor(pnls),
        median_trade_net_pnl=float(np.median(pnls)) if pnls else None,
        max_drawdown_usdc=max_dd_usdc,
        max_drawdown_pct=max_dd_pct,
        top1_pnl_share=_top_share(pnls, 1),
        top2_pnl_share=_top_share(pnls, 2),
        leave_one_out_profit_factor=_leave_out_profit_factor(pnls, 1),
        leave_two_out_profit_factor=_leave_out_profit_factor(pnls, 2),
        positive_trade_count=sum(1 for pnl in pnls if pnl > 0),
        negative_trade_count=sum(1 for pnl in pnls if pnl < 0),
    )


def _summary_dict(summary: BellMetricSummary) -> dict[str, Any]:
    return {key: _to_jsonable(value) for key, value in asdict(summary).items()}


def simulate_bell_variant(
    execution: pd.DataFrame,
    variant: BellVariant,
    thresholds: BellThresholds,
    config: BellConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
    extra_slippage_per_side: float = 0.0,
) -> list[BellTrade]:
    """Simulate one fixed BELL-v1 variant without overlapping trades."""
    if execution.empty:
        return []
    trades: list[BellTrade] = []
    next_entry_allowed_at = start
    signal_frame = execution.loc[(execution.index >= start) & (execution.index <= end)]
    signal_frame = signal_frame[signal_frame["bell_signal_update_bar"].astype(bool)]
    full_index = execution.index
    for signal_time, row in signal_frame.iterrows():
        if signal_time < next_entry_allowed_at:
            continue
        if not bell_signal_passes(row, variant, thresholds, config):
            continue
        signal_pos = int(full_index.get_loc(signal_time))
        entry_pos = signal_pos + 1
        exit_pos = entry_pos + variant.hold_hours
        if exit_pos >= len(execution):
            continue
        entry_time = full_index[entry_pos]
        exit_time = full_index[exit_pos]
        if entry_time < start or exit_time > end:
            continue
        entry_price = float(execution.iloc[entry_pos]["open"])
        exit_price = float(execution.iloc[exit_pos]["open"])
        net_ret, cost_ret = _net_return(
            entry_price,
            exit_price,
            config.trading_cost_config,
            extra_slippage_per_side,
        )
        trades.append(
            BellTrade(
                variant_id=variant.variant_id,
                signal_time=signal_time.isoformat(),
                entry_time=entry_time.isoformat(),
                exit_time=exit_time.isoformat(),
                hold_hours=variant.hold_hours,
                entry_price=entry_price,
                exit_price=exit_price,
                net_return=net_ret,
                net_pnl_usdc=net_ret * config.position_size_usdc,
                fees_and_slippage_ret=cost_ret,
                exit_reason=f"fixed_hold_{variant.hold_hours}h",
                btc_eth_impulse_gap_1h_at_signal=float(
                    row["btc_eth_impulse_gap_1h"]
                ),
                btc_eth_impulse_gap_4h_at_signal=float(
                    row["btc_eth_impulse_gap_4h"]
                ),
                btc_4h_ret_2_at_signal=float(row["btc_4h_ret_2"]),
                eth_4h_ret_2_at_signal=float(row["eth_4h_ret_2"]),
                ethbtc_4h_ret_2_at_signal=float(row["ethbtc_4h_ret_2"]),
                btc_4h_drawdown_at_signal=float(
                    row["btc_4h_drawdown_from_20d_high"]
                ),
                eth_4h_dist_to_high_at_signal=float(
                    row["eth_4h_dist_to_20d_high"]
                ),
            )
        )
        next_entry_allowed_at = exit_time
    return trades


def _forward_return_at_signal(
    execution: pd.DataFrame,
    signal_time: pd.Timestamp,
    horizon_hours: int,
    config: BellConfig,
) -> float | None:
    full_index = execution.index
    signal_pos = int(full_index.get_loc(signal_time))
    entry_pos = signal_pos + 1
    exit_pos = entry_pos + horizon_hours
    if exit_pos >= len(execution):
        return None
    entry_price = float(execution.iloc[entry_pos]["open"])
    exit_price = float(execution.iloc[exit_pos]["open"])
    net_ret, _ = _net_return(entry_price, exit_price, config.trading_cost_config)
    return net_ret


def _sanity_feature_fold(
    execution: pd.DataFrame,
    feature: str,
    horizon_hours: int,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    validation_start: pd.Timestamp,
    validation_end: pd.Timestamp,
    config: BellConfig,
) -> dict[str, Any]:
    train = execution.loc[(execution.index >= train_start) & (execution.index <= train_end)]
    train = train[train["bell_signal_update_bar"].astype(bool)]
    threshold = _safe_quantile(train, feature, 0.80)
    validation = execution.loc[
        (execution.index >= validation_start) & (execution.index <= validation_end)
    ]
    validation = validation[validation["bell_signal_update_bar"].astype(bool)]
    top_returns: list[float] = []
    baseline_returns: list[float] = []
    for timestamp, row in validation.iterrows():
        forward = _forward_return_at_signal(execution, timestamp, horizon_hours, config)
        if forward is None:
            continue
        baseline_returns.append(forward)
        if (
            float(row[feature]) >= threshold
            and float(row["usdc_dev"]) <= config.max_usdc_dev
            and abs(float(row["basis_usdt_4h"])) <= config.max_basis_abs
        ):
            top_returns.append(forward)
    top_mean = float(np.mean(top_returns)) if top_returns else None
    baseline_mean = float(np.mean(baseline_returns)) if baseline_returns else None
    positive = (
        top_mean is not None
        and baseline_mean is not None
        and top_mean > 0
        and top_mean > baseline_mean
    )
    return {
        "threshold_q80": threshold,
        "top_count": len(top_returns),
        "baseline_count": len(baseline_returns),
        "top_mean_net_return": top_mean,
        "baseline_mean_net_return": baseline_mean,
        "top_beats_positive_baseline": positive,
    }


def run_bell_sanity_scan(
    execution: pd.DataFrame,
    windows: list[dict[str, str]],
    training_start: pd.Timestamp,
    config: BellConfig,
) -> dict[str, Any]:
    """Run the training-only BELL-v1 lead-lag existence sanity scan."""
    feature_names = (
        "btc_eth_impulse_gap_1h",
        "btc_eth_impulse_gap_4h",
        "btc_impulse_with_ethbtc_lag",
    )
    horizons = (12, 24, 36, 48)
    scans: list[dict[str, Any]] = []
    for feature in feature_names:
        for horizon in horizons:
            folds = []
            for window in windows:
                folds.append(
                    {
                        **window,
                        **_sanity_feature_fold(
                            execution,
                            feature,
                            horizon,
                            training_start,
                            pd.Timestamp(window["train_end"]),
                            pd.Timestamp(window["validation_start"]),
                            pd.Timestamp(window["validation_end"]),
                            config,
                        ),
                    }
                )
            positive_folds = sum(
                bool(fold["top_beats_positive_baseline"]) for fold in folds
            )
            scans.append(
                {
                    "feature": feature,
                    "horizon_hours": horizon,
                    "positive_folds": positive_folds,
                    "sanity_passed": positive_folds >= config.min_sanity_positive_folds,
                    "folds": folds,
                }
            )
    passing = [scan for scan in scans if scan["sanity_passed"]]
    best = max(
        scans,
        key=lambda scan: (
            scan["positive_folds"],
            np.nanmean(
                [
                    fold["top_mean_net_return"]
                    for fold in scan["folds"]
                    if fold["top_mean_net_return"] is not None
                ]
                or [float("-inf")]
            ),
        ),
        default=None,
    )
    return {
        "sanity_status": "bell_sanity_passed" if passing else "bell_sanity_failed",
        "sanity_passed": bool(passing),
        "passing_scan_count": len(passing),
        "best_scan": best,
        "scans": scans,
    }


def _baseline_unconditional_trades(
    execution: pd.DataFrame,
    hold_hours: int,
    config: BellConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[float]:
    returns: list[float] = []
    full_index = execution.index
    next_entry_allowed_at = start
    window = execution.loc[(execution.index >= start) & (execution.index <= end)]
    for signal_time in window.index:
        if signal_time < next_entry_allowed_at:
            continue
        signal_pos = int(full_index.get_loc(signal_time))
        entry_pos = signal_pos + 1
        exit_pos = entry_pos + hold_hours
        if exit_pos >= len(execution):
            continue
        entry_time = full_index[entry_pos]
        exit_time = full_index[exit_pos]
        if entry_time < start or exit_time > end:
            continue
        entry_price = float(execution.iloc[entry_pos]["open"])
        exit_price = float(execution.iloc[exit_pos]["open"])
        net_ret, _ = _net_return(entry_price, exit_price, config.trading_cost_config)
        returns.append(net_ret * config.position_size_usdc)
        next_entry_allowed_at = exit_time
    return returns


def _eligible(
    summary: BellMetricSummary,
    fold_summaries: list[BellMetricSummary],
    robust_summary: BellMetricSummary,
    baseline_pnl_usdc: float,
    config: BellConfig,
    sanity_passed: bool,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    positive_folds = sum(fold.pnl_usdc > 0 for fold in fold_summaries)
    worst_fold = min((fold.pnl_usdc for fold in fold_summaries), default=0.0)
    if not sanity_passed:
        reasons.append("leadlag_sanity_scan_failed")
    if summary.trades < config.min_validation_trades:
        reasons.append("validation_trades_below_minimum")
    if positive_folds < config.min_positive_folds:
        reasons.append("positive_folds_below_minimum")
    if worst_fold <= 0:
        reasons.append("worst_fold_not_positive")
    if summary.pnl_usdc <= 0:
        reasons.append("validation_pnl_not_positive")
    if summary.pnl_usdc <= baseline_pnl_usdc:
        reasons.append("does_not_beat_unconditional_eth_hold_baseline")
    if summary.profit_factor is None or summary.profit_factor < config.min_profit_factor:
        reasons.append("profit_factor_below_minimum")
    if summary.profit_factor is not None and summary.profit_factor > config.max_profit_factor:
        reasons.append("profit_factor_above_overfit_limit")
    if summary.median_trade_net_pnl is None or summary.median_trade_net_pnl <= 0:
        reasons.append("median_trade_net_pnl_not_positive")
    if (
        summary.leave_one_out_profit_factor is None
        or summary.leave_one_out_profit_factor < config.min_leave_one_out_profit_factor
    ):
        reasons.append("leave_one_out_profit_factor_below_minimum")
    if (
        summary.leave_two_out_profit_factor is None
        or summary.leave_two_out_profit_factor < config.min_leave_two_out_profit_factor
    ):
        reasons.append("leave_two_out_profit_factor_below_minimum")
    if summary.top1_pnl_share is None or summary.top1_pnl_share > config.max_top1_pnl_share:
        reasons.append("top1_pnl_share_above_limit")
    if summary.top2_pnl_share is None or summary.top2_pnl_share > config.max_top2_pnl_share:
        reasons.append("top2_pnl_share_above_limit")
    if robust_summary.pnl_usdc <= 0 or (
        robust_summary.profit_factor is not None and robust_summary.profit_factor < 1.0
    ):
        reasons.append("extra_slippage_robustness_failed")
    return not reasons, reasons


def evaluate_bell_variant(
    execution: pd.DataFrame,
    variant: BellVariant,
    windows: list[dict[str, str]],
    training_start: pd.Timestamp,
    config: BellConfig,
    sanity_passed: bool,
) -> dict[str, Any]:
    """Evaluate one BELL-v1 variant on training-only walkforward folds."""
    fold_reports: list[dict[str, Any]] = []
    validation_trades: list[BellTrade] = []
    robust_trades: list[BellTrade] = []
    baseline_pnls: list[float] = []
    fold_summaries: list[BellMetricSummary] = []
    for window in windows:
        train_end = pd.Timestamp(window["train_end"])
        validation_start = pd.Timestamp(window["validation_start"])
        validation_end = pd.Timestamp(window["validation_end"])
        thresholds = calibrate_bell_thresholds(execution, training_start, train_end)
        trades = simulate_bell_variant(
            execution,
            variant,
            thresholds,
            config,
            validation_start,
            validation_end,
        )
        robust = simulate_bell_variant(
            execution,
            variant,
            thresholds,
            config,
            validation_start,
            validation_end,
            extra_slippage_per_side=config.extra_slippage_robustness_per_side,
        )
        baseline = _baseline_unconditional_trades(
            execution,
            variant.hold_hours,
            config,
            validation_start,
            validation_end,
        )
        validation_trades.extend(trades)
        robust_trades.extend(robust)
        baseline_pnls.extend(baseline)
        fold_summary = summarize_bell_trades(
            trades,
            validation_start,
            validation_end,
            config.position_size_usdc,
        )
        fold_summaries.append(fold_summary)
        fold_reports.append(
            {
                **window,
                "thresholds": asdict(thresholds),
                "validation_summary": _summary_dict(fold_summary),
                "baseline_unconditional_pnl_usdc": float(sum(baseline)),
                "trade_count": len(trades),
            }
        )
    aggregate_start = (
        pd.Timestamp(windows[0]["validation_start"]) if windows else training_start
    )
    aggregate_end = (
        pd.Timestamp(windows[-1]["validation_end"]) if windows else training_start
    )
    summary = summarize_bell_trades(
        validation_trades,
        aggregate_start,
        aggregate_end,
        config.position_size_usdc,
    )
    robust_summary = summarize_bell_trades(
        robust_trades,
        aggregate_start,
        aggregate_end,
        config.position_size_usdc,
    )
    baseline_pnl = float(sum(baseline_pnls))
    is_eligible, rejection_reasons = _eligible(
        summary,
        fold_summaries,
        robust_summary,
        baseline_pnl,
        config,
        sanity_passed,
    )
    return {
        "variant": asdict(variant),
        "folds": fold_reports,
        "validation_summary": _summary_dict(summary),
        "robust_extra_slippage_summary": _summary_dict(robust_summary),
        "baseline_unconditional_pnl_usdc": baseline_pnl,
        "eligible_for_frozen_blindtest": is_eligible,
        "rejection_reasons": rejection_reasons,
        "selection_score": (
            summary.usdc_per_day
            - max(0.0, (summary.top2_pnl_share or 0.0) - config.max_top2_pnl_share)
            if is_eligible
            else None
        ),
    }


def _load_execution() -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    eth_1m = load_1m_candles("ETHUSDC")
    training_start, blindtest_start, blindtest_end = latest_train_blind_window(eth_1m)
    window_start = training_start - pd.Timedelta(days=25)
    window_end = blindtest_start - pd.Timedelta(minutes=1)
    frames = {
        "ETHUSDC": eth_1m.loc[(eth_1m.index >= window_start) & (eth_1m.index <= window_end)],
        "BTCUSDC": load_1m_candles("BTCUSDC").loc[
            lambda frame: (frame.index >= window_start) & (frame.index <= window_end)
        ],
        "ETHBTC": load_1m_candles("ETHBTC").loc[
            lambda frame: (frame.index >= window_start) & (frame.index <= window_end)
        ],
        "ETHUSDT": load_1m_candles("ETHUSDT").loc[
            lambda frame: (frame.index >= window_start) & (frame.index <= window_end)
        ],
        "USDCUSDT": load_1m_candles("USDCUSDT").loc[
            lambda frame: (frame.index >= window_start) & (frame.index <= window_end)
        ],
    }
    execution = build_bell_feature_frame(
        frames["ETHUSDC"],
        frames["BTCUSDC"],
        frames["ETHBTC"],
        frames["ETHUSDT"],
        frames["USDCUSDT"],
    )
    execution = execution.loc[
        (execution.index >= training_start) & (execution.index < blindtest_start)
    ].copy()
    return execution, training_start, blindtest_start, blindtest_end


def run_bell_v1_leadlag_scan(config: BellConfig | None = None) -> dict[str, Any]:
    """Run the BELL-v1 training-only lead-lag/catch-up scan."""
    active_config = config or BellConfig()
    execution, training_start, blindtest_start, blindtest_end = _load_execution()
    windows = build_walkforward_windows(training_start, blindtest_start, active_config)
    sanity = run_bell_sanity_scan(execution, windows, training_start, active_config)
    variant_reports = [
        evaluate_bell_variant(
            execution,
            variant,
            windows,
            training_start,
            active_config,
            bool(sanity["sanity_passed"]),
        )
        for variant in build_bell_variants()
    ]
    eligible = [
        report
        for report in variant_reports
        if report["eligible_for_frozen_blindtest"]
    ]
    selected = None
    if eligible:
        selected = max(
            eligible,
            key=lambda report: (
                report["selection_score"],
                report["validation_summary"]["leave_two_out_profit_factor"],
                -report["validation_summary"]["top2_pnl_share"],
            ),
        )
    if selected is not None:
        status = "new_training_only_candidate_found"
    elif sanity["sanity_passed"]:
        status = "bell_sanity_passed_but_no_walkforward_candidate"
    else:
        status = "no_bell_training_edge"
    report: dict[str, Any] = {
        "strategy_version": BELL_V1_VERSION,
        "status": status,
        "research_only": True,
        "training_only": True,
        "runs_blindtest": False,
        "runs_ui_backtest": False,
        "changes_router": False,
        "uses_blindtest_for_selection": False,
        "keeps_erem_hysteresis_v1_2_unchanged": True,
        "data_range": {
            "training_start": training_start.isoformat(),
            "blindtest_start_not_used": blindtest_start.isoformat(),
            "blindtest_end_not_used": blindtest_end.isoformat(),
        },
        "data_sources_used": [
            "ETHUSDC 1m resampled to closed 1h/4h execution and features",
            "BTCUSDC 1m resampled to closed 1h/4h lead/risk context",
            "ETHBTC 1m resampled to closed 1h/4h relative lag context",
            "ETHUSDT and USDCUSDT 1m used only for basis/peg sanity",
        ],
        "lookahead_safety_notes": [
            "1h/4h bars are indexed by availability time after close.",
            "Fold thresholds are calibrated only on fold-training data.",
            "Signals are evaluated only on closed 4h update bars.",
            "Entries execute at the next 1h open after signal availability.",
            "Exits are fixed-hold next-open exits; no adaptive exit tuning.",
            "Blindtest remains untouched in this scan.",
        ],
        "config": {
            key: str(value) if isinstance(value, Path) else _to_jsonable(value)
            for key, value in asdict(active_config).items()
        },
        "walkforward_fold_count": len(windows),
        "sanity_scan": sanity,
        "variant_count": len(variant_reports),
        "eligible_variant_count": len(eligible),
        "selected_training_only_variant": selected,
        "variants": variant_reports,
        "decision_summary": {
            "frozen_blindtest_allowed_now": selected is not None,
            "ui_full_backtest_allowed_now": False,
            "router_integration_allowed_now": False,
            "recommended_next_step": (
                "Build exactly one frozen research blindtest for the selected "
                "BELL-v1 candidate. Do not patch router/UI yet."
                if selected is not None
                else (
                    "Do not run a UI full backtest for BELL-v1. The shared "
                    "router path is unchanged; a full run would only re-measure "
                    "the existing EREM-Hysteresis v1.2 baseline."
                )
            ),
        },
    }
    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "bell_v1_leadlag_scan_report.json"
    report["output_paths"] = {"report": str(report_path)}
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=_to_jsonable) + "\n",
        encoding="utf-8",
    )
    return report
