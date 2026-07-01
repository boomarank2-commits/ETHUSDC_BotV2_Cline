"""Research-only ERH-v1 higher-timeframe regime study.

ERH-v1 = ETH Regime Hold / ETH multi-timeframe regime trend participation.

This module deliberately lives outside ``activity_first_router``. It tests the
Arena.ai HTF pivot away from 8-15 minute micro-trading by using closed 4h/1h
candles, ETHBTC leadership, BTC risk context and ETHUSDC order-flow persistence.
If training walkforward eligibility fails, no blindtest and no UI integration
are performed.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import DATA_DIR, REPORTS_DIR
from src.data.train_blind_split import BLINDTEST_CANDLE_COUNT, TRAINING_CANDLE_COUNT

ERH_V1_VERSION = "erh_v1_htf_regime_research_20260701"


@dataclass(frozen=True)
class ErhVariant:
    """Small training-only parameter variant."""

    variant_id: str
    regime_score_min: int
    trail_arm: float
    trail_giveback: float


@dataclass(frozen=True)
class ErhConfig:
    """Configuration for the research-only ERH-v1 runner."""

    position_size_usdc: float = 100.0
    fee_rate_per_side: float = 0.0010
    slippage_rate_per_side: float = 0.0001
    extra_slippage_robustness_per_side: float = 0.0002
    hard_sl: float = 0.06
    max_hold_hours: int = 168
    val_days: int = 120
    purge_days: int = 7
    fold_count: int = 6
    min_validation_trades: int = 12
    min_positive_folds: int = 4
    min_profit_factor: float = 1.40
    min_avg_win_loss_ratio: float = 1.80
    max_drawdown_pct: float = 0.20
    max_single_trade_pnl_share: float = 0.40
    min_robust_profit_factor: float = 1.30
    output_dir: Path = REPORTS_DIR / "research" / "erh_v1"

    @property
    def roundtrip_cost_floor_ret(self) -> float:
        return 2.0 * (self.fee_rate_per_side + self.slippage_rate_per_side)


@dataclass(frozen=True)
class ErhTrade:
    """Captured ERH-v1 research trade."""

    variant_id: str
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
    regime_score_at_entry: int
    ethbtc_4h_close_vs_ema20_at_entry: float
    btc_4h_drawdown_at_entry: float
    eth_of_4h_buy_share_at_entry: float


@dataclass(frozen=True)
class ErhMetricSummary:
    """Compact trade performance summary."""

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


def build_erh_variants() -> list[ErhVariant]:
    """Return the intentionally tiny ERH-v1 training grid."""
    variants: list[ErhVariant] = []
    for regime_score_min in (3, 4):
        for trail_arm in (0.03, 0.04):
            for trail_giveback in (0.030, 0.045):
                variants.append(
                    ErhVariant(
                        variant_id=(
                            f"erh_score{regime_score_min}"
                            f"_arm{int(trail_arm * 1000)}"
                            f"_give{int(trail_giveback * 1000)}"
                        ),
                        regime_score_min=regime_score_min,
                        trail_arm=trail_arm,
                        trail_giveback=trail_giveback,
                    )
                )
    return variants


def _candle_path(symbol: str) -> Path:
    return DATA_DIR / "candles" / f"{symbol}_1m.csv"


def load_1m_candles(symbol: str) -> pd.DataFrame:
    """Load local 1m candle CSVs used by ERH-v1."""
    path = _candle_path(symbol)
    if not path.exists():
        msg = f"missing local candle file for {symbol}: {path}"
        raise FileNotFoundError(msg)
    columns = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "taker_buy_quote_volume",
    ]
    frame = pd.read_csv(path, usecols=lambda name: name in columns)
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
    frame = frame.sort_values("open_time").drop_duplicates("open_time")
    frame = frame.set_index("open_time")
    numeric_columns = [column for column in frame.columns if column != "open_time"]
    frame[numeric_columns] = frame[numeric_columns].apply(pd.to_numeric, errors="coerce")
    return frame


def latest_train_blind_window(
    eth_1m: pd.DataFrame,
) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    """Return training start, blindtest start and blindtest end from latest 1095 days."""
    required = TRAINING_CANDLE_COUNT + BLINDTEST_CANDLE_COUNT
    if len(eth_1m) < required:
        msg = "ETHUSDC dataset does not contain enough 1m rows for 730/365 split"
        raise ValueError(msg)
    selected = eth_1m.tail(required)
    training_start = selected.index[0]
    blindtest_start = selected.index[TRAINING_CANDLE_COUNT]
    blindtest_end = selected.index[-1]
    return training_start, blindtest_start, blindtest_end


def _complete_bars(ohlc: pd.DataFrame, counts: pd.Series, expected_count: int) -> pd.DataFrame:
    complete = ohlc[counts == expected_count].copy()
    return complete.dropna(subset=["open", "high", "low", "close"])


def resample_closed_candles(frame_1m: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Aggregate complete 1m buckets and index them by their availability time.

    A 4h bar starting at 00:00 is indexed at 04:00, never at 00:00. This makes
    the returned frame safe to merge into decision times without lookahead.
    """
    expected_count = {"1h": 60, "4h": 240}[timeframe]
    offset = pd.Timedelta(minutes=expected_count)
    aggregations: dict[str, str] = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "quote_volume": "sum",
        "trade_count": "sum",
        "taker_buy_quote_volume": "sum",
    }
    existing_aggregations = {
        key: value for key, value in aggregations.items() if key in frame_1m.columns
    }
    resampler = frame_1m.resample(timeframe, label="left", closed="left")
    ohlc = resampler.agg(existing_aggregations)
    counts = resampler["close"].count()
    complete = _complete_bars(ohlc, counts, expected_count)
    complete.index = complete.index + offset
    complete.index.name = "available_at"
    if "quote_volume" not in complete.columns:
        complete["quote_volume"] = complete["close"] * complete.get("volume", 0.0)
    if "taker_buy_quote_volume" not in complete.columns:
        complete["taker_buy_quote_volume"] = np.nan
    return complete


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def _streak_true(condition: pd.Series) -> pd.Series:
    streak_values: list[int] = []
    current = 0
    for value in condition.fillna(False).astype(bool):
        current = current + 1 if value else 0
        streak_values.append(current)
    return pd.Series(streak_values, index=condition.index, dtype="int64")


