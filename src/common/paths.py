"""Central project paths for the ETHUSDC Bot V2 project."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIGS_DIR = PROJECT_ROOT / "configs"
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
LOGS_DIR = PROJECT_ROOT / "logs"
DOCS_DIR = PROJECT_ROOT / "docs"
MEMORY_BANK_DIR = PROJECT_ROOT / "memory-bank"


def ensure_runtime_dirs() -> None:
    """Create runtime directories that are safe for local project execution."""
    for path in (CONFIGS_DIR, REPORTS_DIR, LOGS_DIR):
        path.mkdir(parents=True, exist_ok=True)
