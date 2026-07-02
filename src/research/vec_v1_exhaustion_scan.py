"""Training-only VEC-v1 selling-exhaustion scan.

VEC-v1 = Volume Climax & Selling Exhaustion Reversion.

This module is a research-only scan for short-horizon ETHUSDC spot long setups.
It deliberately leaves the BRH/EREM regime-hold line behind and asks whether
real Binance kline orderflow fields show frequent, robust local exhaustion
signals:

    extreme quote volume + taker-sell dominance + red candle + reclaim/absorption

Only the 730-day training/walkforward area is used. The 365-day blindtest is not
loaded into the selection path, no router integration is performed and no UI
backtest is run.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import REPORTS_DIR
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

VEC_V1_EXHAUSTION_SCAN_VERSION = "vec_v1_exhaustion_scan_20260702"


@dataclass(frozen=True)
class VecVariant:
    """One fixed VEC-v1 exhaustion hypothesis."""

    variant_id: str
    timeframe: str
    hold_hours: int
    volume_quantile: float = 0.95
    sell_imbalance_quantile: float = 0.80
    drop_quantile: float = 0.20
    close_location_quantile: float = 0.60
    require_reclaim: bool = True


@dataclass(frozen=True)
class VecThresholds:
    """Training-only thresholds for one VEC fold."""

    quote_volume_ratio_min: float
    sell_imbalance_min: float
    bar_return_max: float
    close_location_min: float


@dataclass(frozen=True)
class VecTrade:
    """One simulated VEC validation trade."""

    variant_id: str
    signal_time: str
    entry_time: str
    exit_time: str
    timeframe: str
    hold_hours: int
    entry_price: float
    exit_price: float
    net_return: float
    net_pnl_usdc: float
    quote_volume_ratio_at_signal: float
    sell_imbalance_at_signal: float
    bar_return_at_signal: float
    close_location_at_signal: float


@dataclass(frozen=True)
class VecConfig:
    """Configuration for VEC-v1 training-only scan."""

    output_dir: Path = REPORTS_DIR / "research" / "vec_v1_exhaustion_scan"
    position_size_usdc: float = 100.0
    val_days: int = 120
    purge_days: int = 7
    fold_count: int = 6
    min_validation_trades: int = 60
    min_positive_folds: int = 5
    min_profit_factor: float = 1.20
    min_median_trade_pnl_usdc: float = 0.0
    min_leave_two_out_profit_factor: float = 1.20
    max_top2_pnl_share: float = 0.35
    min_worst_fold_pnl_usdc: float = 0.0
    trading_cost_config: ErhConfig = ErhConfig(position_size_usdc=100.0)


def build_vec_variants() -> list[VecVariant]:
    """Return a tiny fixed scan set; no blindtest-informed expansion."""
    return [
        VecVariant("vec_15m_sell_climax_reclaim_4h", timeframe="15min", hold_hours=4),
        VecVariant("vec_15m_sell_climax_reclaim_8h", timeframe="15min", hold_hours=8),
        VecVariant("vec_1h_sell_climax_reclaim_8h", timeframe="1h", hold_hours=8),
        VecVariant("vec_1h_sell_climax_reclaim_12h", timeframe="1h", hold_hours=12),
    ]


def _expected_count(timeframe: str) -> int:
    if timeframe == "15min":
        return 15
    if timeframe == "1h":
        return 60
    msg = f"unsupported VEC timeframe: {timeframe}"
    raise ValueError(msg)


def _rolling_lookback_bars(timeframe: str) -> int:
    minutes = _expected_count(timeframe)
    return int(20 * 24 * 60 / minutes)


def resample_vec_candles(frame_1m: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Aggregate complete 1m candles into lookahead-safe VEC decision bars."""
    expected = _expected_count(timeframe)
    offset = pd.Timedelta(minutes=expected)
    aggregations = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "quote_volume": "sum",
        "trade_count": "sum",
        "taker_buy_quote_volume": "sum",
    }
    resampler = frame_1m.resample(timeframe, label="left", closed="left")
    bars = resampler.agg(aggregations)
    counts = resampler["close"].count()
    bars = bars[counts == expected].dropna(subset=["open", "high", "low", "close"])
    bars.index = bars.index + offset
    bars.index.name = "available_at"
    bars["taker_sell_quote_volume"] = (
        bars["quote_volume"] - bars["taker_buy_quote_volume"]
    ).clip(lower=0.0)
    bars["sell_imbalance"] = np.where(
        bars["quote_volume"] > 0,
        (bars["taker_sell_quote_volume"] - bars["taker_buy_quote_volume"])
        / bars["quote_volume"],
        np.nan,
    )
    bars["bar_return"] = bars["close"] / bars["open"] - 1.0
    candle_range = bars["high"] - bars["low"]
    bars["close_location"] = np.where(
        candle_range > 0,
        (bars["close"] - bars["low"]) / candle_range,
        0.5,
    )
    lookback = _rolling_lookback_bars(timeframe)
    prior_quote_mean = bars["quote_volume"].rolling(lookback).mean().shift(1)
    bars["quote_volume_ratio_20d"] = np.where(
        prior_quote_mean > 0,
        bars["quote_volume"] / prior_quote_mean,
        np.nan,
    )
    return bars


