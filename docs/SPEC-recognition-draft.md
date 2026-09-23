# SPEC DRAFT — Baldur Posture Recognition (Recognition-only v1)

> Skill: `to-spec` (no interview, synthesis of `docs/SRS.md`, `CONTEXT.md`, ADRs 0001–0003).
> Seams confirmed by user 2026-09-23: (1) stdout JSON-lines event stream as top seam,
> (2) pure posture-score function, (3) webcam frame loop.
> Publish target: GitHub issue with label `ready-for-agent`.
> BLOCKED: `gh` CLI not installed in this environment — run the publish command at the bottom after `gh auth login`.

## Problem Statement

As a desk worker staying at a PC, I sit for long hours and drift into non-upright posture without noticing, which causes discomfort over time. I want the PC itself to notice when my posture stays outside the valid range and tell me through a downstream stage, without any video of me ever leaving my machine or being stored anywhere.

## Solution

Ship Recognition: a local Python YOLO stage that watches the webcam, tracks a single Person, estimates pose keypoints every frame, computes a posture score, applies valid-range plus dwell-time hysteresis, and emits only posture events as JSON-lines on stdout. A deferred Warning stage will consume that stream; this spec freezes that event contract but does not build the UI.

## User Stories

1. As a desk worker, I want camera permission checked first, so that a denied camera produces a clear error instead of a silent hang.
2. As a desk worker, I want the single webcam opened as a continuous stream, so that scoring follows my real-time movement.
3. As a desk worker, I want the largest Person in frame tracked for scoring, so that background passers-by do not flip my state.
4. As a desk worker, I want pose keypoints estimated per frame, so that my posture score reflects my actual body position.
5. As a desk worker, I want a 0–100 posture score from ear-shoulder verticality plus shoulder symmetry, so that higher always means more upright.
6. As a desk worker, I want scores at or above 70 treated as upright, so that small natural sway does not trigger warnings.
7. As a desk worker, I want a bad-posture signal only after 10 continuous seconds outside the valid range, so that brief reaches or sips of coffee are ignored.
8. As a desk worker, I want recovery confirmed only after 3 continuous seconds at or above 80, so that the signal does not flap on the boundary.
9. As a desk worker, I want exactly one bad-posture event per slouch episode, so that downstream stages do not spam me.
10. As a desk worker, I want a heartbeat event every 5 seconds regardless of state, so that the downstream host knows Recognition is alive.
11. As a desk worker, I want empty frames (nobody visible) treated as neutral, so that stepping away never counts as bad posture.
12. As a desk worker, I want low-visibility or occluded frames treated as neutral, so that poor light or a hand in front of the camera does not punish me.
13. As a desk worker, I want machine-readable error events on camera or model failure, so that the host can react instead of watching a dead stream.
14. As a desk worker, I want stdout to carry only the four frozen events, so that the downstream parser never breaks on stray logs.
15. As a desk worker, I want no image, video, keypoint, or score persistence, so that continuous camera monitoring never becomes a recording liability.
16. As a desk worker, I want everything to run locally on Windows with local inference, so that my video never leaves my device.
17. As a desk worker, I want pinned model and runtime versions after the environment spike, so that my setup reproduces instead of breaking on upgrades.
18. As a notebook user, I want one concern per cell with importable scoring functions, so that spikes can later become a plain script without rewrites.
19. As a future Warning consumer, I want the four-event JSON-lines contract frozen now, so that the fullscreen popup stage can be built later against a stable interface.
20. As a future Oratory user, I want Oratory kept fully out of this build, so that posture work stays uncluttered by a second feature area.

## Implementation Decisions