def _profit_factor(pnls: list[float]) -> float | None:
    wins = sum(pnl for pnl in pnls if pnl > 0)
    losses = -sum(pnl for pnl in pnls if pnl < 0)
    if losses <= 0:
        return None if wins <= 0 else math.inf
    return wins / losses


def _avg_win_loss_ratio(pnls: list[float]) -> float | None:
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [-pnl for pnl in pnls if pnl < 0]
    if not wins or not losses:
        return None
    avg_loss = float(np.mean(losses))
    return None if avg_loss <= 0 else float(np.mean(wins) / avg_loss)


def _max_drawdown(pnls: list[float], initial_equity: float) -> tuple[float, float]:
    equity = initial_equity
    peak = initial_equity
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd, max_dd / initial_equity if initial_equity > 0 else math.nan


def summarize_trades(
    trades: list[ErhTrade],
    start: pd.Timestamp,
    end: pd.Timestamp,
    initial_equity: float,
) -> ErhMetricSummary:
    """Summarize ERH-v1 trades over a calendar interval."""
    pnls = [trade.net_pnl_usdc for trade in trades]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    pnl_total = float(sum(pnls))
    max_dd_usdc, max_dd_pct = _max_drawdown(pnls, initial_equity)
    positive_pnls = [pnl for pnl in pnls if pnl > 0]
    concentration = None
    if pnl_total > 0 and positive_pnls:
        concentration = max(positive_pnls) / pnl_total
    return ErhMetricSummary(
        trades=len(trades),
        pnl_usdc=pnl_total,
        usdc_per_day=pnl_total / days,
        profit_factor=_profit_factor(pnls),
        avg_win_loss_ratio=_avg_win_loss_ratio(pnls),
        median_trade_net_pnl=float(np.median(pnls)) if pnls else None,
        max_drawdown_usdc=max_dd_usdc,
        max_drawdown_pct=max_dd_pct,
        max_single_trade_pnl_share=concentration,
        positive_trade_count=sum(1 for pnl in pnls if pnl > 0),
        negative_trade_count=sum(1 for pnl in pnls if pnl < 0),
    )