def _quantile(frame: pd.DataFrame, column: str, quantile: float) -> float:
    values = frame[column].replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        msg = f"cannot calibrate VEC threshold; no values for {column}"
        raise ValueError(msg)
    return float(values.quantile(quantile))


def calibrate_vec_thresholds(
    bars: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    variant: VecVariant,
) -> VecThresholds:
    """Calibrate thresholds using only the fold training interval."""
    training = bars.loc[(bars.index >= start) & (bars.index <= end)]
    return VecThresholds(
        quote_volume_ratio_min=_quantile(
            training,
            "quote_volume_ratio_20d",
            variant.volume_quantile,
        ),
        sell_imbalance_min=_quantile(
            training,
            "sell_imbalance",
            variant.sell_imbalance_quantile,
        ),
        bar_return_max=_quantile(training, "bar_return", variant.drop_quantile),
        close_location_min=_quantile(
            training,
            "close_location",
            variant.close_location_quantile,
        ),
    )


def vec_signal_passes(
    row: pd.Series,
    variant: VecVariant,
    thresholds: VecThresholds,
) -> bool:
    """Return whether one closed bar is a VEC selling-exhaustion signal."""
    required = [
        "quote_volume_ratio_20d",
        "sell_imbalance",
        "bar_return",
        "close_location",
    ]
    if any(pd.isna(row[column]) for column in required):
        return False
    if float(row["quote_volume_ratio_20d"]) < thresholds.quote_volume_ratio_min:
        return False
    if float(row["sell_imbalance"]) < thresholds.sell_imbalance_min:
        return False
    if float(row["bar_return"]) > thresholds.bar_return_max:
        return False
    return (
        not variant.require_reclaim
        or float(row["close_location"]) >= thresholds.close_location_min
    )


def _hold_bars(variant: VecVariant) -> int:
    return int(variant.hold_hours * 60 / _expected_count(variant.timeframe))


