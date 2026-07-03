"""Run the BEV-L v1 volatility-divergence training-only existence scan."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.bev_l_v1_divergence_scan import (  # noqa: E402
    BevConfig,
    run_bev_l_v1_divergence_scan,
)


def main() -> None:
    report = run_bev_l_v1_divergence_scan(
        BevConfig(output_dir=Path("reports/research/bev_l_v1_divergence_scan"))
    )
    print(
        json.dumps(
            {
                "strategy_version": report["strategy_version"],
                "status": report["status"],
                "passing_horizon_count": report["passing_horizon_count"],
                "decision_summary": report["decision_summary"],
                "output_paths": report["output_paths"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