- Modules to build (Recognition only): camera intake (permission check, single-webcam streaming opener, FPS measure); pose estimation (Ultralytics pose model loader with stable fallback family, per-frame keypoint reader exposing pixel, normalized, and visibility channels, largest-Person selector, neutral-on-empty handling); scoring (pure keypoints-to-score function combining ear-shoulder verticality with shoulder symmetry, 0–100 range); event loop (dwell-time hysteresis state machine, heartbeat ticker, error emitter, stdout-only JSON-lines writer).
- Model decision (ADR-0003, Context7 `/ultralytics/ultralytics`): Ultralytics `yolo26n-pose` family with fallback to the latest stable pose weights if the v26 wheel is not installable on Windows; webcam consumed as a streaming generator; headless scoring loop with no on-screen preview.
- Scoring decision: ear-shoulder verticality plus shoulder symmetry; valid range upright at 70 and above; recovery hysteresis at 80; calibration against real desk postures in the scoring spike, with a throwaway prototype detour if the formula cannot be settled in conversation.
- Dwell decision: continuous 10s outside valid range before a single bad-posture emission; continuous 3s at or above 80 after a bad-posture before a recovered emission; heartbeat every 5s independent of state; empty or low-confidence frames hold state (neutral), never directly triggering bad posture.
- API contract decision (frozen, shared with deferred Warning): stdout JSON-lines with exactly four event names — bad-posture carrying score plus dwell seconds, recovered carrying score plus dwell seconds, heartbeat carrying score, error carrying machine-readable code plus message. No other stdout output permitted.
- Warning contract decision (frozen interface, deferred build; Context7 `/dotnet/wpf`): host launches the engine as a child process with piped stdout read asynchronously, shows a maximized always-on-top modal dialog on bad posture, hides on recovered, gates optional pointer restriction behind configuration, and always clears restriction and dismisses on ESC. Mouse-restriction API choice, config location, and multi-monitor behavior are Warning-ticket decisions, not this spec.
- Notebook decision (Context7 `/jupyter/notebook`): deliverable is notebooks in three phases — environment plus camera, pose-score calibration, events JSON-lines — kept importable with no magic-dependent logic inside scoring functions; script conversion with a guarded entry point is a separate later ticket.
- Platform and privacy decisions (ADR-0001, ADR-0002): Windows-only local inference, no cloud, no cross-platform support; memory-only scoring holding only the current frame and score, trading debuggability and analytics for user trust.

## Testing Decisions

- What makes a good test here: assert external behavior at the highest seam (the stdout event stream), not internals; feed controlled score sequences or fixture frames and assert emitted events; never assert on private helpers or model weights.
- Seam 1 (top, preferred): stdout JSON-lines stream — parse lines, assert event names, ordering, dwell counts, heartbeat cadence, and absence of non-event output.
- Seam 2: pure posture-score function — property checks (upright frames score higher than slouched frames, symmetric shoulders outscore asymmetric ones, output always within 0–100).
- Seam 3: webcam frame loop — largest-Person selection, neutral hold on empty or low-visibility input, no bad-posture emission from neutral runs.
- Prior art: none — greenfield notebooks, no existing test suite; new tests establish the pattern.
- Process gates (per project workflow): shred scenarios to atomic single-purpose processes, save the scenario list under the infrastructure test folder with a timestamped filename, and hold a manual user confirm before any code.

## Out of Scope

- Warning build: fullscreen popup, modal behavior, pointer restriction, ESC wiring, configuration surface, multi-monitor handling (contract frozen only).
- Script conversion and child-process integration tickets (notebook-to-script hardening, host process wiring).
- Oratory skills enhancer in any form.
- Any persistence of images, video, keypoints, or scores, including calibration datasets.
- Cloud inference, cross-platform support, multi-camera support, analytics dashboards.
- Score-formula reweighting beyond the v1 verticality-plus-symmetry definition (belongs to a later calibration ticket if needed).

## Further Notes

- Vocabulary throughout follows `CONTEXT.md` (Person, pose keypoints, posture score, valid range, dwell time, Recognition, Warning); contradicts none of ADR-0001 (Windows-local), ADR-0002 (no persistence), ADR-0003 (YOLO26-pose with fallback).
- Context7 library IDs used: `/ultralytics/ultralytics`, `/dotnet/wpf`, `/jupyter/notebook` (fetched 2026-09-23).
- Provenance: synthesized from `docs/SRS.md` v1.0 (promoted from `instruction/SRS.md` grill draft), no interviews, seams confirmed by user.

---

## Publish (requires `gh`)

Install `gh`, then from the repo root run `gh auth login` and:

```powershell
gh issue create --title "SPEC: Baldur Posture Recognition (Recognition-only v1)" --label "ready-for-agent" --body-file "docs/SPEC-recognition-draft.md"
```