def simulate_vec_variant(
    bars: pd.DataFrame,
    variant: VecVariant,
    thresholds: VecThresholds,
    config: VecConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[VecTrade]:
    """Simulate one VEC variant in a validation interval without overlap."""
    signal_frame = bars.loc[(bars.index >= start) & (bars.index <= end)]
    full_index = bars.index
    trades: list[VecTrade] = []
    next_entry_allowed_at = start
    hold_bars = _hold_bars(variant)
    for signal_time, row in signal_frame.iterrows():
        if signal_time < next_entry_allowed_at:
            continue
        if not vec_signal_passes(row, variant, thresholds):
            continue
        signal_pos = int(full_index.get_loc(signal_time))
        entry_pos = signal_pos + 1
        exit_pos = entry_pos + hold_bars
        if exit_pos >= len(bars):
            continue
        entry_time = full_index[entry_pos]
        exit_time = full_index[exit_pos]
        if entry_time < start or exit_time > end:
            continue
        entry_price = float(bars.iloc[entry_pos]["open"])
        exit_price = float(bars.iloc[exit_pos]["open"])
        net_return, _ = _net_return(
            entry_price,
            exit_price,
            config.trading_cost_config,
        )
        trades.append(
            VecTrade(
                variant_id=variant.variant_id,
                signal_time=signal_time.isoformat(),
                entry_time=entry_time.isoformat(),
                exit_time=exit_time.isoformat(),
                timeframe=variant.timeframe,
                hold_hours=variant.hold_hours,
                entry_price=entry_price,
                exit_price=exit_price,
                net_return=net_return,
                net_pnl_usdc=net_return * config.position_size_usdc,
                quote_volume_ratio_at_signal=float(row["quote_volume_ratio_20d"]),
                sell_imbalance_at_signal=float(row["sell_imbalance"]),
                bar_return_at_signal=float(row["bar_return"]),
                close_location_at_signal=float(row["close_location"]),
            )
        )
        next_entry_allowed_at = exit_time
    return trades


def _remove_largest_winners(pnls: list[float], count: int) -> list[float]:
    positive_indices = [
        index for index, value in sorted(enumerate(pnls), key=lambda item: item[1], reverse=True)
        if value > 0
    ][:count]
    remove = set(positive_indices)
    return [value for index, value in enumerate(pnls) if index not in remove]


def summarize_vec_trades(
    trades: list[VecTrade],
    start: pd.Timestamp,
    end: pd.Timestamp,
    config: VecConfig,
) -> dict[str, Any]:
    """Summarize VEC validation trades."""
    pnls = [trade.net_pnl_usdc for trade in trades]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    total_pnl = float(sum(pnls))
    max_dd, max_dd_pct = _max_drawdown(pnls, config.position_size_usdc)
    concentration = concentration_metrics(pd.DataFrame([asdict(trade) for trade in trades]))
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
        "leave_two_out_profit_factor": _to_jsonable(
            _profit_factor(_remove_largest_winners(pnls, 2))
        ),
    }


def _eligibility_reasons(
    summary: dict[str, Any],
    positive_folds: int,
    worst_fold_pnl: float,
    config: VecConfig,
) -> list[str]:
    reasons: list[str] = []
    if summary["trades"] < config.min_validation_trades:
        reasons.append("validation_trades_below_minimum")
    if positive_folds < config.min_positive_folds:
        reasons.append("positive_folds_below_minimum")
    pf = summary["profit_factor"]
    if not isinstance(pf, (int, float)) or pf < config.min_profit_factor:
        reasons.append("profit_factor_below_minimum")
    median = summary["median_trade_pnl_usdc"]
    if median is None or median <= config.min_median_trade_pnl_usdc:
        reasons.append("median_trade_pnl_not_positive")
    leave_two = summary["leave_two_out_profit_factor"]
    if (
        not isinstance(leave_two, (int, float))
        or leave_two < config.min_leave_two_out_profit_factor
    ):
        reasons.append("leave_two_out_profit_factor_below_minimum")
    top2 = (summary["concentration"].get("top_trade_pnl_share") or {}).get("2")
    if top2 is None or top2 > config.max_top2_pnl_share:
        reasons.append("top2_pnl_share_above_limit")
    if worst_fold_pnl <= config.min_worst_fold_pnl_usdc:
        reasons.append("worst_fold_pnl_not_positive")
    return reasons


