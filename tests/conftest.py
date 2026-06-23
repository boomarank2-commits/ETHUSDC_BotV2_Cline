"""Test runtime isolation for project-local files."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


TEST_PROJECT_ROOT = Path(
    os.environ.get("PYTEST_CURRENT_TEST_ROOT", tempfile.mkdtemp(prefix="ethusdc_botv2_tests_"))
)
TEST_PROJECT_ROOT = TEST_PROJECT_ROOT.resolve()

os.environ.setdefault("ETHUSDC_BOTV2_PROJECT_ROOT", str(TEST_PROJECT_ROOT))

for relative in ("configs", "data", "reports", "logs"):
    (TEST_PROJECT_ROOT / relative).mkdir(parents=True, exist_ok=True)