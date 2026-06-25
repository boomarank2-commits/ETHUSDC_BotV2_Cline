import json
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

import src.data.binance_kline_client as client_module
from src.data.binance_kline_client import BinanceRequestError, fetch_binance_klines


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_url_parameters_are_built_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_url = ""

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        nonlocal captured_url
        captured_url = url
        return _FakeResponse([])

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)
    fetch_binance_klines("ETHUSDC", "1m", 1_700_000_000_000, 1_700_000_060_000, 500)

    assert "symbol=ETHUSDC" in captured_url
    assert "interval=1m" in captured_url
    assert "startTime=1700000000000" in captured_url
    assert "endTime=1700000060000" in captured_url
    assert "limit=500" in captured_url


def test_timeout_parameter_is_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_timeout = 0

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        nonlocal captured_timeout
        captured_timeout = timeout
        return _FakeResponse([])

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    fetch_binance_klines("ETHUSDC", "1m", 1, timeout=45)

    assert captured_timeout == 45


def test_valid_response_is_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        client_module,
        "urlopen",
        lambda url, timeout: _FakeResponse(
            [
                [
                    1,
                    "100",
                    "110",
                    "90",
                    "105",
                    "12",
                    59_999,
                    "1260",
                    42,
                    "7",
                    "735",
                    "0",
                ]
            ]
        ),
    )

    klines = fetch_binance_klines("ETHUSDC", "1m", 1)

    assert klines[0].open_time_ms == 1
    assert klines[0].close == 105.0
    assert klines[0].close_time_ms == 59_999
    assert klines[0].quote_volume == 1260.0
    assert klines[0].trade_count == 42
    assert klines[0].taker_buy_base_volume == 7.0
    assert klines[0].taker_buy_quote_volume == 735.0


def test_wrong_symbol_is_rejected() -> None:
    with pytest.raises(ValueError):
        fetch_binance_klines("XRPUSDC", "1m", 1)


def test_wrong_interval_is_rejected() -> None:
    with pytest.raises(ValueError):
        fetch_binance_klines("ETHUSDC", "5m", 1)


def test_limit_above_1000_is_rejected() -> None:
    with pytest.raises(ValueError):
        fetch_binance_klines("ETHUSDC", "1m", 1, limit=1001)


def test_http_error_is_handled(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, timeout: int) -> None:
        raise HTTPError(url, 500, "server error", hdrs=None, fp=BytesIO())

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    with pytest.raises(BinanceRequestError, match="Binance HTTP error"):
        fetch_binance_klines("ETHUSDC", "1m", 1)


def test_timeout_url_error_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, timeout: int) -> None:
        raise URLError(TimeoutError("timed out"))

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    with pytest.raises(BinanceRequestError, match="Binance request error"):
        fetch_binance_klines("ETHUSDC", "1m", 1)


def test_os_error_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, timeout: int) -> None:
        raise OSError("[WinError 10060] timeout")

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    with pytest.raises(BinanceRequestError, match="WinError 10060"):
        fetch_binance_klines("ETHUSDC", "1m", 1)
