from pathlib import Path

from src.common.config import CONFIG


def test_project_truth_is_ethusdc_usdc() -> None:
    assert CONFIG.symbol == "ETHUSDC"
    assert CONFIG.quote_asset == "USDC"
    assert CONFIG.allow_short is False
    assert CONFIG.allow_futures is False
    assert CONFIG.allow_margin is False
    assert CONFIG.allow_leverage is False


def test_main_ui_source_does_not_show_wrong_quote_asset() -> None:
    forbidden_quote = "USD" + "T"
    source = Path("src/ui/app.py").read_text(encoding="utf-8")

    assert forbidden_quote not in source
    assert "Einsatz pro Trade (USDC):" in source


def test_ethusdt_context_does_not_change_primary_trading_symbol() -> None:
    source = Path("src/data/binance_candle_downloader.py").read_text(encoding="utf-8")

    assert '"ETHUSDT"' in source
    assert CONFIG.symbol == "ETHUSDC"
    assert CONFIG.quote_asset == "USDC"
