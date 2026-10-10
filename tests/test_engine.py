"""T8r (issue #16) - duplication-free engine.py, RED: thin composition only.

engine.py must reuse notebook namespaces via tests/nb_loader and define no
domain logic itself. Orchestration mirrors tests/test_pipeline_chain
drive_chain (the 04 live chain); fakes mirror that module's doubles.
"""

import ast
import json
import sys
from pathlib import Path

import numpy
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import engine
from test_pipeline_chain import FakeCapture, FakeModel, FakeResult, slouch_person
from test_pose_score import upright

NOTEBOOKS = [
    "00_env_camera.ipynb",
    "01_pose_score.ipynb",
    "02_events_jsonl.ipynb",
    "03_yolo_inference.ipynb",
]

FROZEN_EVENTS = {"bad_posture", "recovered", "heartbeat", "error"}


def _notebook_defined_names():
    import json as json_lib

    names = set()
    for notebook in NOTEBOOKS:
        with open(ROOT / "notebooks" / notebook, encoding="utf-8") as handle:
            cells = json_lib.load(handle)["cells"]
        for cell in cells:
            if cell["cell_type"] != "code":
                continue
            source = "".join(cell["source"])
            if "# DEMO" in source or "# LIVE" in source:
                continue
            tree = ast.parse(source)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.add(node.name)
                elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name):
                            names.add(target.id)
    return names


def _engine_tree():
    with open(ROOT / "engine.py", encoding="utf-8") as handle:
        return ast.parse(handle.read())


def upright_result():
    xyn, vis = upright()
    result = FakeResult(numpy.stack([xyn]), numpy.expand_dims(vis, 0),
                        numpy.array([[10.0, 20.0, 110.0, 220.0]]))
    plotted = numpy.full((10, 10, 3), 7, dtype=numpy.uint8)
    result.plot = lambda: plotted
    result.plotted = plotted
    return result


def slouch_result():
    result = FakeResult(numpy.stack([slouch_person()]), numpy.full((1, 17), 1.0),
                        numpy.array([[10.0, 20.0, 110.0, 220.0]]))
    plotted = numpy.full((10, 10, 3), 9, dtype=numpy.uint8)
    result.plot = lambda: plotted
    result.plotted = plotted
    return result


def stdout_events(capsys):
    lines = capsys.readouterr().out.strip().splitlines()
    return [json.loads(line) for line in lines]


def test_import_has_no_side_effects(capsys):
    import importlib

    importlib.reload(engine)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_base_dir_resolves_repo_root_in_dev():
    assert engine._base_dir() == ROOT
    assert (engine._base_dir() / "notebooks").is_dir()


def test_base_dir_prefers_meipass_when_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "X:\\bundle", raising=False)
    assert engine._base_dir() == Path("X:\\bundle")


def test_exit_codes_documented():
    assert (engine.EXIT_OK, engine.EXIT_CAMERA, engine.EXIT_ENGINE) == (0, 2, 3)
    assert "non-zero" in engine.__doc__


def test_defines_no_notebook_logic():
    engine_names = set()
    for node in _engine_tree().body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            engine_names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    engine_names.add(target.id)
    engine_names.discard("EXIT_OK")
    engine_names.discard("EXIT_CAMERA")
    engine_names.discard("EXIT_ENGINE")
    overlap = engine_names & _notebook_defined_names()
    assert overlap == set(), f"engine.py redefines notebook logic: {sorted(overlap)}"


def test_imports_are_stdlib_or_loader_only():
    allowed = {"argparse", "json", "sys", "time", "pathlib", "os", "nb_loader"}
    for node in ast.walk(_engine_tree()):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in allowed, alias.name
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] in allowed, node.module


def test_no_stdout_prints_in_engine_source():
    for node in ast.walk(_engine_tree()):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
            files = [kw.value for kw in node.keywords if kw.arg == "file"]
            assert files, "engine.py must never print to stdout (diagnostics go to stderr)"


