"""Summarize tracking_accuracy_log.csv into a position-error + stability report.

The CSV is written once per fire-map tick (~1 Hz, see LustraApp.update_fire_map
-> log_tracking_accuracy) by LustraApp: for every active FireTrack it records
the nearest ground-truth fire cluster and the world-space distance to it.
This script re-groups those rows by ground-truth cluster and derives:

  - position error (how far the track centroid sits from the true cluster)
  - coverage (fraction of ticks where some track was near the cluster)
  - time-to-confirm (ticks from first evidence to track.hits >= min_hits)
  - ID switches / fragmentation (MOT-style track-identity stability)

"Coverage" and "which track belongs to which fire" are both defined by a
capture radius of 3x the cluster's true radius -- outside that, a track is
considered to be tracking something else (or nothing).
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List

from lustra.config import get_project_paths

CAPTURE_RADIUS_MULT = 3.0


@dataclass
class TrackingRow:
    timestamp_unix: float
    gt_name: str
    gt_center_x: float
    gt_center_y: float
    gt_radius_m: float
    track_id: int
    hits: int
    confirmed: bool
    confidence: float
    age_s: float
    centroid_x: float
    centroid_y: float
    center_distance_m: float
    position_error_m: float


def read_rows(csv_path: str) -> List[TrackingRow]:
    rows: List[TrackingRow] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(
                TrackingRow(
                    timestamp_unix=float(r["timestamp_unix"]),
                    gt_name=r["gt_name"],
                    gt_center_x=float(r["gt_center_x"]),
                    gt_center_y=float(r["gt_center_y"]),
                    gt_radius_m=float(r["gt_radius_m"]),
                    track_id=int(r["track_id"]),
                    hits=int(r["hits"]),
                    confirmed=bool(int(r["confirmed"])),
                    confidence=float(r["confidence"]),
                    age_s=float(r["age_s"]),
                    centroid_x=float(r["centroid_x"]),
                    centroid_y=float(r["centroid_y"]),
                    center_distance_m=float(r["center_distance_m"]),
                    position_error_m=float(r["position_error_m"]),
                )
            )
    return rows


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def _format_cluster(gt_name: str, rows: List[TrackingRow]) -> List[str]:
    rows = sorted(rows, key=lambda r: r.timestamp_unix)
    radius_m = rows[0].gt_radius_m
    capture_radius = radius_m * CAPTURE_RADIUS_MULT

    covered = [r for r in rows if r.center_distance_m <= capture_radius]
    confirmed_covered = [r for r in covered if r.confirmed]

    n_ticks = len(rows)
    n_covered = len(covered)
    coverage_pct = 100.0 * n_covered / n_ticks if n_ticks else float("nan")

    lines = [
        f"[{gt_name}]  true radius={radius_m:.1f} m  capture radius={capture_radius:.1f} m",
        f"  Ticks logged: {n_ticks}   Covered (a track within capture radius): {n_covered} ({coverage_pct:.1f}%)",
    ]

    if confirmed_covered:
        errs = [r.position_error_m for r in confirmed_covered]
        lines.append(
            f"  Position error (confirmed tracks, m): mean={_mean(errs):.2f}  "
            f"median={sorted(errs)[len(errs) // 2]:.2f}  min={min(errs):.2f}  max={max(errs):.2f}"
        )
    else:
        lines.append("  Position error: n/a (no confirmed track ever came within capture radius)")

    # Identity-stability sequence: the covered track id at each tick, in time
    # order. Collapsing out the not-covered ticks means a track blinking out
    # for one tick and right back in with the same id isn't counted as a
    # switch -- only an actual change of track_id while covered is.
    covered_flags = [r.center_distance_m <= capture_radius for r in rows]
    compact = [r.track_id for r, is_covered in zip(rows, covered_flags) if is_covered]
    id_switches = sum(1 for a, b in zip(compact, compact[1:]) if a != b)

    fragments = 0
    prev_state = False
    for is_covered in covered_flags:
        if is_covered and not prev_state:
            fragments += 1
        prev_state = is_covered
    lines.append(f"  ID switches while covered: {id_switches}   Coverage segments (fragmentation): {fragments}")

    if covered:
        first_seen_s = min(r.timestamp_unix for r in rows)
        first_confirmed = [r for r in confirmed_covered]
        if first_confirmed:
            t_confirm = min(r.timestamp_unix for r in first_confirmed) - first_seen_s
            lines.append(f"  Time-to-confirm (first log tick -> first confirmed+covered tick): {t_confirm:.1f} s")
        else:
            lines.append("  Time-to-confirm: n/a (never confirmed while covered)")

    return lines


def format_report(rows: List[TrackingRow]) -> str:
    if not rows:
        return "Tracking accuracy report: no rows logged yet -- run the sim with fires visible first."

    by_gt: Dict[str, List[TrackingRow]] = defaultdict(list)
    for r in rows:
        by_gt[r.gt_name].append(r)

    lines = [
        "Tracking accuracy report (position error + ID stability vs. sim ground truth)",
        "=" * 82,
        f"Ticks logged: {len(rows)}   Ground-truth fire clusters seen: {len(by_gt)}",
        "",
    ]
    for gt_name in sorted(by_gt):
        lines.extend(_format_cluster(gt_name, by_gt[gt_name]))
        lines.append("")

    with_confirmed = [
        r for r in rows if r.confirmed and r.center_distance_m <= r.gt_radius_m * CAPTURE_RADIUS_MULT
    ]
    if with_confirmed:
        errs = [r.position_error_m for r in with_confirmed]
        lines.append(f"Overall mean position error (confirmed, covered ticks): {_mean(errs):.2f} m")
    return "\n".join(lines)


def main() -> None:
    paths = get_project_paths()
    csv_path = os.path.join(paths.captured_images_dir, "tracking_accuracy_log.csv")
    report_path = os.path.join(paths.root_dir, "tracking_accuracy_report.txt")

    rows = read_rows(csv_path) if os.path.exists(csv_path) else []
    report = format_report(rows)
    report += f"\n\nRaw per-tick log: {csv_path}\n"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"\nWrote {report_path}")


if __name__ == "__main__":
    main()
