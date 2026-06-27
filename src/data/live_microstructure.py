"""Collect public ETHUSDC spread and depth snapshots for future time-safe use."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from src.common.paths import CONFIGS_DIR, DATA_DIR, PROJECT_ROOT

LIVE_MICROSTRUCTURE_DIR = DATA_DIR / "live_microstructure" / "ETHUSDC"
LIVE_MICROSTRUCTURE_STATUS_PATH = LIVE_MICROSTRUCTURE_DIR / "status.json"
LIVE_COLLECTOR_STOP_PATH = CONFIGS_DIR / ".live_microstructure.stop"
LIVE_COLLECTOR_STOPPED_PATH = CONFIGS_DIR / ".live_microstructure.stopped"
BINANCE_BASE_URL = "https://api.binance.com"
REQUEST_TIMEOUT_SECONDS = 30
COLLECTION_INTERVAL_SECONDS = 60
HEARTBEAT_MAX_AGE_SECONDS = 180
MINIMUM_BACKTEST_COVERAGE_DAYS = 30


@dataclass(frozen=True)
class LiveMicrostructureStatus:
    """Status of the append-only public ETHUSDC spread/depth collector."""

    success: bool
    message: str
    collector_running: bool
    process_id: int | None
    first_sample_time: str | None
    last_sample_time: str | None
    sample_count: int
    coverage_days: float
    usable_for_backtest: bool
    output_path: str
    error: str | None


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _fetch_json(path: str, params: dict[str, object]) -> Any:
    url = f"{BINANCE_BASE_URL}{path}?{urlencode(params)}"
    try:
        with urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        msg = f"Binance microstructure HTTP error: {error.code}"
        raise RuntimeError(msg) from error
    except (URLError, OSError, TimeoutError) as error:
        msg = f"Binance microstructure request error: {error}"
        raise RuntimeError(msg) from error


def _load_status() -> LiveMicrostructureStatus | None:
    if not LIVE_MICROSTRUCTURE_STATUS_PATH.exists():
        return None
    try:
        raw_status = LIVE_MICROSTRUCTURE_STATUS_PATH.read_text(encoding="utf-8")
        if not raw_status.strip() or "\x00" in raw_status:
            return None
        return LiveMicrostructureStatus(**json.loads(raw_status))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return None


def load_live_microstructure_status() -> LiveMicrostructureStatus | None:
    """Load current collector status without starting network activity."""
    return _load_status()


def _save_status(status: LiveMicrostructureStatus) -> None:
    LIVE_MICROSTRUCTURE_DIR.mkdir(parents=True, exist_ok=True)
    content = json.dumps(asdict(status), indent=2, sort_keys=True) + "\n"
    temp_path = LIVE_MICROSTRUCTURE_STATUS_PATH.with_name(
        f"{LIVE_MICROSTRUCTURE_STATUS_PATH.name}.{os.getpid()}.tmp"
    )
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(LIVE_MICROSTRUCTURE_STATUS_PATH)


def _coverage_days(first_sample: str | None, last_sample: str | None) -> float:
    if first_sample is None or last_sample is None:
        return 0.0
    first = datetime.fromisoformat(first_sample.replace("Z", "+00:00"))
    last = datetime.fromisoformat(last_sample.replace("Z", "+00:00"))
    return max(0.0, (last - first).total_seconds() / 86400)


def _status_is_current(status: LiveMicrostructureStatus | None) -> bool:
    if status is None or not status.collector_running or status.last_sample_time is None:
        return False
    last = datetime.fromisoformat(status.last_sample_time.replace("Z", "+00:00"))
    return (_utc_now() - last).total_seconds() <= HEARTBEAT_MAX_AGE_SECONDS


def collect_live_microstructure_snapshot() -> LiveMicrostructureStatus:
    """Append one timestamped best-bid/ask and top-20 depth snapshot."""
    now = _utc_now()
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    book = _fetch_json("/api/v3/ticker/bookTicker", {"symbol": "ETHUSDC"})
    depth = _fetch_json("/api/v3/depth", {"symbol": "ETHUSDC", "limit": 20})
    sample = {
        "timestamp": timestamp,
        "symbol": "ETHUSDC",
        "best_bid_price": float(book["bidPrice"]),
        "best_bid_quantity": float(book["bidQty"]),
        "best_ask_price": float(book["askPrice"]),
        "best_ask_quantity": float(book["askQty"]),
        "spread": float(book["askPrice"]) - float(book["bidPrice"]),
        "last_update_id": int(depth["lastUpdateId"]),
        "bids": [[float(price), float(quantity)] for price, quantity in depth["bids"]],
        "asks": [[float(price), float(quantity)] for price, quantity in depth["asks"]],
    }
    LIVE_MICROSTRUCTURE_DIR.mkdir(parents=True, exist_ok=True)
    daily_path = LIVE_MICROSTRUCTURE_DIR / f"{now.date().isoformat()}.jsonl"
    with daily_path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(sample, separators=(",", ":")) + "\n")

    previous = _load_status()
    first_sample = (
        previous.first_sample_time
        if previous is not None and previous.first_sample_time is not None
        else timestamp
    )
    sample_count = (previous.sample_count if previous is not None else 0) + 1
    coverage_days = _coverage_days(first_sample, timestamp)
    status = LiveMicrostructureStatus(
        success=True,
        message="ETHUSDC live spread/depth collection active",
        collector_running=True,
        process_id=os.getpid(),
        first_sample_time=first_sample,
        last_sample_time=timestamp,
        sample_count=sample_count,
        coverage_days=coverage_days,
        usable_for_backtest=coverage_days >= MINIMUM_BACKTEST_COVERAGE_DAYS,
        output_path=str(LIVE_MICROSTRUCTURE_DIR),
        error=None,
    )
    _save_status(status)
    return status


def _start_collector_process() -> int:
    for marker in (LIVE_COLLECTOR_STOP_PATH, LIVE_COLLECTOR_STOPPED_PATH):
        if marker.exists():
            marker.unlink()
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "src.data.live_microstructure", "--collect"],
        cwd=PROJECT_ROOT,
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return int(process.pid)


def request_live_microstructure_collector_stop(
    timeout_seconds: float = REQUEST_TIMEOUT_SECONDS + 5,
) -> bool:
    """Ask the detached collector to stop and wait for its acknowledgement."""
    status = _load_status()
    if status is None or not status.collector_running:
        return True
    LIVE_COLLECTOR_STOP_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LIVE_COLLECTOR_STOPPED_PATH.exists():
        LIVE_COLLECTOR_STOPPED_PATH.unlink()
    LIVE_COLLECTOR_STOP_PATH.write_text("stop\n", encoding="utf-8")
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        if LIVE_COLLECTOR_STOPPED_PATH.exists():
            return True
        sleep(0.1)
    return False


def ensure_live_microstructure_collection_started() -> LiveMicrostructureStatus:
    """Ensure a current snapshot exists and a hidden collector stays active."""
    current = _load_status()
    if _status_is_current(current):
        return current
    try:
        snapshot = collect_live_microstructure_snapshot()
        process_id = _start_collector_process()
        status = LiveMicrostructureStatus(
            **{
                **asdict(snapshot),
                "process_id": process_id,
                "message": "ETHUSDC live spread/depth collector started",
            }
        )
    except Exception as error:  # noqa: BLE001
        previous = _load_status()
        status = LiveMicrostructureStatus(
            success=False,
            message=str(error),
            collector_running=False,
            process_id=None,
            first_sample_time=previous.first_sample_time if previous else None,
            last_sample_time=previous.last_sample_time if previous else None,
            sample_count=previous.sample_count if previous else 0,
            coverage_days=previous.coverage_days if previous else 0.0,
            usable_for_backtest=previous.usable_for_backtest if previous else False,
            output_path=str(LIVE_MICROSTRUCTURE_DIR),
            error=str(error),
        )
    _save_status(status)
    return status


def run_collector_forever() -> None:
    """Run the public collector until the local process is stopped."""
    try:
        while not LIVE_COLLECTOR_STOP_PATH.exists():
            try:
                collect_live_microstructure_snapshot()
            except Exception as error:  # noqa: BLE001
                previous = _load_status()
                status = LiveMicrostructureStatus(
                    success=False,
                    message=str(error),
                    collector_running=True,
                    process_id=os.getpid(),
                    first_sample_time=previous.first_sample_time if previous else None,
                    last_sample_time=previous.last_sample_time if previous else None,
                    sample_count=previous.sample_count if previous else 0,
                    coverage_days=previous.coverage_days if previous else 0.0,
                    usable_for_backtest=previous.usable_for_backtest if previous else False,
                    output_path=str(LIVE_MICROSTRUCTURE_DIR),
                    error=str(error),
                )
                _save_status(status)
            for _ in range(COLLECTION_INTERVAL_SECONDS):
                if LIVE_COLLECTOR_STOP_PATH.exists():
                    break
                sleep(1)
    finally:
        LIVE_COLLECTOR_STOPPED_PATH.parent.mkdir(parents=True, exist_ok=True)
        LIVE_COLLECTOR_STOPPED_PATH.write_text("stopped\n", encoding="utf-8")


if __name__ == "__main__":
    if "--collect" in sys.argv:
        run_collector_forever()
