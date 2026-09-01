ohhhSTATUS: Implemented 2026-08-17. See "Implementation" section at the bottom.

# Accuracy Reports — Plan / Handoff Notes

Context: user is resetting their laptop and wants to pick this up in a new session.
This file captures the goal, what's already in the repo, and the open questions
that still need answers before implementation starts.

## Goal

User wants accuracy reports for **detection**, **tracking/localization**, and
**spread prediction** — same style as the existing `distance_measurements_report.txt`.

## Reference: how the existing distance report works

- `lustra/app.py` — in the running sim (Panda3D), pressing a key while hovering
  the mouse triggers `process_click()`, which reads the simulator's known true
  ground-truth range (via raycast hit point) and compares it to the stereo-vision
  estimated range at that pixel.
- Each click is logged as a row to `captured_images/clicked_depth_comparisons.csv`
  (frame, pixel, estimated range, true range, abs/rel error, eye/hit world coords).
- `distance_measurements_report.txt` is a manually-produced summary table + stats
  (n=50, mean abs error 0.990 m, mean rel error 2.533%, min/max abs error) derived
  from that CSV. No script for generating this summary was found in-repo — it
  appears to have been produced ad hoc from the CSV.

## Existing infra relevant to the other three reports

- **Detection** — `lustra/vision/detection.py`: thin `YoloDetector` wrapper
  around an Ultralytics YOLO model (`last.pt` at repo root). No accuracy harness
  exists yet.
- **Tracking/localization** — `lustra/vision/fire_tracker.py`: `FireTracker`
  builds per-track evidence grids from detections + stereo-projected polygons,
  tracks id/hits/confidence over time, exports GeoJSON. No ground-truth
  comparison exists yet.
- **Spread prediction** — `lustra/prediction/validation.py`: already has
  - `REFERENCE_SCENARIOS` / `run_all_reference_scenarios()` — checks Rothermel
    `compute_spread()` ROS output against literature-derived expected bands
    (pass/fail), with `format_report()` producing text output.
  - `sorensen_index()` — Dice/Sorensen similarity between a predicted fire
    perimeter ring and an observed one (lon/lat polygons), for scoring
    predicted-vs-observed spread over time.
  - Nothing currently wires this into a saved report file the way
    `distance_measurements_report.txt` exists for distance.

## Open questions (asked via AskUserQuestion, not yet answered)

### 1. Detection accuracy — where should ground truth come from?
- (a) **Simulator ground truth**: since the world is a Panda3D sim with known
  fire object placements, log whether YOLO fired when a known fire body was in
  view → precision/recall/false pos/neg, same click-driven style as distance.
- (b) **Manual labeled frames**: periodically save frames, user labels boxes
  after the fact, compare YOLO boxes to labels via IoU → precision/recall,
  standard ML-eval style.
- (c) **Existing YOLO val set only**: if `last.pt`'s training already has a
  val split, just run YOLO's built-in validation (mAP/precision/recall) —
  no new sim instrumentation needed.

### 2. Tracking/localization accuracy — what's being measured?
- (a) **Position error**: compare each `FireTrack` centroid/polygon (world XY)
  against the simulator's true fire body position over time — meters-error
  style like the distance report.
- (b) **Track stability / ID consistency**: ID switches, track fragmentation,
  time-to-confirm (hits reaching `min_hits`), track lifetime vs true fire
  lifetime — MOT-style tracking metrics.
- (c) **Both** combined into one report.

### 3. Spread prediction accuracy — what should the report be based on?
- (a) **Existing reference-scenario suite only**: wire up
  `run_all_reference_scenarios()` to produce a saved report file (pass/fail vs
  literature ROS bands), same style as the other reports.
- (b) **Sim-based perimeter comparison**: run the spread prediction against
  actual simulated fire growth in-world, score with `sorensen_index()` over
  time (predicted vs observed perimeter overlap).
- (c) **Both** — reference suite for physics sanity + sim-based perimeter
  comparison for real predictive accuracy.

## Next step

When resuming: ask the user to pick an option (or describe their own approach)
for each of the three questions above, then design + implement the
corresponding instrumentation/report-generation code, following the existing
distance-report pattern (CSV log during a live sim run → summary stats file).

## Implementation (2026-08-17)

User picked: detection = (a) simulator ground truth, tracking = (c) both,
spread = (a) reference-scenario suite only.

- `lustra/accuracy/ground_truth.py` — `FIRE_SPAWN_SPECS`, the single source
  of truth for the three fire clusters' spawn params (previously hardcoded
  inline 3x in `setup_simulation()`). `radius_m` = `max_scale / 2` (the
  center sprite dominates each cluster's visible extent).
- `lustra/app.py`:
  - `setup_simulation()` now loops over `FIRE_SPAWN_SPECS`, capturing each
    cluster's spawned PyBullet body ids into `self.fire_ground_truth`.
  - `log_detection_accuracy()` — called every frame the detector is ready.
    Uses the segmentation buffer (not a frustum check) to determine true
    fire visibility, so occlusion is handled for free. Frame-level TP/FP/FN/TN
    vs whether YOLO fired, appended to `captured_images/detection_accuracy_log.csv`.
  - `log_tracking_accuracy()` — called once per fire-map tick (~1 Hz, same
    cadence as `fire_state.json` writes). Logs every fire_tracker track
    (confirmed or not) with its nearest ground-truth cluster and distance to
    `captured_images/tracking_accuracy_log.csv`.
- `lustra/accuracy/detection_report.py`, `tracking_report.py`, `spread_report.py`
  — read the CSVs (or, for spread, just run the existing reference suite) and
  write `detection_accuracy_report.txt`, `tracking_accuracy_report.txt`,
  `spread_prediction_accuracy_report.txt` at repo root. Tracking report derives
  ID switches / fragmentation / time-to-confirm / position error by
  re-grouping the raw per-tick rows by ground-truth cluster (capture radius =
  3x true radius) — no live event detection needed in the instrumentation.
- Root entry scripts (`generate_detection_report.py`, `generate_tracking_report.py`,
  `generate_spread_report.py`) mirror `main.py`'s thin-wrapper style.
- Verified: `generate_spread_report.py` runs end-to-end (5/5 reference
  scenarios pass). Detection/tracking report logic verified against synthetic
  CSVs (not a live sim run — needs `python main.py` with fires in view to
  produce real data first).
