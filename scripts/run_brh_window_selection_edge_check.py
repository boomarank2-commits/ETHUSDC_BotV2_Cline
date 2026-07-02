"""Run training-only BRH window-selection edge pre-check."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.brh_window_selection_edge import (  # noqa: E402
    BrhWindowSelectionEdgeConfig,
    run_brh_window_selection_edge_check,
)


def main() -> None:
    report = run_brh_window_selection_edge_check(
        BrhWindowSelectionEdgeConfig(
            output_dir=Path("reports/research/brh_window_selection_edge")
        )
    )
    print(
        json.dumps(
            {
                "strategy_version": report["strategy_version"],
                "status": report["status"],
                "selected_v1_variant_id": report["selected_v1_variant_id"],
                "passing_variant_count": report["passing_variant_count"],
                "best_training_only_variant_by_window_selection_edge": report[
                    "best_training_only_variant_by_window_selection_edge"
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