def test_missing_camera_yields_single_error_and_exit_2(capsys):
    capture = FakeCapture(opened=False)
    code = engine.run(capture_factory=lambda source: capture, model=FakeModel(results=[]))
    assert code == engine.EXIT_CAMERA == 2
    assert capture.released is True
    events = stdout_events(capsys)
    assert len(events) == 1
    assert events[0]["event"] == "error"
    assert events[0]["code"] == "CAMERA_UNAVAILABLE"


def test_slouch_then_recovered_chain(capsys):
    tall = upright_result()
    slouch = slouch_result()
    script = [slouch] * 11 + [tall] * 3

    class ScriptModel(FakeModel):
        def __call__(self, frame, verbose=False):
            self.calls += 1
            return [script[min(self.calls - 1, len(script) - 1)]]

    capture = FakeCapture(frame=numpy.zeros((480, 640, 3), dtype=numpy.uint8))
    code = engine.run(frames=14, dt=1.0, capture_factory=lambda source: capture,
                      model=ScriptModel())
    assert code == engine.EXIT_OK == 0
    assert capture.released is True
    events = stdout_events(capsys)
    assert {event["event"] for event in events} <= FROZEN_EVENTS
    bad = [event for event in events if event["event"] == "bad_posture"]
    assert len(bad) == 1
    assert bad[0]["dwell_s"] == 10
    assert bad[0]["score"] < 70
    recovered = [event for event in events if event["event"] == "recovered"]
    assert len(recovered) == 1
    assert recovered[0]["dwell_s"] == 3
    assert recovered[0]["score"] >= 80
    beats = [event for event in events if event["event"] == "heartbeat"]
    assert len(beats) >= 2


def test_covered_person_fires_at_ten_with_strict_zero(capsys):
    """Covered-person parity: the strict scorer never abstains (0.0, not
    None), so illegible presence accrues the visible outside clock and
    fires bad_posture at the same 10s bar. The (None, True) occluded clock
    in update() belongs to 02 unit scope for abstaining scorers."""
    xyn = numpy.zeros((1, 17, 2))
    xyn[0, 5] = (0.45, 0.45)
    xyn[0, 6] = (0.55, 0.42)
    vis = numpy.zeros((1, 17))
    result = FakeResult(xyn, vis, numpy.array([[10.0, 20.0, 110.0, 220.0]]))
    capture = FakeCapture(frame=numpy.zeros((480, 640, 3), dtype=numpy.uint8))
    code = engine.run(frames=10, dt=1.0, capture_factory=lambda source: capture,
                      model=FakeModel(results=[result]))
    assert code == engine.EXIT_OK == 0
    events = stdout_events(capsys)
    bad = [event for event in events if event["event"] == "bad_posture"]
    assert len(bad) == 1
    assert bad[0]["dwell_s"] == 10
    assert bad[0]["score"] == 0.0


def test_warmup_discards_one_infer():
    capture = FakeCapture(frame=numpy.zeros((480, 640, 3), dtype=numpy.uint8))
    model = FakeModel(results=[])
    code = engine.run(frames=5, dt=1.0, capture_factory=lambda source: capture, model=model)
    assert code == engine.EXIT_OK == 0
    assert model.calls == 6


def test_midloop_failure_releases_and_returns_3(capsys):
    slouch = slouch_result()

    class FlakyModel(FakeModel):
        def __call__(self, frame, verbose=False):
            self.calls += 1
            if self.calls > 4:
                raise RuntimeError("cuda gone")
            return [slouch]

    capture = FakeCapture(frame=numpy.zeros((480, 640, 3), dtype=numpy.uint8))
    code = engine.run(frames=10, dt=1.0, capture_factory=lambda source: capture,
                      model=FlakyModel())
    assert code == engine.EXIT_ENGINE == 3
    assert capture.released is True
    events = stdout_events(capsys)
    assert events[-1]["event"] == "error"


def test_keyboard_interrupt_stops_clean(capsys):
    class QuittingCapture(FakeCapture):
        def read(self):
            self.reads += 1
            if self.reads > 2:
                raise KeyboardInterrupt
            return True, self.frame

    capture = QuittingCapture(frame=numpy.zeros((480, 640, 3), dtype=numpy.uint8))
    code = engine.run(dt=1.0, capture_factory=lambda source: capture,
                      model=FakeModel(results=[]))
    assert code == engine.EXIT_OK == 0
    assert capture.released is True


