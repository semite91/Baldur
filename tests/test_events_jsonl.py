"""T3 (issue #4) - event loop JSON-lines, RED cycle 1: dwell core.

Seam under test: pure dt-injectable state machine update(state, score, dt).
Thresholds mirror 01 (consistency pinned in cycle 2); unified in engine.py (T4).
"""

from pathlib import Path
import json

from nb_loader import load_notebook

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "02_events_jsonl.ipynb"

NS = load_notebook(str(NOTEBOOK))


def feed(score, seconds, state=None, dt=1.0):
    update = NS["update"]
    state = NS["new_state"]() if state is None else state
    events = []
    steps = int(seconds / dt)
    for _ in range(steps):
        events.extend(update(state, score, dt))
    return state, events


def state_events(events):
    return [e for e in events if e["event"] in ("bad_posture", "recovered")]


FROZEN_EVENTS = {"bad_posture", "recovered", "heartbeat", "error"}


def test_ten_seconds_below_70_emits_one_bad_posture():
    _, events = feed(60, 10)
    assert state_events(events) == [
        {"event": "bad_posture", "score": 60, "dwell_s": 10}
    ]
    assert {e["event"] for e in events} <= FROZEN_EVENTS


def test_nine_seconds_below_70_emits_no_state_events():
    _, events = feed(60, 9)
    assert state_events(events) == []


def test_twelve_seconds_below_70_still_single_bad_posture():
    _, events = feed(60, 12)
    assert state_events(events) == [
        {"event": "bad_posture", "score": 60, "dwell_s": 10}
    ]
    assert {e["event"] for e in events} <= FROZEN_EVENTS


def test_upright_frames_emit_no_state_events():
    _, events = feed(85, 20)
    assert state_events(events) == []


# RED cycle 2: recovery, None-hold, heartbeat, error emitter, wiring.


def test_three_seconds_recovered_after_bad_emits_recovered():
    update = NS["update"]
    state = NS["new_state"]()
    for _ in range(10):
        update(state, 60, 1.0)
    events = []
    for _ in range(3):
        events.extend(update(state, 85, 1.0))
    assert state_events(events) == [
        {"event": "recovered", "score": 85, "dwell_s": 3}
    ]


def test_partial_recovery_resets_clock():
    update = NS["update"]
    state = NS["new_state"]()
    for _ in range(10):
        update(state, 60, 1.0)
    for _ in range(2):
        update(state, 85, 1.0)
    events = update(state, 60, 1.0)
    assert state_events(events) == []
    assert state["in_bad"] is True
    assert state["recovery_s"] == 0.0


def test_none_freezes_dwell_clocks():
    update = NS["update"]
    state = NS["new_state"]()
    for _ in range(6):
        update(state, 60, 1.0)
    frozen = state["outside_s"]
    for _ in range(20):
        events = update(state, None, 1.0)
        assert state_events(events) == []
    assert state["outside_s"] == frozen
    _, resumed = feed(60, 4, state=state)
    assert state_events(resumed) == [
        {"event": "bad_posture", "score": 60, "dwell_s": 10}
    ]


def test_heartbeat_every_five_seconds_with_last_score():
    _, events = feed(72, 11)
    beats = [e for e in events if e["event"] == "heartbeat"]
    assert len(beats) == 2
    assert all(b["score"] == 72 for b in beats)


def test_heartbeat_before_first_score_carries_null():
    update = NS["update"]
    state = NS["new_state"]()
    events = update(state, None, 5.0)
    assert events == [{"event": "heartbeat", "score": None}]


def test_failed_frame_emits_frozen_error_event(capsys):
    def broken():
        raise RuntimeError("shutter jam")

    events = NS["safe_update"](NS["new_state"](), broken, 1.0)
    assert events == []
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "event": "error",
        "code": "UPDATE_FAILED",
        "message": "shutter jam",
    }


def test_error_event_preserves_machine_code(capsys):
    class CameraDown(Exception):
        def __init__(self):
            super().__init__("source=0 lost")
            self.code = "CAMERA_UNAVAILABLE"

    def failing():
        raise CameraDown()

    NS["safe_update"](NS["new_state"](), failing, 1.0)
    line = capsys.readouterr().out.strip().splitlines()
    assert json.loads(line[0])["code"] == "CAMERA_UNAVAILABLE"


def test_thresholds_mirror_scoring_notebook():
    scoring = load_notebook(
        Path(__file__).resolve().parents[1] / "notebooks" / "01_pose_score.ipynb"
    )
    assert NS["UPRIGHT_SCORE"] == scoring["UPRIGHT_SCORE"]
    assert NS["RECOVERED_SCORE"] == scoring["RECOVERED_SCORE"]


def test_scripted_run_stdout_parses_as_frozen_events_only(capsys):
    update, emit_event = NS["update"], NS["emit_event"]
    state = NS["new_state"]()
    script = [(60, 1.0)] * 10 + [(85, 1.0)] * 3 + [(None, 1.0)] * 6
    for score, dt in script:
        for event in update(state, score, dt):
            emit_event(event)
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines, "expected stdout output"
    parsed = [json.loads(line) for line in lines]
    assert {e["event"] for e in parsed} <= FROZEN_EVENTS
    kinds = [e["event"] for e in parsed]
    assert "bad_posture" in kinds and "recovered" in kinds and "heartbeat" in kinds


def test_largest_person_drives_state_machine():
    scoring = load_notebook(
        Path(__file__).resolve().parents[1] / "notebooks" / "01_pose_score.ipynb"
    )
    import numpy

    xyn = numpy.zeros((17, 2))
    xyn[3] = (0.60, 0.34)
    xyn[4] = (0.64, 0.35)
    xyn[5] = (0.45, 0.46)
    xyn[6] = (0.55, 0.42)
    xyn[0] = (0.56, 0.42)
    xyn[1] = (0.53, 0.32)
    xyn[2] = (0.59, 0.32)
    xyn[11] = (0.46, 0.65)
    xyn[12] = (0.54, 0.65)
    vis = numpy.full(17, 1.0)
    near = {"area": 2.0, "xyn": xyn, "visibility": vis}
    far = {"area": 0.5, "xyn": numpy.zeros((17, 2)), "visibility": vis}
    update = NS["update"]
    state = NS["new_state"]()
    events = []
    for _ in range(10):
        person = scoring["select_largest_person"]([far, near])
        assert person is near
        score = scoring["posture_score"](person["xyn"], person["visibility"])
        assert score < 70
        events.extend(update(state, score, 1.0))
    assert state_events(events) == [
        {"event": "bad_posture", "score": score, "dwell_s": 10}
    ]
