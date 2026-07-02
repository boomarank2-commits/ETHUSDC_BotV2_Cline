"""Run diagnostic-only BRH/ERV-v1 post-mortem."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.brh_v1_diagnostics import (  # noqa: E402
    BrhDiagnosticConfig,
    run_brh_v1_diagnostics,
)


def main() -> None:
    report = run_brh_v1_diagnostics(
        BrhDiagnosticConfig(output_dir=Path("reports/research/brh_v1_diag"))
    )
    print(
        json.dumps(
            {
                "strategy_version": report["strategy_version"],
                "status": report["status"],
                "selected_variant_id": report["selected_variant_id"],
                "thresholds_training_only": report["threshold_source_verification"][
                    "matches_recalculated_training_only_thresholds"
                ],
                "decision_summary": report["decision_summary"],
                "output_paths": report["output_paths"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
