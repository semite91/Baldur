"""T1 (issue #2) - env/camera spike, RED cycle 1: error-event seam.

Seam under test: stdout JSON-lines error emission (frozen interface:
bad_posture, recovered, heartbeat, error - only error is in T1 scope).
"""

import json
from importlib import metadata
from pathlib import Path

import numpy

from nb_loader import load_notebook

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "00_env_camera.ipynb"

NS = load_notebook(str(NOTEBOOK))


def test_denied_camera_emits_single_error_event(capsys):
    emit_error = NS["emit_error"]
    event = emit_error("CAMERA_UNAVAILABLE", "source=0 could not be opened")

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "event": "error",
        "code": "CAMERA_UNAVAILABLE",
        "message": "source=0 could not be opened",
    }
    assert event["event"] == "error"


def test_stdout_lines_are_events_only(capsys):
    emit_error = NS["emit_error"]
    emit_error("CAMERA_UNAVAILABLE", "boom")

    lines = capsys.readouterr().out.strip().splitlines()
    assert lines, "expected at least one stdout line"
    for line in lines:
        parsed = json.loads(line)
        assert "event" in parsed


# RED cycle 2: webcam frame-loop seam (injectable capture factory).


class FakeCapture:
    def __init__(self, opened=True, frame=None):
        self.opened = opened
        self.frame = frame
        self.released = False

    def isOpened(self):
        return self.opened

    def read(self):
        if self.frame is None:
            return False, None
        return True, self.frame

    def release(self):
        self.released = True


def make_factory(capture):
    seen = {}

    def factory(source):
        seen["source"] = source
        return capture

    factory.seen = seen
    return factory


def test_open_uses_source_zero():
    capture = FakeCapture(opened=True)
    open_camera = NS["open_camera"]
    result = open_camera(source=0, open_capture=make_factory(capture))
    assert result is capture


def test_open_records_single_webcam_source():
    capture = FakeCapture(opened=True)
    factory = make_factory(capture)
    NS["open_camera"](source=0, open_capture=factory)
    assert factory.seen["source"] == 0


def test_read_frame_returns_frame_with_shape():
    frame = numpy.zeros((480, 640, 3), dtype=numpy.uint8)
    capture = FakeCapture(opened=True, frame=frame)
    result = NS["read_frame"](capture)
    assert result.shape == (480, 640, 3)


def test_failed_open_raises_camera_error_and_releases():
    capture = FakeCapture(opened=False)
    open_camera = NS["open_camera"]
    CameraError = NS["CameraError"]
    try:
        open_camera(source=0, open_capture=make_factory(capture))
    except CameraError as exc:
        assert exc.code == "CAMERA_UNAVAILABLE"
    else:
        raise AssertionError("expected CameraError")
    assert capture.released is True


def test_failed_read_raises_camera_error():
    capture = FakeCapture(opened=True, frame=None)
    CameraError = NS["CameraError"]
    try:
        NS["read_frame"](capture)
    except CameraError as exc:
        assert exc.code == "FRAME_READ_FAILED"
    else:
        raise AssertionError("expected CameraError")


# RED cycle 3: FPS measure + version pins + no-persistence guard.


def test_fps_measured_from_real_timestamps():
    assert NS["measure_fps"](30, 2.0) == 15.0


def test_fps_zero_elapsed_returns_zero():
    assert NS["measure_fps"](30, 0.0) == 0.0


def test_pinned_versions_match_installed():
    versions = NS["pinned_versions"]()
    assert set(versions) == {"ultralytics", "torch", "opencv", "numpy"}
    assert versions["ultralytics"] == metadata.version("ultralytics")
    assert versions["torch"] == metadata.version("torch")
    assert versions["opencv"] == metadata.version("opencv-python")
    assert versions["numpy"] == metadata.version("numpy")


def test_camera_functions_write_no_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    frame = numpy.zeros((48, 64, 3), dtype=numpy.uint8)
    capture = FakeCapture(opened=True, frame=frame)
    NS["open_camera"](source=0, open_capture=make_factory(capture))
    NS["read_frame"](capture)
    NS["release_camera"](capture)
    NS["emit_error"]("CAMERA_UNAVAILABLE", "audit probe")
    capsys.readouterr()
    assert list(tmp_path.iterdir()) == []
