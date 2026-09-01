"""Summarize detection_accuracy_log.csv into a precision/recall report.

The CSV is written continuously by LustraApp.log_detection_accuracy() while
the sim runs: every frame the detector is loaded, it checks (via the
PyBullet segmentation buffer) which known fire clusters are actually
visible, and compares that to whether YOLO reported a fire, producing a
TP/FP/FN/TN outcome per frame.
"""

from __future__ import annotations

import csv
import os
from collections import Counter
from dataclasses import dataclass
from typing import List

from lustra.config import get_project_paths

# A new sim run starts a new "session" in the CSV (rows are appended across
# runs, never overwritten). Detected by a timestamp gap or a frame-number
# reset. Sessions shorter than this are treated as aborted test runs and
# excluded from the report.
SESSION_GAP_SECONDS = 30.0
MIN_SESSION_ROWS = 100


@dataclass
class DetectionRow:
    timestamp_unix: float
    frame: int
    true_fire_visible: bool
    visible_fire_names: str
    yolo_fire_detected: bool
    yolo_fire_count: int
    yolo_max_conf: float
    outcome: str


def read_rows(csv_path: str) -> List[DetectionRow]:
    rows: List[DetectionRow] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(
                DetectionRow(
                    timestamp_unix=float(r["timestamp_unix"]),
                    frame=int(r["frame"]),
                    true_fire_visible=bool(int(r["true_fire_visible"])),
                    visible_fire_names=r["visible_fire_names"],
                    yolo_fire_detected=bool(int(r["yolo_fire_detected"])),
                    yolo_fire_count=int(r["yolo_fire_count"]),
                    yolo_max_conf=float(r["yolo_max_conf"]),
                    outcome=r["outcome"],
                )
            )
    return rows


def split_sessions(rows: List[DetectionRow]) -> List[List[DetectionRow]]:
    sessions: List[List[DetectionRow]] = []
    current: List[DetectionRow] = []
    for row in rows:
        if current:
            prev = current[-1]
            new_session = (
                row.timestamp_unix - prev.timestamp_unix > SESSION_GAP_SECONDS
                or row.frame < prev.frame
            )
            if new_session:
                sessions.append(current)
                current = []
        current.append(row)
    if current:
        sessions.append(current)
    return sessions


def format_report(rows: List[DetectionRow], active_span_seconds: float = None) -> str:
    if not rows:
        return "Detection accuracy report: no rows logged yet -- run the sim with the detector loaded first."

    counts = Counter(r.outcome for r in rows)
    tp, fp, fn, tn = counts["TP"], counts["FP"], counts["FN"], counts["TN"]
    n = len(rows)

    precision = tp / (tp + fp) if (tp + fp) > 0 else float("nan")
    recall = tp / (tp + fn) if (tp + fn) > 0 else float("nan")
    f1 = (
        2 * precision * recall / (precision + recall)
        if (tp + fp) > 0 and (tp + fn) > 0 and (precision + recall) > 0
        else float("nan")
    )
    accuracy = (tp + tn) / n

    tp_confs = [r.yolo_max_conf for r in rows if r.outcome == "TP"]
    fp_confs = [r.yolo_max_conf for r in rows if r.outcome == "FP"]

    if active_span_seconds is None:
        active_span_seconds = max(r.timestamp_unix for r in rows) - min(r.timestamp_unix for r in rows)

    lines = [
        "Detection accuracy report (simulator ground truth via segmentation buffer)",
        "=" * 76,
        f"Frames logged: {n}   Active session time: {active_span_seconds:.1f} s",
        "",
        "Confusion matrix (frame-level: was a known fire body visible vs. did YOLO fire):",
        f"  TP (fire visible, detected):     {tp:6d}",
        f"  FN (fire visible, missed):       {fn:6d}",
        f"  FP (nothing visible, detected):  {fp:6d}",
        f"  TN (nothing visible, quiet):     {tn:6d}",
        "",
        "Summary statistics:",
        f"  Precision: {precision:.4f}" if precision == precision else "  Precision: n/a (no detections fired)",
        f"  Recall:    {recall:.4f}" if recall == recall else "  Recall:    n/a (fire never visible)",
        f"  F1:        {f1:.4f}" if f1 == f1 else "  F1:        n/a",
        f"  Accuracy:  {accuracy:.4f}",
    ]
    if tp_confs:
        lines.append(f"  Mean YOLO confidence on TP frames: {sum(tp_confs) / len(tp_confs):.4f}")
    if fp_confs:
        lines.append(f"  Mean YOLO confidence on FP frames: {sum(fp_confs) / len(fp_confs):.4f}")
    return "\n".join(lines)


def main() -> None:
    paths = get_project_paths()
    csv_path = os.path.join(paths.captured_images_dir, "detection_accuracy_log.csv")
    report_path = os.path.join(paths.root_dir, "detection_accuracy_report.txt")

    all_rows = read_rows(csv_path) if os.path.exists(csv_path) else []
    sessions = split_sessions(all_rows)

    kept_sessions = [s for s in sessions if len(s) >= MIN_SESSION_ROWS]
    dropped_sessions = [s for s in sessions if len(s) < MIN_SESSION_ROWS]

    session_lines = [
        "Sessions (split on timestamp gap > "
        f"{SESSION_GAP_SECONDS:.0f}s or frame reset):",
    ]
    for i, s in enumerate(sessions, start=1):
        status = "kept" if len(s) >= MIN_SESSION_ROWS else "DROPPED (< min rows, test run)"
        t0, t1 = s[0].timestamp_unix, s[-1].timestamp_unix
        c = Counter(r.outcome for r in s)
        session_lines.append(
            f"  Session {i}: frames={s[0].frame}-{s[-1].frame}  n={len(s):4d}  span={t1 - t0:6.1f}s"
            f"  TP={c['TP']:4d} FN={c['FN']:4d} FP={c['FP']:4d} TN={c['TN']:4d}  [{status}]"
        )
    session_lines.append(
        f"Kept {len(kept_sessions)}/{len(sessions)} sessions "
        f"({sum(len(s) for s in kept_sessions)} rows; "
        f"dropped {sum(len(s) for s in dropped_sessions)} rows from "
        f"{len(dropped_sessions)} short test session(s))."
    )

    kept_rows = [row for s in kept_sessions for row in s]
    active_span_seconds = sum(s[-1].timestamp_unix - s[0].timestamp_unix for s in kept_sessions)
    report = format_report(kept_rows, active_span_seconds=active_span_seconds)
    report += "\n\n" + "\n".join(session_lines)
    report += f"\n\nRaw per-frame log: {csv_path}\n"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"\nWrote {report_path}")


if __name__ == "__main__":
    main()
