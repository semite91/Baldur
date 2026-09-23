# SRS - Baldur Posture Recognition - ACCEPTED v1.0

> Status: ACCEPTED. `/grill-with-docs` Rounds 1+2 closed - shared understanding reached for Recognition v1.
> Scope: Recognition-only (`ipynb` first). Warning UI + Oratory deferred. Event interface frozen: `bad_posture/recovered/heartbeat/error`.
> Score v1: ear-shoulder verticality + shoulder symmetry, 0-100, bad if <70 for 10s, recovered if >80 for 3s, heartbeat 5s. Camera: single webcam `source=0`, largest person, empty/low-confidence neutral.

Sources:
- `project.md` - initializer (AI-first, OpenCode harness, posture + deferred oratory)
- `instruction/workflow.md`, `instruction/standards.md`, `instruction/coding_standards.md`
- Context7 MCP:
  - `/ultralytics/ultralytics` - YOLO26 pose, webcam stream, keypoints access
  - `/dotnet/wpf` - Window.Topmost, ShowDialog modal
  - `/jupyter/notebook` - notebook-as-module pattern

## 1. Assumptions (must confirm in grill)

- A1: This SRS covers Recognition only. Warning UI + Oratory deferred, except frozen JSON-lines interface: `bad_posture, recovered, heartbeat, error`.
- A2: Model = Ultralytics `yolo26n-pose.pt` family, fallback to latest stable `*-pose.pt` if v26 wheel not installable on Windows.
- A3: Deliverable now = `.ipynb`. `py` conversion + WPF child-process integration = separate tickets later.
- A4: Hard constraints: Windows-only local, no image/video persistence, in-memory keypoints + score only.

## 2. Glossary (seed for CONTEXT.md, not yet accepted)

- `person` - detected human in camera frame.
- `pose keypoints` - YOLO `result.keypoints.xy / xyn / data (x,y,visibility)`.
- `posture score` - TBD function of keypoints (e.g. neck/shoulder angle). Formula open.
- `valid range` - TBD score interval considered upright. Open.
- `dwell time` - TBD continuous seconds outside valid range before trigger. Open.
- `event` - JSON line on stdout: `bad_posture | recovered | heartbeat | error`.

## 3. Architecture

```
[Webcam] -> [Python YOLO pose scoring, local] --JSON-lines stdout--> [WPF .NET 9 host]
  source=0, stream=True          bad_posture/recovered/         async stdout read
  no store                       heartbeat/error, no store       fullscreen popup + optional mouse block (ESC clears)
```

- Recognition: Jupyter notebook -> `py`. Steps per `project.md`: check camera permission -> detect person -> estimate pose -> capture posture from realtime movement -> score -> dwell check -> emit event.
- Warning (deferred build, contract frozen now): WPF launches `python engine.py` as child `Process` with `RedirectStandardOutput=true`, async read, `WindowState=Maximized, Topmost=true, ShowDialog` modal, config `mouseBlocking:true/false`, ESC disables block.

## 4. Context7-grounded implementation notes

### 4.1 YOLO26-pose (`/ultralytics/ultralytics`)

Confirmed patterns - do not invent wrappers:

```python
from ultralytics import YOLO
model = YOLO("yolo26n-pose.pt")  # official pose weights
results = model(source=0, stream=True)  # webcam generator of Results
for r in results:
    xy = r.keypoints.xy    # pixel coords
    xyn = r.keypoints.xyn  # normalized
    kpts = r.keypoints.data  # x, y, visibility
```

Rules:
- Use `stream=True` for webcam, iterate generator, avoid `show=True` in headless scoring loop.
- Handle no-person frames (empty keypoints) as neutral, not `bad_posture`.
- Pin `ultralytics`, `torch (CPU/CUDA)`, `opencv-python` versions in notebook header after env spike.

### 4.2 WPF Warning (`/dotnet/wpf`)

Confirmed:
- `Window.Topmost` dependency property for always-on-top warning.
- `Window.ShowDialog()` for modal blocking owner.

Roadmap application (deferred tickets):
- `WarningWindow.xaml`: `WindowState="Maximized" WindowStyle="None" Topmost="True"`, `KeyDown` ESC -> close/unblock.
- Host: `System.Diagnostics.Process` with `UseShellExecute=false, RedirectStandardOutput=true`, `OutputDataReceived` async parse JSON lines, `Dispatcher.Invoke` to show/hide window.
- Mouse block: config-gated, low-level hook or `ClipCursor`, ESC always clears. Needs security review.

### 4.3 Jupyter -> py (`/jupyter/notebook`)

- Keep notebooks importable: one concern per cell, no magic-dependent logic in scoring functions (mirrors NotebookLoader exec-cells-as-module pattern).
- Conversion: `jupyter nbconvert --to script recognition.ipynb --output engine.py` then harden `if __name__ == "__main__"` stdout loop. Ticket separately.

## 5. Phased roadmap

- Phase 0 DONE: `setup-matt-pocock-skills` - `AGENTS.md`, `docs/agents/issue-tracker.md (GitHub)`, `domain.md (single-context)`, `triage-labels.md`. NOTE: `gh` CLI still missing - install + `gh auth login` before `to-spec/to-tickets` create issues.
- Phase 1 (next): Close grill Round 1 Q1-Q4 -> write `CONTEXT.md` + ADR-0001 Windows-local, ADR-0002 no-persistence, ADR-0003 YOLO26-pose pin.
- Phase 2: Env spike notebook `00_env_camera.ipynb` - permission check, `source=0` stream, FPS measure, `yolo26n-pose.pt` download. Test scenarios per `workflow.md:2-4` in `infrastructure/test/test_scenarios_YYYY_MM_DD_hh_mm.txt` (manual confirm gate).
- Phase 3: Scoring spike `01_pose_score.ipynb` - keypoint geometry -> `score`, `valid range`, `dwell time` calibration on real desk postures. This is the `prototype` detour if formula can't be settled in conversation.
- Phase 4: Event loop `02_events_jsonl.ipynb` - emit only `bad_posture/recovered/heartbeat/error`, dwell hysteresis, no store audit.
- Phase 5: `to-spec` -> `to-tickets` -> `implement` (TDD per ticket) for `engine.py` conversion + WPF host + fullscreen + mouse-block + ESC.
- Phase 6 (later): Oratory skills part - separate grill, do not mix into posture tickets.

## 6. Test plan (per instruction/workflow.md)

- Test scenarios shredded to atomic processes (e.g. `toggle enable submit` style: `detect person`, `update score`, `emit bad_posture`), saved to `infrastructure/test/test_scenarios_YYYY_MM_DD_hh_mm.txt`, manual confirm before code.
- Review loop steps 6-11, code quality via OpenCodeReview, final accepted doc attached as SRS to PR description.

## 7. Open decisions (blocking spec)

- Q1 scope, Q2 model fallback permission, Q3 ipynb vs py deliverable, Q4 hard constraints.
- Undefined: score formula, valid range numbers, dwell seconds, multi-person policy, low-light / occlusion policy, CPU vs CUDA target FPS, camera permission UX text.
- WPF detail: mouse-block API choice, config file location, fullscreen multi-monitor behavior.

## 8. Next action

Answer grill Q1-Q4. Then I finalize `CONTEXT.md` + ADRs and promote this DRAFT to accepted SRS for `to-spec`.
