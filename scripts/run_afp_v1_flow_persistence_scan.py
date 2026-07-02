"""Run the AFP-v1 training-only aggregate-flow persistence scan."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.afp_v1_flow_persistence_scan import (  # noqa: E402
    AfpConfig,
    run_afp_v1_flow_persistence_scan,
)


def main() -> None:
    report = run_afp_v1_flow_persistence_scan(
        AfpConfig(output_dir=Path("reports/research/afp_v1_flow_persistence_scan"))
    )
    print(
        json.dumps(
            {
                "strategy_version": report["strategy_version"],
                "status": report["status"],
                "agg_trade_completeness": report["agg_trade_completeness"],
                "sanity_check": {
                    "status": report["sanity_check"]["status"],
                    "passing_folds": report["sanity_check"].get("passing_folds"),
                    "required_passing_folds": report["sanity_check"].get(
                        "required_passing_folds"
                    ),
                    "sanity_pass": report["sanity_check"]["sanity_pass"],
                },
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
