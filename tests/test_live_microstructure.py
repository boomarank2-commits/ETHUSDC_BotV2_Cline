from datetime import UTC, datetime
from pathlib import Path

import pytest

import src.data.live_microstructure as live_module


def _configure_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "live"
    monkeypatch.setattr(live_module, "LIVE_MICROSTRUCTURE_DIR", output_dir)
    monkeypatch.setattr(
        live_module,
        "LIVE_MICROSTRUCTURE_STATUS_PATH",
        output_dir / "status.json",
    )
    monkeypatch.setattr(
        live_module,
        "LIVE_COLLECTOR_STOP_PATH",
        tmp_path / "collector.stop",
    )
    monkeypatch.setattr(
        live_module,
        "LIVE_COLLECTOR_STOPPED_PATH",
        tmp_path / "collector.stopped",
    )


def test_snapshot_writes_public_spread_and_depth_without_claiming_maturity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        live_module,
        "_utc_now",
        lambda: datetime(2026, 6, 25, 12, 0, tzinfo=UTC),
    )

    def fake_fetch(path: str, params: dict[str, object]):
        if path.endswith("bookTicker"):
            return {
                "bidPrice": "2000",
                "bidQty": "2",
                "askPrice": "2001",
                "askQty": "3",
            }
        return {
            "lastUpdateId": 42,
            "bids": [["2000", "2"]],
            "asks": [["2001", "3"]],
        }

    monkeypatch.setattr(live_module, "_fetch_json", fake_fetch)

    status = live_module.collect_live_microstructure_snapshot()

    assert status.success is True
    assert status.sample_count == 1
    assert status.usable_for_backtest is False
    assert (tmp_path / "live" / "2026-06-25.jsonl").is_file()


def test_current_collector_status_does_not_start_duplicate_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    now = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(live_module, "_utc_now", lambda: now)
    current = live_module.LiveMicrostructureStatus(
        True,
        "active",
        True,
        123,
        "2026-06-25T11:00:00Z",
        "2026-06-25T11:59:00Z",
        60,
        1 / 24,
        False,
        str(tmp_path / "live"),
        None,
    )
    live_module._save_status(current)
    monkeypatch.setattr(
        live_module,
        "_start_collector_process",
        lambda: pytest.fail("duplicate process must not start"),
    )

    assert live_module.ensure_live_microstructure_collection_started() == current


def test_corrupt_status_file_is_treated_as_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    live_module.LIVE_MICROSTRUCTURE_DIR.mkdir(parents=True, exist_ok=True)
    live_module.LIVE_MICROSTRUCTURE_STATUS_PATH.write_bytes(b"\x00" * 128)

    assert live_module.load_live_microstructure_status() is None


def test_status_save_replaces_corrupt_file_atomically(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    live_module.LIVE_MICROSTRUCTURE_DIR.mkdir(parents=True, exist_ok=True)
    live_module.LIVE_MICROSTRUCTURE_STATUS_PATH.write_bytes(b"\x00" * 128)
    status = live_module.LiveMicrostructureStatus(
        True,
        "active",
        True,
        123,
        None,
        None,
        0,
        0.0,
        False,
        str(tmp_path / "live"),
        None,
    )

    live_module._save_status(status)

    assert live_module.load_live_microstructure_status() == status


def test_stop_request_waits_for_collector_acknowledgement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    status = live_module.LiveMicrostructureStatus(
        True,
        "active",
        True,
        123,
        None,
        None,
        0,
        0.0,
        False,
        str(tmp_path / "live"),
        None,
    )
    live_module._save_status(status)

    def fake_sleep(seconds: float) -> None:
        live_module.LIVE_COLLECTOR_STOPPED_PATH.write_text(
            "stopped\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(live_module, "sleep", fake_sleep)

    assert live_module.request_live_microstructure_collector_stop(1.0) is True
    assert live_module.LIVE_COLLECTOR_STOP_PATH.exists()
