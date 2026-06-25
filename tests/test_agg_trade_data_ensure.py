from datetime import date
from pathlib import Path

import pytest

import src.data.agg_trade_data_ensure as agg_module


def test_aggregate_rows_builds_time_safe_buy_sell_minute_features() -> None:
    rows = [
        ["1", "100", "2", "10", "11", "1767225600000", "false", "true"],
        ["2", "101", "3", "12", "14", "1767225630000000", "true", "true"],
    ]

    minutes = agg_module._aggregate_rows(rows)

    aggregate = minutes["2026-01-01T00:00:00Z"]
    assert aggregate.agg_trade_count == 2
    assert aggregate.raw_trade_count == 5
    assert aggregate.base_volume == 5.0
    assert aggregate.quote_volume == 503.0
    assert aggregate.taker_buy_base_volume == 2.0
    assert aggregate.taker_buy_quote_volume == 200.0
    assert aggregate.taker_sell_base_volume == 3.0
    assert aggregate.taker_sell_quote_volume == 303.0
    assert aggregate.max_agg_trade_quote == 303.0


def test_ensure_downloads_only_missing_required_partitions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    feature_dir = tmp_path / "agg"
    monkeypatch.setattr(agg_module, "AGG_TRADE_FEATURE_DIR", feature_dir)
    monkeypatch.setattr(agg_module, "AGG_TRADE_STATUS_PATH", feature_dir / "status.json")
    monkeypatch.setattr(agg_module, "REQUIRED_CANDLE_COUNT", 2 * 24 * 60)
    downloaded: list[str] = []

    def fake_download(period: str, progress_callback=None) -> Path:
        downloaded.append(period)
        target = feature_dir / f"{period}.csv"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("open_time,agg_trade_count\n", encoding="utf-8")
        return target

    monkeypatch.setattr(agg_module, "_download_and_aggregate_archive", fake_download)

    result = agg_module.ensure_ethusdc_agg_trade_features_ready(
        today=date(2026, 3, 5)
    )

    assert result.success is True
    assert downloaded == ["2026-03-01", "2026-03-02", "2026-03-03"]
    assert result.latest_complete_date == "2026-03-03"

    downloaded.clear()
    second = agg_module.ensure_ethusdc_agg_trade_features_ready(
        today=date(2026, 3, 5)
    )

    assert second.success is True
    assert downloaded == []
    assert second.was_updated is False


def test_partition_plan_uses_daily_archives_for_previous_month(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(agg_module, "REQUIRED_CANDLE_COUNT", 40 * 24 * 60)

    partitions, latest_complete = agg_module._required_partition_keys(
        date(2026, 3, 5)
    )

    assert "2026-01" in partitions
    assert "2026-02" not in partitions
    assert "2026-02-01" in partitions
    assert partitions[-1] == "2026-03-03"
    assert latest_complete == date(2026, 3, 3)
