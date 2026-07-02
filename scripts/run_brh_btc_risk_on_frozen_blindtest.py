"""Run the frozen research blindtest for brh_btc_risk_on_72h."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.brh_btc_risk_on_frozen_blindtest import (  # noqa: E402
    BrhBtcRiskOnFrozenBlindtestConfig,
    run_brh_btc_risk_on_frozen_blindtest,
)


def main() -> None:
    report = run_brh_btc_risk_on_frozen_blindtest(
        BrhBtcRiskOnFrozenBlindtestConfig(
            output_dir=Path("reports/research/brh_btc_risk_on_frozen_blindtest")
        )
    )
    print(
        json.dumps(
            {
                "strategy_version": report["strategy_version"],
                "status": report["status"],
                "candidate_variant_id": report["candidate_variant_id"],
                "blindtest_summary": report["blindtest_summary"],
                "blindtest_concentration": report["blindtest_concentration"],
                "blindtest_buy_hold_baseline": report["blindtest_buy_hold_baseline"],
                "decision_summary": report["decision_summary"],
                "output_paths": report["output_paths"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
