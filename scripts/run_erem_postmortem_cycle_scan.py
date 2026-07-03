"""Run the EREM post-mortem cycle scan."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.erem_postmortem_cycle_scan import (  # noqa: E402
    EremPostmortemConfig,
    run_erem_postmortem_cycle_scan,
)


def main() -> None:
    report = run_erem_postmortem_cycle_scan(
        EremPostmortemConfig(
            output_dir=Path("reports/research/erem_postmortem_cycle_scan")
        )
    )
    print(
        json.dumps(
            {
                "strategy_version": report["strategy_version"],
                "status": report["status"],
                "cycle_metrics": report["cycle_metrics"],
                "pass_criteria": report["pass_criteria"],
                "decision_summary": report["decision_summary"],
                "output_paths": report["output_paths"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
