import pytest

from src.data.data_catalog import (
    DEFAULT_ETHUSDC_1M_PATH,
    CandleDataCatalogEntry,
    default_ethusdc_1m_catalog_entry,
    get_catalog_path,
    load_data_catalog,
    save_data_catalog,
)


def test_default_entry_is_ethusdc_1m() -> None:
    entry = default_ethusdc_1m_catalog_entry()

    assert entry.symbol == "ETHUSDC"
    assert entry.interval == "1m"


def test_default_path_is_ethusdc_1m_csv() -> None:
    entry = default_ethusdc_1m_catalog_entry()

    assert entry.path == DEFAULT_ETHUSDC_1M_PATH
    assert entry.path == "data/candles/ETHUSDC_1m.csv"


def test_save_and_load_data_catalog() -> None:
    entries = [default_ethusdc_1m_catalog_entry()]

    save_data_catalog(entries)

    assert load_data_catalog() == entries


def test_wrong_symbol_is_rejected() -> None:
    with pytest.raises(ValueError):
        CandleDataCatalogEntry("BTCUSDC", "1m", DEFAULT_ETHUSDC_1M_PATH)


def test_wrong_interval_is_rejected() -> None:
    with pytest.raises(ValueError):
        CandleDataCatalogEntry("ETHUSDC", "5m", DEFAULT_ETHUSDC_1M_PATH)


def test_empty_path_is_rejected() -> None:
    with pytest.raises(ValueError):
        CandleDataCatalogEntry("ETHUSDC", "1m", "")


def test_path_traversal_is_rejected() -> None:
    with pytest.raises(ValueError):
        CandleDataCatalogEntry("ETHUSDC", "1m", "../unsafe.csv")


def test_missing_catalog_is_file_not_found_error() -> None:
    catalog_path = get_catalog_path()
    backup_path = catalog_path.with_suffix(".json.test_backup")
    if backup_path.exists():
        backup_path.unlink()
    if catalog_path.exists():
        catalog_path.replace(backup_path)
    try:
        with pytest.raises(FileNotFoundError):
            load_data_catalog()
    finally:
        if backup_path.exists():
            backup_path.replace(catalog_path)


def test_catalog_path_is_under_configs() -> None:
    assert get_catalog_path().name == "data_catalog.json"
    assert get_catalog_path().parent.name == "configs"