def evaluate_vec_variant(
    bars: pd.DataFrame,
    variant: VecVariant,
    windows: list[dict[str, str]],
    training_start: pd.Timestamp,
    config: VecConfig,
) -> dict[str, Any]:
    """Evaluate one fixed VEC variant over training-only walkforward folds."""
    fold_reports: list[dict[str, Any]] = []
    all_trades: list[VecTrade] = []
    positive_folds = 0
    for window in windows:
        train_end = pd.Timestamp(window["train_end"])
        validation_start = pd.Timestamp(window["validation_start"])
        validation_end = pd.Timestamp(window["validation_end"])
        thresholds = calibrate_vec_thresholds(
            bars,
            training_start,
            train_end,
            variant,
        )
        trades = simulate_vec_variant(
            bars,
            variant,
            thresholds,
            config,
            validation_start,
            validation_end,
        )
        all_trades.extend(trades)
        summary = summarize_vec_trades(trades, validation_start, validation_end, config)
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
    validation_start = pd.Timestamp(windows[0]["validation_start"]) if windows else training_start
    validation_end = pd.Timestamp(windows[-1]["validation_end"]) if windows else training_start
    aggregate = summarize_vec_trades(all_trades, validation_start, validation_end, config)
    worst_fold_pnl = min(
        (fold["summary"]["pnl_usdc"] for fold in fold_reports),
        default=0.0,
    )
    reasons = _eligibility_reasons(aggregate, positive_folds, worst_fold_pnl, config)
    aggregate.update(
        {
            "positive_folds": positive_folds,
            "worst_fold_pnl_usdc": worst_fold_pnl,
            "eligible_for_frozen_blindtest": not reasons,
            "rejection_reasons": reasons,
            "selection_score": (
                aggregate["usdc_per_day"]
                + (aggregate["median_trade_pnl_usdc"] or 0.0) / 100.0
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


def run_vec_v1_exhaustion_scan(config: VecConfig | None = None) -> dict[str, Any]:
    """Run VEC-v1 training-only selling-exhaustion scan."""
    active_config = config or VecConfig()
    eth_1m = load_1m_candles("ETHUSDC")
    training_start, blindtest_start, blindtest_end = latest_train_blind_window(eth_1m)
    eth_1m = eth_1m.loc[(eth_1m.index >= training_start) & (eth_1m.index < blindtest_start)]
    windows = build_walkforward_windows(training_start, blindtest_start, active_config)
    bars_by_timeframe = {
        timeframe: resample_vec_candles(eth_1m, timeframe)
        for timeframe in sorted({variant.timeframe for variant in build_vec_variants()})
    }
    variant_reports = [
        evaluate_vec_variant(
            bars_by_timeframe[variant.timeframe],
            variant,
            windows,
            training_start,
            active_config,
        )
        for variant in build_vec_variants()
    ]
    passing = [
        report
        for report in variant_reports
        if report["aggregate"]["eligible_for_frozen_blindtest"]
    ]
    best = None
    if passing:
        best = max(
            passing,
            key=lambda report: (
                report["aggregate"]["selection_score"],
                report["aggregate"]["trades"],
            ),
        )
    status = "vec_training_edge_found" if best is not None else "no_vec_training_edge"
    report_out: dict[str, Any] = {
        "strategy_version": VEC_V1_EXHAUSTION_SCAN_VERSION,
        "status": status,
        "research_only": True,
        "training_only": True,
        "runs_new_blindtest": False,
        "runs_ui_backtest": False,
        "uses_blindtest_for_selection": False,
        "data_sources_used": [
            "ETHUSDC 1m Klines with quote volume, trade count and taker-buy quote volume",
            "lookahead-safe closed 15m/1h resampled VEC bars",
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
        "variant_count": len(variant_reports),
        "passing_variant_count": len(passing),
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
            "brh_erv_line_closed": True,
            "erem_is_not_profit_alpha": True,
            "vec_frozen_blindtest_conditionally_allowed": best is not None,
            "ui_full_backtest_allowed_now": False,
            "recommended_next_step": (
                "Build exactly one frozen VEC research blindtest for the selected "
                "training-only variant; no UI/router integration yet."
                if best is not None
                else (
                    "Do not UI-backtest. VEC-v1 did not find a robust training-only "
                    "exhaustion edge with current kline orderflow features."
                )
            ),
        },
    }
    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "vec_v1_exhaustion_scan_report.json"
    trades_path = active_config.output_dir / "vec_v1_exhaustion_validation_trades.csv"
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
