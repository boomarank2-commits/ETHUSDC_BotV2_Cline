"""Run the EREM training-only exposure-management edge check."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.erem_exposure_edge_check import (  # noqa: E402
    EremConfig,
    run_erem_exposure_edge_check,
)


def main() -> None:
    report = run_erem_exposure_edge_check(
        EremConfig(output_dir=Path("reports/research/erem_exposure_edge_check"))
    )
    print(
        json.dumps(
            {
                "strategy_version": report["strategy_version"],
                "status": report["status"],
                "variant_count": report["variant_count"],
                "passing_variant_count": report["passing_variant_count"],
                "best_training_only_variant": report["best_training_only_variant"],
                "decision_summary": report["decision_summary"],
                "output_paths": report["output_paths"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
