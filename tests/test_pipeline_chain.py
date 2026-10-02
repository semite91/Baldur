"""#6 restarted TDD - project.md pipeline chain proven with fakes.

Namespaces 00/01/02/03 wired exactly as 04_live_pipeline wires them live:
permission -> frame -> infer -> largest -> score(aspect from frame) ->
update -> frozen stdout. 10 slouch seconds must yield one bad_posture.
"""

import json
from pathlib import Path

import numpy

from nb_loader import load_notebook

ROOT = Path(__file__).resolve().parents[1] / "notebooks"
NS00 = load_notebook(str(ROOT / "00_env_camera.ipynb"))
NS01 = load_notebook(str(ROOT / "01_pose_score.ipynb"))
NS02 = load_notebook(str(ROOT / "02_events_jsonl.ipynb"))
NS03 = load_notebook(str(ROOT / "03_yolo_inference.ipynb"))

FROZEN_EVENTS = {"bad_posture", "recovered", "heartbeat", "error"}


class FakeCapture:
    def __init__(self, opened=True, frame=None):
        self.opened = opened
        self.frame = frame
        self.released = False
        self.reads = 0
        self.sources = []

    def isOpened(self):
        return self.opened

    def read(self):
        self.reads += 1
        if self.frame is None:
            return False, None
        return True, self.frame

    def release(self):
        self.released = True


class FakeKeypoints:
    def __init__(self, xyn, vis):
        data = numpy.zeros((xyn.shape[0], 17, 3))
        data[:, :, :2] = xyn
        data[:, :, 2] = vis
        self.xyn = xyn
        self.data = data


class FakeResult:
    def __init__(self, xyn, vis, xyxy):
        self.keypoints = FakeKeypoints(xyn, vis)
        self.boxes = type("Boxes", (), {"xyxy": xyxy})()


class FakeModel:
    def __init__(self, results=None, error=None):
        self.results = results if results is not None else []
        self.error = error
        self.calls = 0

    def __call__(self, frame, verbose=False):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.results


def slouch_person():
    xyn = numpy.zeros((17, 2))
    xyn[0] = (0.56, 0.42)
    xyn[1] = (0.47, 0.32)
    xyn[2] = (0.53, 0.32)
    xyn[3] = (0.60, 0.34)
    xyn[4] = (0.64, 0.35)
    xyn[5] = (0.45, 0.46)
    xyn[6] = (0.55, 0.42)
    xyn[11] = (0.46, 0.65)
    xyn[12] = (0.54, 0.65)
    return xyn


def drive_chain(capture, model, n_frames, dt=1.0):
    """Mirror of 04_live_pipeline: returns (events, state)."""
    factory_sources = []

    def factory(source):
        factory_sources.append(source)
        return capture

    events = []
    failed = []
    try:
        cap = NS00["open_camera"](source=0, open_capture=factory)
    except Exception as exc:
        NS00["emit_error"](
            getattr(exc, "code", "CAMERA_UNAVAILABLE"),
            str(exc) or type(exc).__name__,
        )
        return events, None
    try:
        state = NS02["new_state"]()
        for _ in range(n_frames):
            frame = NS00["read_frame"](cap)
            height, width = frame.shape[0], frame.shape[1]

            def score_one():
                persons = NS03["infer_frame"](model, frame)
                if not persons:
                    return None, False
                person = NS01["select_largest_person"](persons)
                return (
                    NS01["posture_score"](
                        person["xyn"], person["visibility"], aspect=width / height
                    ),
                    True,
                )

            frame_events = NS02["safe_update"](
                state, score_one, dt, on_error=lambda code, msg: failed.append(code)
            )
            for event in frame_events:
                NS02["emit_event"](event)
                events.append(event)
            if failed:
                break
    finally:
        NS00["release_camera"](cap)
    assert factory_sources == [0]
    return events, state


