"""Run the strict BRH/ERV selection robustness gatekeeper."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.brh_selection_edge_robustness_v2check import (  # noqa: E402
    BrhSelectionRobustnessConfig,
    run_brh_selection_edge_robustness_v2check,
)


def main() -> None:
    report = run_brh_selection_edge_robustness_v2check(
        BrhSelectionRobustnessConfig(
            output_dir=Path("reports/research/brh_selection_edge_robustness_v2check")
        )
    )
    print(
        json.dumps(
            {
                "strategy_version": report["strategy_version"],
                "status": report["status"],
                "selected_v1_variant_id": report["selected_v1_variant_id"],
                "passing_variant_count": report["passing_variant_count"],
                "best_training_only_variant_after_robustness_gatekeeper": report[
                    "best_training_only_variant_after_robustness_gatekeeper"
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
