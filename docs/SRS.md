# SRS — Baldur Posture Recognition v1.0

Status: ACCEPTED (promoted from `instruction/SRS.md` grill draft v1.0, Rounds 1+2 closed).
Scope: Recognition only. Warning UI + Oratory deferred, except frozen JSON-lines interface.
Sources: `project.md`, `CONTEXT.md`, `docs/adr/0001-0003`, `instruction/workflow.md`, `instruction/standards.md`.
Context7 grounding (fetched 2026-09-23):
- `/ultralytics/ultralytics` — YOLO26-pose, webcam stream, keypoints access
- `/dotnet/wpf` — `Window.Topmost`, `ShowDialog` modal
- `/jupyter/notebook` — notebook-as-module pattern

## 1. Purpose

Desk-worker posture monitoring from a local webcam. Recognition scores upright posture in real time and emits posture events. No UI in this scope.

## 2. Scope

In scope (Recognition):
- Check camera permission, open single webcam `source=0`.
- Detect single Person (largest person if multiple).
- Estimate pose keypoints via Ultralytics pose model.
- Compute posture score 0–100 per frame, in memory only.
- Apply valid-range + dwell-time hysteresis, emit JSON-lines events on stdout.

Out of scope (deferred, contract only):
- Warning: WPF fullscreen popup + optional mouse block (ESC clears). Build deferred, interface frozen.
- Oratory skills enhancer: separate grill, no tickets in this SRS.
- `.py` conversion + WPF child-process integration: separate tickets later. Deliverable now = `.ipynb`.

Hard constraints (ADR-0001, ADR-0002):
- Windows-only, local inference only. No cloud.
- No persistence: no image/video/keypoint/score storage. In-memory current frame + score only.

## 3. Definitions (from `CONTEXT.md` — use verbatim)

- **Person**: A single human detected in the camera frame and tracked for scoring.
- **Pose keypoints**: YOLO pose outputs per person (`xy`, `xyn`, `data` with visibility).
- **Posture score**: A 0–100 number from ear-shoulder verticality plus shoulder symmetry where higher means more upright.
- **Valid range**: Scores at or above 70 are upright; recovery requires reaching 80 to stop flapping.
- **Dwell time**: Continuous seconds outside valid range before emitting `bad_posture` (10s) or confirming `recovered` (3s).
- **Recognition**: The Python YOLO stage that captures movement and emits posture events. No UI.
- **Warning**: The deferred WPF stage that shows the fullscreen popup. Not part of this build.

## 4. Assumptions / Decisions

- A1: This SRS covers Recognition only. Warning UI + Oratory deferred, except frozen JSON-lines interface: `bad_posture, recovered, heartbeat, error`.
- A2: Model = Ultralytics `yolo26n-pose.pt` family, fallback to latest stable `*-pose.pt` if v26 wheel not installable on Windows (ADR-0003).
- A3: Deliverable now = `.ipynb` (`00_env_camera`, `01_pose_score`, `02_events_jsonl`). `engine.py` conversion = separate ticket.
- A4: Hard constraints: Windows-only local, no image/video persistence, in-memory keypoints + score only.

## 5. Functional requirements

### FR-1 Camera input
- REQ-1.1: Open single webcam `source=0` with `stream=True` generator.
- REQ-1.2: Permission check first; on denial emit `error` event, do not retry-loop blindly.
- REQ-1.3: Measure FPS in env spike; pin `ultralytics`, `torch (CPU/CUDA)`, `opencv-python` versions in notebook header.

### FR-2 Person + pose keypoints (Context7: `/ultralytics/ultralytics`)
- REQ-2.1: Load official weights: `YOLO("yolo26n-pose.pt")`.
- REQ-2.2: Iterate `results = model(source=0, stream=True)`; per result read `r.keypoints.xy`, `r.keypoints.xyn`, `r.keypoints.data`.
- REQ-2.3: Largest-person policy if multiple Person instances in frame.
- REQ-2.4: Empty keypoints or low-visibility frames → neutral (hold last state, never emit `bad_posture` directly).
- REQ-2.5: Do not use `show=True` in headless scoring loop.

Reference pattern (do not invent wrappers):

```python
from ultralytics import YOLO
model = YOLO("yolo26n-pose.pt")
results = model(source=0, stream=True)
for r in results:
    xy = r.keypoints.xy
    xyn = r.keypoints.xyn
    kpts = r.keypoints.data
```

