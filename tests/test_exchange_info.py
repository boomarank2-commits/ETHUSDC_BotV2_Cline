import json

import pytest

import src.data.exchange_info as exchange_info_module
from src.data.exchange_info import ensure_exchange_info_current, fetch_exchange_info


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _payload() -> dict:
    return {"symbols": [{"symbol": "ETHUSDC", "filters": [{"filterType": "LOT_SIZE"}]}]}


def test_fetch_exchange_info_requests_ethusdc(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_url = ""

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        nonlocal captured_url
        captured_url = url
        return _FakeResponse(_payload())

    monkeypatch.setattr(exchange_info_module, "urlopen", fake_urlopen)

    payload = fetch_exchange_info()

    assert payload["symbols"][0]["symbol"] == "ETHUSDC"
    assert "symbol=ETHUSDC" in captured_url


def test_ensure_exchange_info_current_writes_cache(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    target = tmp_path / "exchange_info.json"
    monkeypatch.setattr(exchange_info_module, "EXCHANGE_INFO_PATH", target)
    monkeypatch.setattr(exchange_info_module, "fetch_exchange_info", _payload)

    status = ensure_exchange_info_current()

    assert status.exists is True
    assert status.was_updated is True
    assert status.usable_for_backtest is True
    assert status.used_in_backtest is True


def test_invalid_exchange_info_symbol_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        exchange_info_module,
        "urlopen",
        lambda url, timeout: _FakeResponse({"symbols": [{"symbol": "BTCUSDC", "filters": []}]}),
    )

    with pytest.raises(ValueError):
        fetch_exchange_info()