def test_main_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        engine.main(["--help"])
    assert excinfo.value.code == 0


def test_warmup_read_failure_returns_3(capsys):
    capture = FakeCapture(opened=True, frame=None)
    code = engine.run(dt=1.0, capture_factory=lambda source: capture,
                      model=FakeModel(results=[]))
    assert code == engine.EXIT_ENGINE == 3
    assert capture.released is True
    events = stdout_events(capsys)
    assert events[-1]["event"] == "error"
    assert events[-1]["code"] == "FRAME_READ_FAILED"


def test_midloop_read_failure_releases_and_returns_3(capsys):
    class DyingCapture(FakeCapture):
        def read(self):
            self.reads += 1
            if self.reads > 2:
                return False, None
            return True, self.frame

    capture = DyingCapture(frame=numpy.zeros((480, 640, 3), dtype=numpy.uint8))
    code = engine.run(dt=1.0, capture_factory=lambda source: capture,
                      model=FakeModel(results=[]))
    assert code == engine.EXIT_ENGINE == 3
    assert capture.released is True
    events = stdout_events(capsys)
    assert events[-1]["event"] == "error"


# RED P1-P6 (--preview, issue #16): stub viewer injected by monkeypatching
# engine._load_namespaces; no GUI, no camera, no model needed.


class StubCV2:
    FONT_HERSHEY_SIMPLEX = 0
    WND_PROP_VISIBLE = 1

    def __init__(self, fail_on=0, quit_at=0, visible_at=0, no_property=False):
        self.shows = []
        self.frames = []
        self.texts = []
        self.destroys = 0
        self.calls = 0
        self.fail_on = fail_on
        self.quit_at = quit_at
        self.visible_at = visible_at
        self.no_property = no_property

    def imshow(self, name, frame):
        self.calls += 1
        if self.fail_on and self.calls >= self.fail_on:
            raise RuntimeError("no GUI backend")
        self.shows.append(name)
        self.frames.append(frame)

    def waitKey(self, delay):
        if self.quit_at and self.calls >= self.quit_at:
            return ord("q")
        return -1

    def getWindowProperty(self, name, prop):
        if self.no_property:
            raise RuntimeError("unsupported backend")
        if self.visible_at and self.calls >= self.visible_at:
            return 0
        return 1

    def destroyAllWindows(self):
        self.destroys += 1

    def putText(self, image, text, org, font, scale, color, thickness):
        self.texts.append((text, org))

    def waitKey(self, delay):
        if self.quit_at and self.calls >= self.quit_at:
            return ord("q")
        return -1

    def destroyAllWindows(self):
        self.destroys += 1


def stub_viewer(monkeypatch, cv2stub, annotates):
    real_load = engine._load_namespaces

    def fake_load(stems=engine._NOTEBOOK_STEMS, notebooks_dir=None):
        if "05_live_view" in stems:
            def annotate(frame, box, score, in_bad, extra=None):
                annotates.append((box, score, in_bad, extra))
                return frame

            return {"05_live_view": {
                "cv2": cv2stub,
                "annotate_frame": annotate,
                "box_color": lambda in_bad: (0, 0, 255) if in_bad else (0, 255, 0),
            }}
        return real_load(stems, notebooks_dir)

    monkeypatch.setattr(engine, "_load_namespaces", fake_load)


def blank_capture():
    return FakeCapture(frame=numpy.zeros((480, 640, 3), dtype=numpy.uint8))


def test_preview_shows_and_destroys(capsys, monkeypatch):
    cv2stub = StubCV2()
    annotates = []
    stub_viewer(monkeypatch, cv2stub, annotates)
    capture = blank_capture()
    code = engine.run(frames=3, dt=1.0, capture_factory=lambda source: capture,
                      model=FakeModel(results=[]), preview=True)
    assert code == engine.EXIT_OK == 0
    assert capture.released is True
    assert cv2stub.shows == ["Baldur posture"] * 3
    assert cv2stub.destroys == 1
    assert len(annotates) == 3
    assert all(box is None and score is None and not bad
               for box, score, bad, extra in annotates)
    assert all(extra == "RULA --" for _, _, _, extra in annotates)
    assert capsys.readouterr().out == ""


