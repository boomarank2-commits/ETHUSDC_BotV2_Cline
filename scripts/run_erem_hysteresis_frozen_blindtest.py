"""Run the frozen EREM hysteresis research blindtest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.erem_hysteresis_frozen_blindtest import (  # noqa: E402
    EremHysteresisFrozenConfig,
    run_erem_hysteresis_frozen_blindtest,
)


def main() -> None:
    report = run_erem_hysteresis_frozen_blindtest(
        EremHysteresisFrozenConfig(
            output_dir=Path("reports/research/erem_hysteresis_frozen_blindtest")
        )
    )
    print(
        json.dumps(
            {
                "strategy_version": report["strategy_version"],
                "status": report["status"],
                "candidate_overlay": report["candidate_overlay"],
                "base_erem_blindtest_metrics": report["base_erem_blindtest_metrics"],
                "hysteresis_blindtest_metrics": report[
                    "hysteresis_blindtest_metrics"
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
