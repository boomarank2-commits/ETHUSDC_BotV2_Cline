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


def test_no_wrong_symbol_in_source_tests_docs_or_readme() -> None:
    forbidden_symbol = "ETH" + "USD" + "T"
    paths = list(Path("src").rglob("*.py"))
    paths += list(Path("tests").rglob("*.py"))
    paths += list(Path("docs").rglob("*.md"))
    if Path("README.md").exists():
        paths.append(Path("README.md"))

    for path in paths:
        assert forbidden_symbol not in path.read_text(encoding="utf-8")
