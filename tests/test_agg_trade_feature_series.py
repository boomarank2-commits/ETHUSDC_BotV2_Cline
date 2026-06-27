import src.data.agg_trade_feature_series as aggtrade_module
import pytest

from src.data.candle_schema import Candle
from src.data.agg_trade_feature_series import build_closed_agg_trade_feature_series


def _candle(index: int, close: float = 100.0) -> Candle:
    return Candle(
        open_time=f"2026-01-01T00:{index:02d}:00Z",
        open=100.0,
        high=max(101.0, close),
        low=min(99.0, close),
        close=close,
        volume=1.0,
    )


def _write_features(tmp_path, values: list[tuple[float, float, float, float, float, float, float]]) -> None:
    rows = [
        "open_time,agg_trade_count,raw_trade_count,base_volume,quote_volume,"
        "taker_buy_base_volume,taker_buy_quote_volume,taker_sell_base_volume,"
        "taker_sell_quote_volume,vwap,max_agg_trade_quote"
    ]
    for index, (agg_count, raw_count, buy_quote, sell_quote, vwap, max_quote, quote_volume) in enumerate(values):
        rows.append(
            f"2026-01-01T00:{index:02d}:00Z,{agg_count},{raw_count},1,"
            f"{quote_volume},{buy_quote / 100},{buy_quote},{sell_quote / 100},"
            f"{sell_quote},{vwap},{max_quote}"
        )
    (tmp_path / "2026-01.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_aggtrade_features_use_closed_current_minute_and_prior_window(tmp_path, monkeypatch) -> None:
    _write_features(
        tmp_path,
        [
            (10, 20, 50, 50, 100, 10, 100),
            (20, 40, 100, 100, 100, 20, 200),
            (30, 60, 210, 90, 100, 30, 300),
        ],
    )
    monkeypatch.setattr(aggtrade_module, "AGG_TRADE_FEATURE_DIR", tmp_path)

    series = build_closed_agg_trade_feature_series(
        [_candle(0), _candle(1), _candle(2, 101.0)],
        2,
    )

    assert series.value_at("agg_trade_count_ratio", 1) is None
    assert series.value_at("agg_trade_count_ratio", 2) == pytest.approx(2.0)
    assert series.value_at("raw_trade_count_ratio", 2) == pytest.approx(2.0)
    assert series.value_at("taker_buy_quote_imbalance", 2) == pytest.approx(0.4)
    assert series.value_at("vwap_close_deviation", 2) == pytest.approx(0.01)
    assert series.value_at("max_agg_trade_quote_share", 2) == pytest.approx(0.1)


def test_aggtrade_feature_at_entry_is_unchanged_by_future_minutes(tmp_path, monkeypatch) -> None:
    initial = [
        (10, 20, 50, 50, 100, 10, 100),
        (20, 40, 100, 100, 100, 20, 200),
        (30, 60, 210, 90, 100, 30, 300),
    ]
    _write_features(tmp_path, initial)
    monkeypatch.setattr(aggtrade_module, "AGG_TRADE_FEATURE_DIR", tmp_path)
    candles = [_candle(0), _candle(1), _candle(2, 101.0)]
    before = build_closed_agg_trade_feature_series(candles, 2)

    _write_features(tmp_path, initial + [(1000, 2000, 999, 1, 90, 999, 1000)])
    after = build_closed_agg_trade_feature_series(candles + [_candle(3, 90.0)], 2)

    for metric in aggtrade_module.AGG_TRADE_METRICS:
        assert after.value_at(metric, 2) == before.value_at(metric, 2)
