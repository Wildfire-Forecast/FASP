"""Run the Rothermel reference-scenario suite and save it as a report.

Unlike the detection/tracking reports, this doesn't need a live sim run --
lustra.prediction.validation.REFERENCE_SCENARIOS checks compute_spread()
output against literature-derived rate-of-spread bands directly.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from lustra.config import get_project_paths
from lustra.prediction.validation import format_report, run_all_reference_scenarios


def main() -> None:
    paths = get_project_paths()
    report_path = os.path.join(paths.root_dir, "spread_prediction_accuracy_report.txt")

    results = run_all_reference_scenarios()
    n_pass = sum(1 for r in results if r.passed)
    n_total = len(results)

    header = (
        "Spread prediction accuracy report (Rothermel reference-scenario suite)\n"
        + "=" * 76
        + f"\nGenerated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n"
        f"Scenarios passed: {n_pass}/{n_total}\n\n"
    )
    body = format_report(results)
    footer = (
        "\n\nEach scenario computes compute_spread() rate-of-spread for a fixed "
        "fuel/weather/slope combination and checks it against a literature-derived "
        "expected band (see REFERENCE_SCENARIOS in lustra/prediction/validation.py "
        "for citations). PASS means the model's ROS falls within that band.\n"
    )
    report = header + body + footer

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
