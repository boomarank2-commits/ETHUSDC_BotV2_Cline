from src.common.config import CONFIG
from src.common.paths import (
    CONFIGS_DIR,
    DOCS_DIR,
    LOGS_DIR,
    MEMORY_BANK_DIR,
    PROJECT_ROOT,
    REPORTS_DIR,
    ensure_runtime_dirs,
)


def test_project_paths_point_to_project_root() -> None:
    assert PROJECT_ROOT.name == "ETHUSDC_BotV2_Cline"
    assert CONFIGS_DIR == PROJECT_ROOT / "configs"
    assert DOCS_DIR == PROJECT_ROOT / "docs"
    assert MEMORY_BANK_DIR == PROJECT_ROOT / "memory-bank"


def test_ensure_runtime_dirs_creates_required_runtime_dirs() -> None:
    ensure_runtime_dirs()

    assert CONFIGS_DIR.is_dir()
    assert REPORTS_DIR.is_dir()
    assert LOGS_DIR.is_dir()


def test_config_contains_confirmed_market_basis() -> None:
    assert CONFIG.symbol == "ETHUSDC"
    assert CONFIG.quote_asset == "USDC"
    assert CONFIG.exchange == "Binance Spot"
    assert CONFIG.long_only is True


def test_config_forbids_non_spot_long_only_modes() -> None:
    assert CONFIG.allow_short is False
    assert CONFIG.allow_futures is False
    assert CONFIG.allow_margin is False
    assert CONFIG.allow_leverage is False


def test_config_contains_training_and_blindtest_windows() -> None:
    assert CONFIG.training_days == 730
    assert CONFIG.blindtest_days == 365


def test_config_forbids_blindtest_learning() -> None:
    assert CONFIG.allow_blindtest_learning is False


def test_config_forbids_early_capital_stop() -> None:
    assert CONFIG.allow_early_capital_stop is False