def build_erh_feature_frames(
    eth_1m: pd.DataFrame,
    ethbtc_1m: pd.DataFrame,
    btc_1m: pd.DataFrame,
    ethusdt_1m: pd.DataFrame,
    usdcusdt_1m: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build 1h execution bars and 4h regime features using closed candles only."""
    eth_1h = resample_closed_candles(eth_1m, "1h")
    eth_4h = resample_closed_candles(eth_1m, "4h")
    ethbtc_4h = resample_closed_candles(ethbtc_1m, "4h")
    btc_4h = resample_closed_candles(btc_1m, "4h")
    ethusdt_4h = resample_closed_candles(ethusdt_1m, "4h")
    usdcusdt_4h = resample_closed_candles(usdcusdt_1m, "4h")

    regime = pd.DataFrame(index=eth_4h.index)
    regime["eth_4h_close"] = eth_4h["close"]
    regime["eth_4h_ret_6"] = eth_4h["close"] / eth_4h["close"].shift(6) - 1.0
    regime["eth_4h_dist_to_20d_high"] = (
        eth_4h["close"] / eth_4h["close"].rolling(120, min_periods=60).max() - 1.0
    )
    regime["eth_4h_close_vs_ema20"] = eth_4h["close"] / _ema(eth_4h["close"], 20) - 1.0
    regime["ethbtc_4h_close_vs_ema20"] = (
        ethbtc_4h["close"] / _ema(ethbtc_4h["close"], 20) - 1.0
    ).reindex(regime.index)
    ethbtc_close = ethbtc_4h["close"].reindex(regime.index)
    regime["ethbtc_4h_ret_6"] = ethbtc_close / ethbtc_close.shift(6) - 1.0
    regime["ethbtc_4h_slope_6"] = ethbtc_close / ethbtc_close.shift(6) - 1.0
    regime["ethbtc_4h_above_ema_streak"] = _streak_true(
        regime["ethbtc_4h_close_vs_ema20"] > 0
    )

    btc_close = btc_4h["close"].reindex(regime.index)
    regime["btc_4h_close_vs_ema20"] = btc_close / _ema(btc_close, 20) - 1.0
    regime["btc_4h_drawdown_from_20d_high"] = (
        btc_close / btc_close.rolling(120, min_periods=60).max() - 1.0
    )
    regime["btc_4h_rv_20"] = btc_close.pct_change().rolling(20, min_periods=20).std()

    quote_volume = eth_4h["quote_volume"].replace(0, np.nan)
    buy_quote = eth_4h["taker_buy_quote_volume"]
    regime["eth_of_4h_buy_share"] = buy_quote / quote_volume
    regime["eth_of_4h_buy_share_3avg"] = regime["eth_of_4h_buy_share"].rolling(
        3, min_periods=3
    ).mean()
    regime["eth_of_ofi_4h"] = (2.0 * buy_quote - quote_volume) / quote_volume
    regime["eth_of_ofi_4h_3sum"] = regime["eth_of_ofi_4h"].rolling(3, min_periods=3).sum()
    regime["eth_of_quote_vol_z_20"] = (
        quote_volume - quote_volume.rolling(20, min_periods=20).mean()
    ) / quote_volume.rolling(20, min_periods=20).std()

    usdc_close = usdcusdt_4h["close"].reindex(regime.index)
    ethusdt_close = ethusdt_4h["close"].reindex(regime.index)
    regime["usdc_dev"] = (usdc_close - 1.0).abs()
    regime["basis_usdt_4h"] = np.log(regime["eth_4h_close"] * usdc_close / ethusdt_close)

    regime["gate_eth_trend"] = regime["eth_4h_close_vs_ema20"] > 0
    regime["gate_ethbtc_trend"] = regime["ethbtc_4h_close_vs_ema20"] > 0
    regime["gate_ethbtc_slope"] = regime["ethbtc_4h_slope_6"] > 0
    regime["gate_btc_not_crash"] = regime["btc_4h_drawdown_from_20d_high"] > -0.15
    regime["gate_orderflow"] = regime["eth_of_4h_buy_share_3avg"] >= 0.505
    regime["gate_usdc"] = regime["usdc_dev"] <= 0.0015
    regime["gate_basis"] = regime["basis_usdt_4h"].abs() <= 0.0015
    gate_columns = [
        "gate_eth_trend",
        "gate_ethbtc_trend",
        "gate_ethbtc_slope",
        "gate_btc_not_crash",
        "gate_orderflow",
        "gate_usdc",
        "gate_basis",
    ]
    regime["hard_gate_pass"] = regime[gate_columns].all(axis=1)
    regime["regime_score"] = (
        (regime["eth_4h_ret_6"] > 0.02).astype(int)
        + (regime["ethbtc_4h_ret_6"] > 0.01).astype(int)
        + (regime["ethbtc_4h_above_ema_streak"] >= 3).astype(int)
        + (regime["eth_of_ofi_4h_3sum"] > 0.03).astype(int)
        + (regime["btc_4h_close_vs_ema20"] > 0).astype(int)
    )

    execution = eth_1h[["open", "high", "low", "close"]].copy()
    execution["eth_1h_close_vs_ema10"] = eth_1h["close"] / _ema(eth_1h["close"], 10) - 1.0
    execution["eth_1h_ret_3"] = eth_1h["close"] / eth_1h["close"].shift(3) - 1.0
    execution["eth_1h_pullback_flag"] = execution["eth_1h_close_vs_ema10"] < 0
    execution["recent_pullback_reclaim"] = (
        execution["eth_1h_pullback_flag"]
        .shift(1)
        .rolling(3, min_periods=1)
        .max()
        .fillna(False)
        .astype(bool)
        & (execution["eth_1h_close_vs_ema10"] > 0)
    )
    regime_for_1h = regime.reindex(execution.index, method="ffill")
    for column in regime_for_1h.columns:
        execution[column] = regime_for_1h[column]
    execution["entry_trigger_base"] = (
        (execution["eth_1h_close_vs_ema10"] > 0)
        & (
            (execution["eth_1h_ret_3"] > 0)
            | execution["recent_pullback_reclaim"].fillna(False).astype(bool)
        )
    )
    execution["no_chase_block"] = (
        (execution["eth_4h_dist_to_20d_high"] > -0.005)
        & (execution["regime_score"] < 4)
    )
    return execution.dropna(subset=["open", "high", "low", "close"]), regime


def variant_regime_active(frame: pd.DataFrame, variant: ErhVariant) -> pd.Series:
    """Return whether ERH-v1 allows a long regime for the variant."""
    return (
        frame["hard_gate_pass"].fillna(False).astype(bool)
        & (frame["regime_score"] >= variant.regime_score_min)
    )


def _net_return(
    entry_price: float,
    exit_price: float,
    config: ErhConfig,
    extra_slippage_per_side: float = 0.0,
) -> tuple[float, float]:
    slip = config.slippage_rate_per_side + extra_slippage_per_side
    entry_exec = entry_price * (1.0 + slip)
    exit_exec = exit_price * (1.0 - slip)
    gross_return = exit_exec / entry_exec - 1.0
    fee_return = 2.0 * config.fee_rate_per_side
    return gross_return - fee_return, 2.0 * (config.fee_rate_per_side + slip)


def simulate_erh_variant(
    execution: pd.DataFrame,
    variant: ErhVariant,
    config: ErhConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
    extra_slippage_per_side: float = 0.0,
) -> list[ErhTrade]:
    """Simulate one ERH-v1 variant on a time interval.

    Signals are evaluated only after the 1h bar is closed. A valid signal
    therefore creates a pending entry that executes at the next available 1h
    open. The entry bar's low may trigger the hard stop after entry.
    Regime/trailing/time exits execute at the next 1h open based on
    information from previously closed bars.
    """
    window = execution.loc[(execution.index >= start) & (execution.index <= end)].copy()
    if window.empty:
        return []
    trades: list[ErhTrade] = []
    in_position = False
    entry_time: pd.Timestamp | None = None
    entry_price = 0.0
    stop_price = 0.0
    highest_close = 0.0
    mfe_ret = 0.0
    mae_ret = 0.0
    scheduled_exit_reason: str | None = None
    entry_metadata: dict[str, Any] = {}
    pending_entry_metadata: dict[str, Any] | None = None

    for timestamp, row in window.iterrows():
        current_open = float(row["open"])
        current_high = float(row["high"])
        current_low = float(row["low"])
        current_close = float(row["close"])
        exited_at_open = False

        if in_position and scheduled_exit_reason is not None:
            net_ret, cost_ret = _net_return(
                entry_price, current_open, config, extra_slippage_per_side
            )
            trades.append(
                ErhTrade(
                    variant_id=variant.variant_id,
                    entry_time=str(entry_time.isoformat()) if entry_time else "",
                    exit_time=timestamp.isoformat(),
                    hold_hours=int((timestamp - entry_time).total_seconds() // 3600)
                    if entry_time
                    else 0,
                    entry_price=entry_price,
                    exit_price=current_open,
                    net_return=net_ret,
                    net_pnl_usdc=net_ret * config.position_size_usdc,
                    fees_and_slippage_ret=cost_ret,
                    mfe_ret=mfe_ret,
                    mae_ret=mae_ret,
                    exit_reason=scheduled_exit_reason,
                    regime_score_at_entry=int(entry_metadata["regime_score"]),
                    ethbtc_4h_close_vs_ema20_at_entry=float(
                        entry_metadata["ethbtc_4h_close_vs_ema20"]
                    ),
                    btc_4h_drawdown_at_entry=float(
                        entry_metadata["btc_4h_drawdown_from_20d_high"]
                    ),
                    eth_of_4h_buy_share_at_entry=float(
                        entry_metadata["eth_of_4h_buy_share"]
                    ),
                )
            )
            in_position = False
            scheduled_exit_reason = None
            exited_at_open = True

        if (
            not in_position
            and pending_entry_metadata is not None
            and not exited_at_open
        ):
            in_position = True
            entry_time = timestamp
            entry_price = current_open
            stop_price = entry_price * (1.0 - config.hard_sl)
            highest_close = current_close
            mfe_ret = max(0.0, current_high / entry_price - 1.0)
            mae_ret = min(0.0, current_low / entry_price - 1.0)
            scheduled_exit_reason = None
            entry_metadata = pending_entry_metadata
            pending_entry_metadata = None

        if in_position:
            mfe_ret = max(mfe_ret, current_high / entry_price - 1.0)
            mae_ret = min(mae_ret, current_low / entry_price - 1.0)
            if current_low <= stop_price:
                net_ret, cost_ret = _net_return(
                    entry_price, stop_price, config, extra_slippage_per_side
                )
                trades.append(
                    ErhTrade(
                        variant_id=variant.variant_id,
                        entry_time=str(entry_time.isoformat()) if entry_time else "",
                        exit_time=timestamp.isoformat(),
                        hold_hours=int((timestamp - entry_time).total_seconds() // 3600)
                        if entry_time
                        else 0,
                        entry_price=entry_price,
                        exit_price=stop_price,
                        net_return=net_ret,
                        net_pnl_usdc=net_ret * config.position_size_usdc,
                        fees_and_slippage_ret=cost_ret,
                        mfe_ret=mfe_ret,
                        mae_ret=mae_ret,
                        exit_reason="hard_stop",
                        regime_score_at_entry=int(entry_metadata["regime_score"]),
                        ethbtc_4h_close_vs_ema20_at_entry=float(
                            entry_metadata["ethbtc_4h_close_vs_ema20"]
                        ),
                        btc_4h_drawdown_at_entry=float(
                            entry_metadata["btc_4h_drawdown_from_20d_high"]
                        ),
                        eth_of_4h_buy_share_at_entry=float(
                            entry_metadata["eth_of_4h_buy_share"]
                        ),
                    )
                )
                in_position = False
                scheduled_exit_reason = None
                continue

            highest_close = max(highest_close, current_close)
            hold_hours = int((timestamp - entry_time).total_seconds() // 3600) if entry_time else 0
            active_now = (
                bool(row["hard_gate_pass"])
                and int(row["regime_score"]) >= variant.regime_score_min
            )
            leadership_broken = float(row["ethbtc_4h_close_vs_ema20"]) < 0
            eth_trend_broken = float(row["eth_4h_close_vs_ema20"]) < 0
            btc_crash = float(row["btc_4h_drawdown_from_20d_high"]) < -0.15
            if not active_now or leadership_broken or eth_trend_broken or btc_crash:
                scheduled_exit_reason = "regime_end"
            elif mfe_ret >= variant.trail_arm:
                trail_stop = highest_close * (1.0 - variant.trail_giveback)
                if current_close <= trail_stop:
                    scheduled_exit_reason = "trailing"
            elif hold_hours >= config.max_hold_hours and mfe_ret < 0.02:
                scheduled_exit_reason = "time_stop"

        if not in_position and pending_entry_metadata is None:
            active = (
                bool(row["hard_gate_pass"])
                and int(row["regime_score"]) >= variant.regime_score_min
            )
            trigger = bool(row["entry_trigger_base"]) and not bool(row["no_chase_block"])
            if active and trigger:
                pending_entry_metadata = {
                    "regime_score": int(row["regime_score"]),
                    "ethbtc_4h_close_vs_ema20": float(
                        row["ethbtc_4h_close_vs_ema20"]
                    ),
                    "btc_4h_drawdown_from_20d_high": float(
                        row["btc_4h_drawdown_from_20d_high"]
                    ),
                    "eth_of_4h_buy_share": float(row["eth_of_4h_buy_share"]),
                }

    if in_position and entry_time is not None:
        last_timestamp = window.index[-1]
        last_close = float(window.iloc[-1]["close"])
        net_ret, cost_ret = _net_return(entry_price, last_close, config, extra_slippage_per_side)
        trades.append(
            ErhTrade(
                variant_id=variant.variant_id,
                entry_time=entry_time.isoformat(),
                exit_time=last_timestamp.isoformat(),
                hold_hours=int((last_timestamp - entry_time).total_seconds() // 3600),
                entry_price=entry_price,
                exit_price=last_close,
                net_return=net_ret,
                net_pnl_usdc=net_ret * config.position_size_usdc,
                fees_and_slippage_ret=cost_ret,
                mfe_ret=mfe_ret,
                mae_ret=mae_ret,
                exit_reason="window_end",
                regime_score_at_entry=int(entry_metadata["regime_score"]),
                ethbtc_4h_close_vs_ema20_at_entry=float(
                    entry_metadata["ethbtc_4h_close_vs_ema20"]
                ),
                btc_4h_drawdown_at_entry=float(
                    entry_metadata["btc_4h_drawdown_from_20d_high"]
                ),
                eth_of_4h_buy_share_at_entry=float(entry_metadata["eth_of_4h_buy_share"]),
            )
        )
    return trades


def build_walkforward_windows(
    training_start: pd.Timestamp,
    blindtest_start: pd.Timestamp,
    config: ErhConfig,
) -> list[dict[str, str]]:
    """Build six expanding validation windows inside the 730-day training span."""
    total_days = max((blindtest_start - training_start).days, 1)
    val_days = config.val_days
    step_days = max((total_days - val_days) // config.fold_count, 1)
    min_train_days = max(180, step_days)
    windows: list[dict[str, str]] = []
    for fold_index in range(config.fold_count):
        val_start = training_start + pd.Timedelta(days=min_train_days + fold_index * step_days)
        val_end = val_start + pd.Timedelta(days=val_days)
        if val_end >= blindtest_start:
            val_end = blindtest_start - pd.Timedelta(hours=1)
        train_end = val_start - pd.Timedelta(days=config.purge_days)
        if train_end <= training_start or val_start >= blindtest_start:
            continue
        windows.append(
            {
                "fold_index": str(fold_index + 1),
                "train_start": training_start.isoformat(),
                "train_end": train_end.isoformat(),
                "validation_start": val_start.isoformat(),
                "validation_end": val_end.isoformat(),
            }
        )
    return windows


def _to_reportable(value: Any) -> Any:
    if isinstance(value, float) and math.isinf(value):
        return "inf"
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def _summary_dict(summary: ErhMetricSummary) -> dict[str, Any]:
    return {key: _to_reportable(value) for key, value in asdict(summary).items()}


def _eligible(
    summary: ErhMetricSummary,
    positive_folds: int,
    robust_profit_factor: float | None,
    score_monotonic: bool,
    config: ErhConfig,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if summary.trades < config.min_validation_trades:
        reasons.append("validation_trades_below_12")
    if positive_folds < config.min_positive_folds:
        reasons.append("positive_folds_below_4_of_6")
    if summary.profit_factor is None or summary.profit_factor < config.min_profit_factor:
        reasons.append("profit_factor_below_1_40")
    if (
        summary.avg_win_loss_ratio is None
        or summary.avg_win_loss_ratio < config.min_avg_win_loss_ratio
    ):
        reasons.append("avg_win_loss_ratio_below_1_80")
    if summary.median_trade_net_pnl is None or summary.median_trade_net_pnl <= 0:
        reasons.append("median_trade_net_pnl_not_positive")
    if summary.max_drawdown_pct > config.max_drawdown_pct:
        reasons.append("max_drawdown_pct_above_0_20")
    if (
        summary.max_single_trade_pnl_share is not None
        and summary.max_single_trade_pnl_share > config.max_single_trade_pnl_share
    ):
        reasons.append("single_trade_concentration_above_0_40")
    if robust_profit_factor is None or robust_profit_factor < config.min_robust_profit_factor:
        reasons.append("robust_slippage_profit_factor_below_1_30")
    if not score_monotonic:
        reasons.append("regime_score_monotonicity_failed")
    return not reasons, reasons


def _variant_pair_key(variant: ErhVariant) -> tuple[float, float]:
    return variant.trail_arm, variant.trail_giveback


def run_erh_v1_research(config: ErhConfig | None = None) -> dict[str, Any]:
    """Run ERH-v1 training walkforward and optional frozen blindtest."""
    active_config = config or ErhConfig()
    eth_1m = load_1m_candles("ETHUSDC")
    training_start, blindtest_start, blindtest_end = latest_train_blind_window(eth_1m)
    window_start = training_start - pd.Timedelta(days=25)
    window_end = blindtest_end
    market_frames = {
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
        market_frames["ETHUSDC"],
        market_frames["ETHBTC"],
        market_frames["BTCUSDC"],
        market_frames["ETHUSDT"],
        market_frames["USDCUSDT"],
    )
    execution = execution.loc[
        (execution.index >= training_start) & (execution.index <= blindtest_end)
    ]
    regime_train = regime.loc[(regime.index >= training_start) & (regime.index < blindtest_start)]
    windows = build_walkforward_windows(training_start, blindtest_start, active_config)
    variants = build_erh_variants()
    variant_reports: list[dict[str, Any]] = []
    variant_validation_trades: dict[str, list[ErhTrade]] = {}
    robust_profit_factors: dict[str, float | None] = {}
    validation_summaries: dict[str, ErhMetricSummary] = {}

    for variant in variants:
        fold_reports: list[dict[str, Any]] = []
        validation_trades: list[ErhTrade] = []
        robust_trades: list[ErhTrade] = []
        positive_folds = 0
        for window in windows:
            val_start = pd.Timestamp(window["validation_start"])
            val_end = pd.Timestamp(window["validation_end"])
            trades = simulate_erh_variant(
                execution,
                variant,
                active_config,
                val_start,
                val_end,
            )
            robust_fold_trades = simulate_erh_variant(
                execution,
                variant,
                active_config,
                val_start,
                val_end,
                extra_slippage_per_side=active_config.extra_slippage_robustness_per_side,
            )
            validation_trades.extend(trades)
            robust_trades.extend(robust_fold_trades)
            fold_summary = summarize_trades(
                trades, val_start, val_end, active_config.position_size_usdc
            )
            if fold_summary.pnl_usdc > 0:
                positive_folds += 1
            fold_reports.append(
                {
                    **window,
                    "validation_summary": _summary_dict(fold_summary),
                    "trade_count": len(trades),
                }
            )
        validation_summary = summarize_trades(
            validation_trades,
            pd.Timestamp(windows[0]["validation_start"]) if windows else training_start,
            pd.Timestamp(windows[-1]["validation_end"]) if windows else blindtest_start,
            active_config.position_size_usdc,
        )
        robust_pf = _profit_factor([trade.net_pnl_usdc for trade in robust_trades])
        variant_validation_trades[variant.variant_id] = validation_trades
        robust_profit_factors[variant.variant_id] = robust_pf
        validation_summaries[variant.variant_id] = validation_summary
        variant_reports.append(
            {
                "variant": asdict(variant),
                "folds": fold_reports,
                "positive_folds": positive_folds,
                "validation_summary": _summary_dict(validation_summary),
                "slippage_robustness_2bp_profit_factor": _to_reportable(robust_pf),
            }
        )

    score4_by_pair = {
        _variant_pair_key(variant): validation_summaries[variant.variant_id].profit_factor
        for variant in variants
        if variant.regime_score_min == 4
    }
    eligible_variants: list[dict[str, Any]] = []
    for variant, report in zip(variants, variant_reports, strict=True):
        if variant.regime_score_min == 3:
            score4_pf = score4_by_pair.get(_variant_pair_key(variant))
            own_pf = validation_summaries[variant.variant_id].profit_factor
            score_monotonic = (
                score4_pf is not None
                and own_pf is not None
                and (score4_pf == math.inf or score4_pf >= own_pf)
            )
        else:
            score_monotonic = True
        is_eligible, rejection_reasons = _eligible(
            validation_summaries[variant.variant_id],
            int(report["positive_folds"]),
            robust_profit_factors[variant.variant_id],
            score_monotonic,
            active_config,
        )
        report["regime_score_monotonicity_check"] = score_monotonic
        report["eligible_for_blindtest"] = is_eligible
        report["rejection_reasons"] = rejection_reasons
        if is_eligible:
            eligible_variants.append(report)

    selected_variant_report: dict[str, Any] | None = None
    blindtest_trades: list[ErhTrade] = []
    blindtest_summary: dict[str, Any] | None = None
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
        selected_variant = ErhVariant(**selected_variant_report["variant"])
        blindtest_trades = simulate_erh_variant(
            execution,
            selected_variant,
            active_config,
            blindtest_start,
            blindtest_end,
        )
        blindtest_summary = _summary_dict(
            summarize_trades(
                blindtest_trades,
                blindtest_start,
                blindtest_end,
                active_config.position_size_usdc,
            )
        )

    regime_active_score3 = (
        regime_train["hard_gate_pass"].fillna(False).astype(bool)
        & (regime_train["regime_score"] >= 3)
    )
    report: dict[str, Any] = {
        "strategy_version": ERH_V1_VERSION,
        "status": (
            "blindtest_completed"
            if selected_variant_report
            else "no_training_walkforward_candidate"
        ),
        "uses_blindtest_for_parameter_selection": False,
        "blindtest_candidate_count_evaluated": 1 if selected_variant_report else 0,
        "selected_variant": selected_variant_report["variant"] if selected_variant_report else None,
        "why_selected": (
            "highest validation PF among eligible ERH-v1 variants"
            if selected_variant_report
            else None
        ),
        "why_rejected": (
            "no variant passed ERH-v1 training walkforward eligibility"
            if not selected_variant_report
            else None
        ),
        "data_sources_used": [
            "ETHUSDC 1m OHLCV + kline orderflow aggregated to 1h/4h",
            "ETHBTC 1m aggregated to 4h leadership features",
            "BTCUSDC 1m aggregated to 4h risk features",
            "ETHUSDT 1m aggregated to 4h cross-quote basis",
            "USDCUSDT 1m aggregated to 4h peg/basis filter",
        ],
        "data_sources_not_used_in_v1": [
            "live orderbook/bookTicker/depth: blocked until enough clean real collection",
            (
                "separate aggTrade archive features: not used in first ERH-v1 pass; "
                "kline taker-buy orderflow is used"
            ),
        ],
        "lookahead_safety_notes": [
            "1h and 4h bars are indexed by close/availability time, not by bucket start.",
            "Entry uses the next 1h open after a closed 1h trigger.",
            "4h regime values are forward-filled only after the 4h candle closed.",
            "Blindtest is only evaluated if a variant passes training walkforward eligibility.",
        ],
        "config": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in asdict(active_config).items()
        },
        "data_range": {
            "training_start": training_start.isoformat(),
            "blindtest_start": blindtest_start.isoformat(),
            "blindtest_end": blindtest_end.isoformat(),
        },
        "regime_diagnostics_training": {
            "regime_4h_bar_count": int(len(regime_train)),
            "regime_active_score3_bar_count": int(regime_active_score3.sum()),
            "regime_score_distribution": {
                str(int(score)): int(count)
                for score, count in regime_train["regime_score"].value_counts().sort_index().items()
            },
        },
        "walkforward_fold_count": len(windows),
        "fold_window_days": active_config.val_days,
        "purge_days": active_config.purge_days,
        "variant_count": len(variants),
        "eligible_variant_count": len(eligible_variants),
        "variants": variant_reports,
        "blindtest_summary": blindtest_summary,
        "blindtest_trades": [asdict(trade) for trade in blindtest_trades],
        "next_required_step": (
            "If no_training_walkforward_candidate, do not run UI backtest. "
            "Inspect ERH-v1 rejection reasons and either refine one HTF hypothesis "
            "or ask Arena.ai with the ERH-v1 report."
            if not selected_variant_report
            else "Review blindtest once only; do not tune on it."
        ),
    }

    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = active_config.output_dir / "erh_v1_research_report.json"
    trades_path = active_config.output_dir / "erh_v1_validation_trades.csv"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=_to_reportable) + "\n",
        encoding="utf-8",
    )
    all_validation_trades = [
        asdict(trade)
        for trades in variant_validation_trades.values()
        for trade in trades
    ]
    pd.DataFrame(all_validation_trades).to_csv(trades_path, index=False)
    report["output_paths"] = {
        "report": str(report_path),
        "validation_trades": str(trades_path),
    }
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=_to_reportable) + "\n",
        encoding="utf-8",
    )
    return report
