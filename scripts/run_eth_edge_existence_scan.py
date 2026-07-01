"""Run research-only ETH edge existence scan."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.eth_edge_scan import (  # noqa: E402
    EdgeScanConfig,
    run_eth_edge_existence_scan,
)


def main() -> None:
    report = run_eth_edge_existence_scan(
        EdgeScanConfig(output_dir=Path("reports/research/eth_edge_scan"))
    )
    print(
        json.dumps(
            {
                "strategy_version": report["strategy_version"],
                "status": report["status"],
                "edge_candidate_count": report["edge_candidate_count"],
                "reversion_candidate_count": report["reversion_candidate_count"],
                "momentum_candidate_count": report["momentum_candidate_count"],
                "top_edge_candidate": report["edge_candidates"][0]
                if report["edge_candidates"]
                else None,
                "output_paths": report["output_paths"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
