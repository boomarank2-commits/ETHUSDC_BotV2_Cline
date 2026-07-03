"""Run the BELL-v1 BTC->ETH lead-lag/catch-up training-only scan."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.bell_v1_leadlag_scan import (  # noqa: E402
    BellConfig,
    run_bell_v1_leadlag_scan,
)


def main() -> None:
    report = run_bell_v1_leadlag_scan(
        BellConfig(output_dir=Path("reports/research/bell_v1_leadlag_scan"))
    )
    print(
        json.dumps(
            {
                "strategy_version": report["strategy_version"],
                "status": report["status"],
                "sanity_status": report["sanity_scan"]["sanity_status"],
                "variant_count": report["variant_count"],
                "eligible_variant_count": report["eligible_variant_count"],
                "selected_training_only_variant": report[
                    "selected_training_only_variant"
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
