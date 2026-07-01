"""Run ERH-v1 diagnostic-only signal funnel."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.paths import REPORTS_DIR  # noqa: E402
from src.research.erh_v1 import ErhConfig  # noqa: E402
from src.research.erh_v1_diagnostics import run_erh_v1_diagnostics  # noqa: E402


def main() -> None:
    report = run_erh_v1_diagnostics(
        ErhConfig(output_dir=REPORTS_DIR / "research" / "erh_v1_diag")
    )
    print(
        json.dumps(
            {
                "strategy_version": report["strategy_version"],
                "status": report["status"],
                "suspected_root_cause_category": report[
                    "suspected_root_cause_category"
                ],
                "recommended_next_step": report["recommended_next_step"],
                "output_paths": report["output_paths"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
