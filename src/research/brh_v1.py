"""Research-only BRH/ERV-v1 candidate from the ETH edge scan.

BRH/ERV-v1 = BTC Risk-on ETH Hold / ETH Reversion.

The preceding ``eth_edge_existence_scan`` found training-only structure around
72h ETHUSDC forward returns when BTC was close to its 20-day high, plus smaller
ETHBTC/ETH dip-reversion signals. This module turns that diagnostic into one
minimal walkforward research hypothesis.

It is deliberately not integrated into the UI/router. Only variants that pass
training walkforward eligibility are allowed to run one frozen blindtest.
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
    _avg_win_loss_ratio,
    _max_drawdown,
    _net_return,
    _profit_factor,
    build_erh_feature_frames,
    build_walkforward_windows,
    latest_train_blind_window,
    load_1m_candles,
)

BRH_V1_VERSION = "brh_v1_btc_risk_on_eth_reversion_hold_20260701"


@dataclass(frozen=True)
class BrhVariant:
    """One small fixed-rule BRH/ERV-v1 variant."""

    variant_id: str
    hold_hours: int = 72
    use_btc_drawdown_q80: bool = True
    use_btc_ema_q80: bool = False
    use_ethbtc_ret_q20: bool = False
    use_eth_dist_q20: bool = False
    use_any_eth_dip_q20: bool = False
    use_orderflow_cooldown_q40: bool = False


@dataclass(frozen=True)
class BrhThresholds:
    """Training-only quantile thresholds used by BRH/ERV-v1."""

    btc_drawdown_q80: float
    btc_ema_q80: float
    ethbtc_ret_q20: float
    eth_dist_q20: float
    eth_ofi_q40: float


@dataclass(frozen=True)
class BrhConfig:
    """Configuration for the BRH/ERV-v1 research runner."""

    position_size_usdc: float = 100.0
    val_days: int = 120
    purge_days: int = 7
    fold_count: int = 6
    max_usdc_dev: float = 0.0015
    max_basis_abs: float = 0.0015
    min_validation_trades: int = 18
    min_positive_folds: int = 4
    min_profit_factor: float = 1.15
    min_robust_profit_factor: float = 1.05
    max_drawdown_pct: float = 0.50
    max_single_trade_pnl_share: float = 0.50
    extra_slippage_robustness_per_side: float = 0.0002
    output_dir: Path = REPORTS_DIR / "research" / "brh_v1"
    trading_cost_config: ErhConfig = field(
        default_factory=lambda: ErhConfig(position_size_usdc=100.0)
    )


@dataclass(frozen=True)
class BrhTrade:
    """Captured BRH/ERV-v1 research trade."""

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
    mfe_ret: float
    mae_ret: float
    exit_reason: str
    btc_drawdown_at_signal: float
    btc_ema_at_signal: float
    ethbtc_ret_6_at_signal: float
    eth_dist_to_high_at_signal: float
    eth_ofi_3sum_at_signal: float


@dataclass(frozen=True)
class BrhMetricSummary:
    """Compact BRH/ERV-v1 performance summary."""

    trades: int
    pnl_usdc: float
    usdc_per_day: float
    profit_factor: float | None
    avg_win_loss_ratio: float | None
    median_trade_net_pnl: float | None
    max_drawdown_usdc: float
    max_drawdown_pct: float
    max_single_trade_pnl_share: float | None
    positive_trade_count: int
    negative_trade_count: int


def build_brh_variants() -> list[BrhVariant]:
    """Return the intentionally tiny BRH/ERV-v1 rule set."""
    return [
        BrhVariant("brh_btc_risk_on_72h"),
        BrhVariant("brh_dual_btc_risk_on_72h", use_btc_ema_q80=True),
        BrhVariant("erv_risk_on_ethbtc_dip_72h", use_ethbtc_ret_q20=True),
        BrhVariant("erv_risk_on_eth_dip_72h", use_eth_dist_q20=True),
        BrhVariant("erv_risk_on_any_eth_dip_72h", use_any_eth_dip_q20=True),
        BrhVariant(
            "erv_risk_on_dual_eth_dip_72h",
            use_ethbtc_ret_q20=True,
            use_eth_dist_q20=True,
        ),
        BrhVariant(
            "erv_risk_on_orderflow_cooldown_72h",
            use_orderflow_cooldown_q40=True,
        ),
    ]


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


def _signal_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if "brh_signal_update_bar" not in frame.columns:
        return frame
    return frame[frame["brh_signal_update_bar"].fillna(False).astype(bool)]


def _quantile(frame: pd.DataFrame, column: str, quantile: float) -> float:
    values = frame[column].replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        msg = f"cannot calibrate BRH threshold; no valid values for {column}"
        raise ValueError(msg)
    return float(values.quantile(quantile))


def calibrate_brh_thresholds(
    execution: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> BrhThresholds:
    """Calibrate fixed quantile thresholds from a training-only interval."""
    calibration = execution.loc[(execution.index >= start) & (execution.index <= end)]
    calibration = _signal_rows(calibration)
    return BrhThresholds(
        btc_drawdown_q80=_quantile(calibration, "btc_4h_drawdown_from_20d_high", 0.80),
        btc_ema_q80=_quantile(calibration, "btc_4h_close_vs_ema20", 0.80),
        ethbtc_ret_q20=_quantile(calibration, "ethbtc_4h_ret_6", 0.20),
        eth_dist_q20=_quantile(calibration, "eth_4h_dist_to_20d_high", 0.20),
        eth_ofi_q40=_quantile(calibration, "eth_of_ofi_4h_3sum", 0.40),
    )


def brh_signal_passes(
    row: pd.Series,
    variant: BrhVariant,
    thresholds: BrhThresholds,
    config: BrhConfig,
) -> bool:
    """Return whether one closed feature row proposes a BRH/ERV-v1 entry."""
    required_columns = [
        "btc_4h_drawdown_from_20d_high",
        "btc_4h_close_vs_ema20",
        "ethbtc_4h_ret_6",
        "eth_4h_dist_to_20d_high",
        "eth_of_ofi_4h_3sum",
        "usdc_dev",
        "basis_usdt_4h",
    ]
    if any(pd.isna(row[column]) for column in required_columns):
        return False
    if float(row["usdc_dev"]) > config.max_usdc_dev:
        return False
    if abs(float(row["basis_usdt_4h"])) > config.max_basis_abs:
        return False
    if variant.use_btc_drawdown_q80 and (
        float(row["btc_4h_drawdown_from_20d_high"]) < thresholds.btc_drawdown_q80
    ):
        return False
    if variant.use_btc_ema_q80 and (
        float(row["btc_4h_close_vs_ema20"]) < thresholds.btc_ema_q80
    ):
        return False
    ethbtc_dip = float(row["ethbtc_4h_ret_6"]) <= thresholds.ethbtc_ret_q20
    eth_dip = float(row["eth_4h_dist_to_20d_high"]) <= thresholds.eth_dist_q20
    if variant.use_ethbtc_ret_q20 and not ethbtc_dip:
        return False
    if variant.use_eth_dist_q20 and not eth_dip:
        return False
    if variant.use_any_eth_dip_q20 and not (ethbtc_dip or eth_dip):
        return False
    if variant.use_orderflow_cooldown_q40 and (
        float(row["eth_of_ofi_4h_3sum"]) > thresholds.eth_ofi_q40
    ):
        return False
    return True


def summarize_brh_trades(
    trades: list[BrhTrade],
    start: pd.Timestamp,
    end: pd.Timestamp,
    initial_equity: float,
) -> BrhMetricSummary:
    """Summarize BRH/ERV-v1 trades over a calendar interval."""
    pnls = [trade.net_pnl_usdc for trade in trades]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    total_pnl = float(sum(pnls))
    max_dd_usdc, max_dd_pct = _max_drawdown(pnls, initial_equity)
    positive_pnls = [pnl for pnl in pnls if pnl > 0]
    concentration = None
    if total_pnl > 0 and positive_pnls:
        concentration = max(positive_pnls) / total_pnl
    return BrhMetricSummary(
        trades=len(trades),
        pnl_usdc=total_pnl,
        usdc_per_day=total_pnl / days,
        profit_factor=_profit_factor(pnls),
        avg_win_loss_ratio=_avg_win_loss_ratio(pnls),
        median_trade_net_pnl=float(np.median(pnls)) if pnls else None,
        max_drawdown_usdc=max_dd_usdc,
        max_drawdown_pct=max_dd_pct,
        max_single_trade_pnl_share=concentration,
        positive_trade_count=sum(1 for pnl in pnls if pnl > 0),
        negative_trade_count=sum(1 for pnl in pnls if pnl < 0),
    )


def _summary_dict(summary: BrhMetricSummary) -> dict[str, Any]:
    return {key: _to_jsonable(value) for key, value in asdict(summary).items()}


def simulate_brh_variant(
    execution: pd.DataFrame,
    variant: BrhVariant,
    thresholds: BrhThresholds,
    config: BrhConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
    extra_slippage_per_side: float = 0.0,
) -> list[BrhTrade]:
    """Simulate fixed-hold BRH/ERV-v1 trades without overlap."""
    if execution.empty:
        return []
    trades: list[BrhTrade] = []
    next_entry_allowed_at = start
    signal_frame = execution.loc[(execution.index >= start) & (execution.index <= end)]
    signal_frame = _signal_rows(signal_frame)
    full_index = execution.index

    for signal_time, row in signal_frame.iterrows():
        if signal_time < next_entry_allowed_at:
            continue
        if not brh_signal_passes(row, variant, thresholds, config):
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
        path = execution.iloc[entry_pos:exit_pos]
        mfe_ret = (
            max(0.0, float(path["high"].max()) / entry_price - 1.0)
            if not path.empty
            else 0.0
        )
        mae_ret = (
            min(0.0, float(path["low"].min()) / entry_price - 1.0)
            if not path.empty
            else 0.0
        )
        trades.append(
            BrhTrade(
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
                mfe_ret=mfe_ret,
                mae_ret=mae_ret,
                exit_reason=f"fixed_hold_{variant.hold_hours}h",
                btc_drawdown_at_signal=float(row["btc_4h_drawdown_from_20d_high"]),
                btc_ema_at_signal=float(row["btc_4h_close_vs_ema20"]),
                ethbtc_ret_6_at_signal=float(row["ethbtc_4h_ret_6"]),
                eth_dist_to_high_at_signal=float(row["eth_4h_dist_to_20d_high"]),
                eth_ofi_3sum_at_signal=float(row["eth_of_ofi_4h_3sum"]),
            )
        )
        next_entry_allowed_at = exit_time
    return trades


def _eligible(
    summary: BrhMetricSummary,
    positive_folds: int,
    robust_profit_factor: float | None,
    config: BrhConfig,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if summary.trades < config.min_validation_trades:
        reasons.append("validation_trades_below_minimum")
    if positive_folds < config.min_positive_folds:
        reasons.append("positive_folds_below_minimum")
    if summary.pnl_usdc <= 0:
        reasons.append("validation_pnl_not_positive")
    if summary.profit_factor is None or summary.profit_factor < config.min_profit_factor:
        reasons.append("profit_factor_below_minimum")
    if summary.median_trade_net_pnl is None or summary.median_trade_net_pnl <= 0:
        reasons.append("median_trade_net_pnl_not_positive")
    if summary.max_drawdown_pct > config.max_drawdown_pct:
        reasons.append("max_drawdown_pct_above_limit")
    if robust_profit_factor is None or robust_profit_factor < config.min_robust_profit_factor:
        reasons.append("robust_slippage_profit_factor_below_minimum")
    if (
        summary.max_single_trade_pnl_share is not None
        and summary.max_single_trade_pnl_share > config.max_single_trade_pnl_share
    ):
        reasons.append("single_trade_concentration_above_limit")
    return not reasons, reasons


def _load_full_execution() -> tuple[
    pd.DataFrame,
    pd.Timestamp,
    pd.Timestamp,
    pd.Timestamp,
]:
    eth_1m = load_1m_candles("ETHUSDC")
    training_start, blindtest_start, blindtest_end = latest_train_blind_window(eth_1m)
    window_start = training_start - pd.Timedelta(days=25)
    window_end = blindtest_end
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
    execution, regime = build_erh_feature_frames(
        frames["ETHUSDC"],
        frames["ETHBTC"],
        frames["BTCUSDC"],
        frames["ETHUSDT"],
        frames["USDCUSDT"],
    )
    execution["brh_signal_update_bar"] = execution.index.isin(regime.index)
    execution = execution.loc[
        (execution.index >= training_start) & (execution.index <= blindtest_end)
    ].copy()
    return execution, training_start, blindtest_start, blindtest_end


def run_brh_v1_research(config: BrhConfig | None = None) -> dict[str, Any]:
    """Run BRH/ERV-v1 walkforward and optional frozen blindtest."""
    active_config = config or BrhConfig()
    execution, training_start, blindtest_start, blindtest_end = _load_full_execution()
    windows = build_walkforward_windows(training_start, blindtest_start, active_config)
    variants = build_brh_variants()
    variant_reports: list[dict[str, Any]] = []
    validation_trades_by_variant: dict[str, list[BrhTrade]] = {}
    validation_summaries: dict[str, BrhMetricSummary] = {}
    robust_profit_factors: dict[str, float | None] = {}
    eligible_variants: list[dict[str, Any]] = []

    for variant in variants:
        fold_reports: list[dict[str, Any]] = []
        validation_trades: list[BrhTrade] = []
        robust_trades: list[BrhTrade] = []
        positive_folds = 0
        for window in windows:
            train_end = pd.Timestamp(window["train_end"])
            val_start = pd.Timestamp(window["validation_start"])
            val_end = pd.Timestamp(window["validation_end"])
            thresholds = calibrate_brh_thresholds(execution, training_start, train_end)
            trades = simulate_brh_variant(
                execution,
                variant,
                thresholds,
                active_config,
                val_start,
                val_end,
            )
            robust_fold_trades = simulate_brh_variant(
                execution,
                variant,
                thresholds,
                active_config,
                val_start,
                val_end,
                extra_slippage_per_side=(
                    active_config.extra_slippage_robustness_per_side
                ),
            )
            validation_trades.extend(trades)
            robust_trades.extend(robust_fold_trades)
            fold_summary = summarize_brh_trades(
                trades,
                val_start,
                val_end,
                active_config.position_size_usdc,
            )
            if fold_summary.pnl_usdc > 0:
                positive_folds += 1
            fold_reports.append(
                {
                    **window,
                    "thresholds": asdict(thresholds),
                    "validation_summary": _summary_dict(fold_summary),
                    "trade_count": len(trades),
                }
            )

        validation_summary = summarize_brh_trades(
            validation_trades,
            pd.Timestamp(windows[0]["validation_start"]) if windows else training_start,
            pd.Timestamp(windows[-1]["validation_end"]) if windows else blindtest_start,
            active_config.position_size_usdc,
        )
        robust_pf = _profit_factor([trade.net_pnl_usdc for trade in robust_trades])
        report = {
            "variant": asdict(variant),
            "folds": fold_reports,
            "positive_folds": positive_folds,
            "validation_summary": _summary_dict(validation_summary),
            "slippage_robustness_2bp_profit_factor": _to_jsonable(robust_pf),
        }
        is_eligible, rejection_reasons = _eligible(
            validation_summary,
            positive_folds,
            robust_pf,
            active_config,
        )
        report["eligible_for_blindtest"] = is_eligible
        report["rejection_reasons"] = rejection_reasons
        variant_reports.append(report)
        validation_trades_by_variant[variant.variant_id] = validation_trades
        validation_summaries[variant.variant_id] = validation_summary
        robust_profit_factors[variant.variant_id] = robust_pf
        if is_eligible:
            eligible_variants.append(report)

    selected_variant_report: dict[str, Any] | None = None
    blindtest_trades: list[BrhTrade] = []
    blindtest_summary: dict[str, Any] | None = None
    selected_thresholds: BrhThresholds | None = None
    if eligible_variants:
        selected_variant_report = max(
            eligible_variants,
            key=lambda item: (
                item["validation_summary"]["profit_factor"]
                if isinstance(item["validation_summary"]["profit_factor"], (int, float))
                else float("inf"),
                item["validation_summary"]["pnl_usdc"],
            ),
        )
        selected_variant = BrhVariant(**selected_variant_report["variant"])
        selected_thresholds = calibrate_brh_thresholds(
            execution,
            training_start,
            blindtest_start - pd.Timedelta(hours=1),
        )
        blindtest_trades = simulate_brh_variant(
            execution,
            selected_variant,
            selected_thresholds,
            active_config,
            blindtest_start,
            blindtest_end,
        )
        blindtest_summary = _summary_dict(
            summarize_brh_trades(
                blindtest_trades,
                blindtest_start,
                blindtest_end,
                active_config.position_size_usdc,
            )
        )

    report = {
        "strategy_version": BRH_V1_VERSION,
        "status": (
            "blindtest_completed"
            if selected_variant_report is not None
            else "no_training_walkforward_candidate"
        ),
        "research_only": True,
        "runs_ui_backtest": False,
        "uses_blindtest_for_parameter_selection": False,
        "blindtest_candidate_count_evaluated": 1
        if selected_variant_report is not None
        else 0,
        "data_sources_used": [
            "ETHUSDC 1m OHLCV + kline orderflow resampled to closed 1h/4h",
            "BTCUSDC 1m resampled to 4h risk-on features",
            "ETHBTC 1m resampled to 4h dip/reversion features",
            "ETHUSDT and USDCUSDT 1m resampled to 4h basis/peg sanity filters",
        ],
        "lookahead_safety_notes": [
            "Quantile thresholds are calibrated only on the fold training window.",
            "Signals are evaluated only on new closed 4h availability rows.",
            "Entry executes at the next 1h open after the signal row.",
            "Fixed-hold exits execute at the 1h open after the hold horizon.",
            "One-position-at-a-time is enforced; overlapping signals are skipped.",
            "Blindtest is evaluated once only if walkforward eligibility passes.",
        ],
        "config": {
            key: str(value) if isinstance(value, Path) else _to_jsonable(value)
            for key, value in asdict(active_config).items()
        },
        "data_range": {
            "training_start": training_start.isoformat(),
            "blindtest_start": blindtest_start.isoformat(),
            "blindtest_end": blindtest_end.isoformat(),
        },
        "walkforward_fold_count": len(windows),
        "variant_count": len(variants),
        "eligible_variant_count": len(eligible_variants),
        "selected_variant": selected_variant_report["variant"]
        if selected_variant_report is not None
        else None,
        "selected_thresholds": asdict(selected_thresholds)
        if selected_thresholds is not None
        else None,
        "variants": variant_reports,
        "blindtest_summary": blindtest_summary,
        "blindtest_trades": [asdict(trade) for trade in blindtest_trades],
        "next_required_step": (
            "If blindtest_completed, inspect the frozen blindtest once and do not "
            "tune on it. UI/router integration is still a separate later step."
            if selected_variant_report is not None
            else (
                "No BRH/ERV-v1 variant passed walkforward. Do not UI-backtest. "
                "Archive or ask Arena.ai with this report before another hypothesis."
            )
        ),
    }

    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "brh_v1_research_report.json"
    trades_path = active_config.output_dir / "brh_v1_validation_trades.csv"
    report["output_paths"] = {
        "report": str(report_path),
        "validation_trades": str(trades_path),
    }
    all_validation_trades = [
        asdict(trade)
        for trades in validation_trades_by_variant.values()
        for trade in trades
    ]
    pd.DataFrame(all_validation_trades).to_csv(trades_path, index=False)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=_to_jsonable) + "\n",
        encoding="utf-8",
    )
    return report