### FR-3 Posture score v1
- REQ-3.1: Score 0–100 = ear-shoulder verticality + shoulder symmetry. Higher = more upright.
- REQ-3.2: Valid range: `score >= 70` upright. `score < 70` outside valid range.
- REQ-3.3: Recovery hysteresis: must reach `score >= 80` to confirm `recovered`.
- REQ-3.4: Calibration in `01_pose_score.ipynb` on real desk postures; no magic-dependent logic inside scoring functions (importable cells).

### FR-4 Dwell time + events
- REQ-4.1: `bad_posture` only after continuous 10s outside valid range.
- REQ-4.2: `recovered` only after continuous 3s at/above 80 after a `bad_posture`.
- REQ-4.3: `heartbeat` every 5s regardless of state.
- REQ-4.4: `error` on camera/model failures with machine-readable message; never crash silently.
- REQ-4.5: stdout carries ONLY JSON-lines events. No logs, no scores, no debug prints on stdout.

Frozen event interface:

```json
{"event":"bad_posture","score":64,"dwell_s":10}
{"event":"recovered","score":82,"dwell_s":3}
{"event":"heartbeat","score":78}
{"event":"error","code":"CAMERA_DENIED","message":"..."}
```

### FR-5 Notebook delivery (Context7: `/jupyter/notebook`)
- REQ-5.1: One concern per cell; scoring functions importable (NotebookLoader exec-cells-as-module pattern).
- REQ-5.2: Conversion path (deferred ticket): `jupyter nbconvert --to script recognition.ipynb --output engine.py`, then harden `if __name__ == "__main__"` stdout loop.
- REQ-5.3: Phases: `00_env_camera` → `01_pose_score` → `02_events_jsonl`.

## 6. Non-functional requirements

- NFR-1 Privacy: ADR-0002 — no persistence, memory-only scoring.
- NFR-2 Platform: ADR-0001 — Windows-only local; WPF host is Windows-only.
- NFR-3 Performance: CPU baseline must sustain real-time scoring; CUDA optional. Target FPS set after env spike.
- NFR-4 Robustness: low-light / occlusion → neutral, not flapping events.
- NFR-5 Coding standards: per `instruction/coding_standards.md` + `standards.md` (atomic shredding, grill-first, TDD per ticket in Phase 5).

## 7. Warning contract (frozen, deferred build — Context7: `/dotnet/wpf`)

Recognition does not build this; WPF host must honor:

- Launch: `System.Diagnostics.Process` with `UseShellExecute=false, RedirectStandardOutput=true`, async `OutputDataReceived` JSON-lines parse, `Dispatcher.Invoke` to show/hide.
- Window: `WindowState="Maximized" WindowStyle="None" Topmost="True"` (`Window.Topmost` WS_EX_TOPMOST), modal via `Window.ShowDialog()` (blocks caller, disables other windows on thread).
- Config `mouseBlocking:true/false`; ESC always clears block/closes (WPF `IsCancel` / `KeyDown` → `DialogResult=false`).
- Mouse block API choice, config file location, multi-monitor behavior: open decisions for Warning tickets, not this SRS.

## 8. Acceptance criteria

- AC-1: Notebook opens `source=0`, streams, prints only frozen events.
- AC-2: 10s slouch → exactly one `bad_posture`; 3s upright ≥80 → `recovered`; no flap in between.
- AC-3: No-person / occluded frames produce no false `bad_posture`.
- AC-4: `heartbeat` every 5s ± tolerance.
- AC-5: No files written (images, video, keypoints, scores) during run.
- AC-6: Test scenarios shredded to atomic processes per `workflow.md:2-4`, saved to `infrastructure/test/test_scenarios_YYYY_MM_DD_hh_mm.txt`, manual confirm gate before code.

## 9. Roadmap (from grill draft)

- Phase 0 DONE: skills setup, `AGENTS.md`, issue-tracker/domain/triage docs. NOTE: `gh` CLI still missing — install + `gh auth login` before `to-spec/to-tickets`.
- Phase 1: `CONTEXT.md` + ADR-0001/0002/0003 — DONE.
- Phase 2: Env spike `00_env_camera.ipynb`.
- Phase 3: Scoring spike `01_pose_score.ipynb` (`prototype` detour if formula unsettled).
- Phase 4: Event loop `02_events_jsonl.ipynb`.
- Phase 5: `to-spec` → `to-tickets` → `implement` (TDD).
- Phase 6 (later): Oratory — separate grill.

## 10. Open decisions (blocking spec, not SRS)

Score-formula weights, multi-person beyond largest, low-light/occlusion thresholds, CPU vs CUDA target FPS, camera-permission UX text, WPF mouse-block API, config location, multi-monitor fullscreen.
