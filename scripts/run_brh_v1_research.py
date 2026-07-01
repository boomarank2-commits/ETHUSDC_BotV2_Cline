"""Run research-only BRH/ERV-v1 walkforward study."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.brh_v1 import BrhConfig, run_brh_v1_research  # noqa: E402


def main() -> None:
    report = run_brh_v1_research(
        BrhConfig(output_dir=Path("reports/research/brh_v1"))
    )
    print(
        json.dumps(
            {
                "strategy_version": report["strategy_version"],
                "status": report["status"],
                "eligible_variant_count": report["eligible_variant_count"],
                "blindtest_candidate_count_evaluated": report[
                    "blindtest_candidate_count_evaluated"
                ],
                "selected_variant": report["selected_variant"],
                "blindtest_summary": report["blindtest_summary"],
                "output_paths": report["output_paths"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