def test_preview_box_and_score_overlay(monkeypatch):
    cv2stub = StubCV2()
    annotates = []
    stub_viewer(monkeypatch, cv2stub, annotates)
    capture = blank_capture()
    code = engine.run(frames=10, dt=1.0, capture_factory=lambda source: capture,
                      model=FakeModel(results=[slouch_result()]), preview=True)
    assert code == engine.EXIT_OK == 0
    first = annotates[0]
    assert first[0] is not None and first[1] < 70 and first[2] is False
    last = annotates[-1]
    box, score, bad, extra = last
    assert isinstance(box, tuple) and len(box) == 4
    assert all(isinstance(edge, int) for edge in box)
    assert score < 70
    assert bad is True


def test_preview_q_quits_clean(monkeypatch):
    cv2stub = StubCV2(quit_at=2)
    annotates = []
    stub_viewer(monkeypatch, cv2stub, annotates)
    capture = blank_capture()
    code = engine.run(dt=1.0, capture_factory=lambda source: capture,
                      model=FakeModel(results=[]), preview=True)
    assert code == engine.EXIT_OK == 0
    assert capture.released is True
    assert cv2stub.calls == 2
    assert cv2stub.destroys == 1


def test_preview_backend_failure_returns_3(capsys, monkeypatch):
    cv2stub = StubCV2(fail_on=1)
    annotates = []
    stub_viewer(monkeypatch, cv2stub, annotates)
    capture = blank_capture()
    code = engine.run(frames=5, dt=1.0, capture_factory=lambda source: capture,
                      model=FakeModel(results=[]), preview=True)
    assert code == engine.EXIT_ENGINE == 3
    assert capture.released is True
    events = stdout_events(capsys)
    assert events[-1]["event"] == "error"


def test_preview_missing_viewer_returns_3_without_camera(capsys, monkeypatch):
    real_load = engine._load_namespaces
    opened = []

    def fake_load(stems=engine._NOTEBOOK_STEMS, notebooks_dir=None):
        if "05_live_view" in stems:
            raise ImportError("no cv2 on this box")
        return real_load(stems, notebooks_dir)

    monkeypatch.setattr(engine, "_load_namespaces", fake_load)
    capture = blank_capture()
    code = engine.run(dt=1.0, capture_factory=lambda source: opened.append(source) or capture,
                      model=FakeModel(results=[]), preview=True)
    assert code == engine.EXIT_ENGINE == 3
    assert opened == []
    assert capture.released is False
    events = stdout_events(capsys)
    assert len(events) == 1
    assert events[-1]["event"] == "error"
    assert events[-1]["code"] == "PREVIEW_UNAVAILABLE"


def test_preview_rula_extra_format(monkeypatch):
    cv2stub = StubCV2()
    annotates = []
    stub_viewer(monkeypatch, cv2stub, annotates)
    capture = blank_capture()
    code = engine.run(frames=10, dt=1.0, capture_factory=lambda source: capture,
                      model=FakeModel(results=[slouch_result()]), preview=True)
    assert code == engine.EXIT_OK == 0
    last = annotates[-1][3]
    assert last.startswith("RULA ")
    assert "/A" in last
    assert last != "RULA --"


def test_preview_uses_plotted_base(monkeypatch):
    cv2stub = StubCV2()
    annotates = []
    stub_viewer(monkeypatch, cv2stub, annotates)
    slouch = slouch_result()
    capture = blank_capture()
    code = engine.run(frames=2, dt=1.0, capture_factory=lambda source: capture,
                      model=FakeModel(results=[slouch]), preview=True)
    assert code == engine.EXIT_OK == 0
    assert len(cv2stub.frames) == 2
    assert all(shown is slouch.plotted for shown in cv2stub.frames)