def test_slouch_chain_emits_one_bad_posture(capsys):
    xyn = numpy.stack([slouch_person()])
    vis = numpy.full((1, 17), 1.0)
    xyxy = numpy.array([[10.0, 20.0, 110.0, 220.0]])
    capture = FakeCapture(frame=numpy.zeros((480, 640, 3), dtype=numpy.uint8))
    model = FakeModel(results=[FakeResult(xyn, vis, xyxy)])
    events, _ = drive_chain(capture, model, 10)
    bad = [e for e in events if e["event"] == "bad_posture"]
    assert len(bad) == 1
    assert bad[0]["dwell_s"] == 10
    assert bad[0]["score"] < 70
    lines = capsys.readouterr().out.strip().splitlines()
    assert {json.loads(line)["event"] for line in lines} <= FROZEN_EVENTS
    assert capture.released is True


def test_denied_permission_errors_before_model_touch(capsys):
    capture = FakeCapture(opened=False)
    model = FakeModel(results=[])
    events, state = drive_chain(capture, model, 10)
    assert events == []
    assert state is None
    assert model.calls == 0
    assert capture.released is True
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["code"] == "CAMERA_UNAVAILABLE"


def test_empty_chain_beats_without_bad_posture():
    capture = FakeCapture(frame=numpy.zeros((480, 640, 3), dtype=numpy.uint8))
    model = FakeModel(results=[])
    events, state = drive_chain(capture, model, 12)
    assert [e for e in events if e["event"] == "bad_posture"] == []
    beats = [e for e in events if e["event"] == "heartbeat"]
    assert len(beats) == 2
    assert all(b["score"] is None for b in beats)
    assert state["outside_s"] == 0.0


def test_covered_person_chain_fires_at_ten_occluded_seconds(capsys):
    xyn = numpy.zeros((1, 17, 2))
    xyn[0, 5] = (0.45, 0.45)
    xyn[0, 6] = (0.55, 0.42)
    vis = numpy.zeros((1, 17))
    xyxy = numpy.array([[10.0, 20.0, 110.0, 220.0]])
    capture = FakeCapture(frame=numpy.zeros((480, 640, 3), dtype=numpy.uint8))
    model = FakeModel(results=[FakeResult(xyn, vis, xyxy)])
    events, state = drive_chain(capture, model, 10)
    bad = [e for e in events if e["event"] == "bad_posture"]
    assert len(bad) == 1
    assert bad[0]["dwell_s"] == 10
    assert state["in_bad"] is True
    lines = capsys.readouterr().out.strip().splitlines()
    assert {json.loads(line)["event"] for line in lines} <= FROZEN_EVENTS
    assert capture.released is True


def test_mid_chain_inference_failure_stops_loop(capsys):
    xyn = numpy.stack([slouch_person()])
    vis = numpy.full((1, 17), 1.0)
    xyxy = numpy.array([[10.0, 20.0, 110.0, 220.0]])
    results = [FakeResult(xyn, vis, xyxy)] * 3

    class FlakyModel(FakeModel):
        def __call__(self, frame, verbose=False):
            self.calls += 1
            if self.calls > 3:
                raise RuntimeError("cuda gone")
            return results

    capture = FakeCapture(frame=numpy.zeros((480, 640, 3), dtype=numpy.uint8))
    model = FlakyModel()
    events, _ = drive_chain(capture, model, 10)
    assert model.calls == 4
    assert capture.released is True
    lines = capsys.readouterr().out.strip().splitlines()
    parsed = [json.loads(line) for line in lines]
    assert parsed[-1]["event"] == "error"


def test_on_error_callback_reports_code_and_message():
    seen = []
    state = NS02["new_state"]()

    def broken():
        raise RuntimeError("shutter jam")

    NS02["safe_update"](state, broken, 1.0, on_error=lambda code, msg: seen.append((code, msg)))
    assert seen == [("UPDATE_FAILED", "shutter jam")]
