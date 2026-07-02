"""Run the frozen research blindtest for the selected EREM candidate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.erem_frozen_blindtest import (  # noqa: E402
    EremFrozenBlindtestConfig,
    run_erem_frozen_blindtest,
)


def main() -> None:
    report = run_erem_frozen_blindtest(
        EremFrozenBlindtestConfig(output_dir=Path("reports/research/erem_frozen_blindtest"))
    )
    print(
        json.dumps(
            {
                "strategy_version": report["strategy_version"],
                "status": report["status"],
                "candidate_variant": report["candidate_variant"],
                "blindtest_metrics": report["blindtest_metrics"],
                "decision_summary": report["decision_summary"],
                "output_paths": report["output_paths"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