def test_preview_display_failure_falls_back(capsys, monkeypatch):
    cv2stub = StubCV2()
    annotates = []
    stub_viewer(monkeypatch, cv2stub, annotates)
    bare = FakeResult(numpy.stack([slouch_person()]), numpy.full((1, 17), 1.0),
                      numpy.array([[10.0, 20.0, 110.0, 220.0]]))
    frame = numpy.zeros((480, 640, 3), dtype=numpy.uint8)
    capture = FakeCapture(frame=frame)
    code = engine.run(frames=2, dt=1.0, capture_factory=lambda source: capture,
                      model=FakeModel(results=[bare]), preview=True)
    assert code == engine.EXIT_OK == 0
    assert capture.released is True
    assert len(cv2stub.frames) == 2
    assert all(shown is frame for shown in cv2stub.frames)
    assert capsys.readouterr().out == ""


def test_preview_plotted_status_text(monkeypatch):
    cv2stub = StubCV2()
    annotates = []
    stub_viewer(monkeypatch, cv2stub, annotates)
    slouch = slouch_result()
    capture = blank_capture()
    code = engine.run(frames=2, dt=1.0, capture_factory=lambda source: capture,
                      model=FakeModel(results=[slouch]), preview=True)
    assert code == engine.EXIT_OK == 0
    assert ("plotted", (10, 90)) in cv2stub.texts


def test_preview_not_plotted_status_text(monkeypatch):
    cv2stub = StubCV2()
    annotates = []
    stub_viewer(monkeypatch, cv2stub, annotates)
    capture = blank_capture()
    code = engine.run(frames=2, dt=1.0, capture_factory=lambda source: capture,
                      model=FakeModel(results=[]), preview=True)
    assert code == engine.EXIT_OK == 0
    assert ("not plotted", (10, 90)) in cv2stub.texts
    assert not any(text == "plotted" for text, _ in cv2stub.texts)


def test_preview_x_close_quits_clean(monkeypatch):
    cv2stub = StubCV2(visible_at=2)
    annotates = []
    stub_viewer(monkeypatch, cv2stub, annotates)
    capture = blank_capture()
    code = engine.run(dt=1.0, capture_factory=lambda source: capture,
                      model=FakeModel(results=[]), preview=True)
    assert code == engine.EXIT_OK == 0
    assert capture.released is True
    assert cv2stub.calls == 2
    assert cv2stub.destroys == 1


def test_preview_unsupported_property_keeps_running(monkeypatch, capsys):
    cv2stub = StubCV2(no_property=True)
    annotates = []
    stub_viewer(monkeypatch, cv2stub, annotates)
    capture = blank_capture()
    code = engine.run(frames=3, dt=1.0, capture_factory=lambda source: capture,
                      model=FakeModel(results=[]), preview=True)
    assert code == engine.EXIT_OK == 0
    assert cv2stub.calls == 3
    assert capsys.readouterr().out == ""


# C1 (--probe, issue #18): fast camera check, 00 namespace only.


def test_probe_success_is_silent_and_releases(capsys):
    capture = blank_capture()
    code = engine.probe_camera(capture_factory=lambda source: capture)
    assert code == engine.EXIT_OK == 0
    assert capture.released is True
    assert capsys.readouterr().out == ""


def test_probe_denied_camera_single_error_exit_2(capsys):
    capture = FakeCapture(opened=False)
    code = engine.probe_camera(capture_factory=lambda source: capture)
    assert code == engine.EXIT_CAMERA == 2
    assert capture.released is True
    events = stdout_events(capsys)
    assert len(events) == 1
    assert events[0]["event"] == "error"
    assert events[0]["code"] == "CAMERA_UNAVAILABLE"


def test_probe_read_failure_single_error_exit_2(capsys):
    capture = FakeCapture(opened=True, frame=None)
    code = engine.probe_camera(capture_factory=lambda source: capture)
    assert code == engine.EXIT_CAMERA == 2
    assert capture.released is True
    events = stdout_events(capsys)
    assert len(events) == 1
    assert events[0]["event"] == "error"
    assert events[0]["code"] == "FRAME_READ_FAILED"


def test_probe_main_flag_plumbs_source(monkeypatch):
    seen = []

    def fake_probe(source=0, capture_factory=None, notebooks_dir=None):
        seen.append(source)
        return engine.EXIT_OK

    monkeypatch.setattr(engine, "probe_camera", fake_probe)
    assert engine.main(["--probe", "--source", "3"]) == engine.EXIT_OK
    assert seen == [3]
