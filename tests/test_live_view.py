"""T6 (issue #7) - live annotated view, RED: overlay primitives.

Seams: box_color(in_bad) and annotate_frame(frame, box, score, in_bad)
on synthetic frames. plot() base stays a manual concern.
"""

from pathlib import Path

import numpy

from nb_loader import load_notebook

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "05_live_view.ipynb"

NS = load_notebook(str(NOTEBOOK))

GREEN = (0, 255, 0)
RED = (0, 0, 255)


def blank():
    return numpy.zeros((100, 100, 3), dtype=numpy.uint8)


def test_upright_frame_renders_green_border():
    view = NS["annotate_frame"](blank(), (10, 10, 50, 50), 82, False)
    assert view.shape == (100, 100, 3)
    assert view.dtype == numpy.uint8
    assert tuple(view[49, 30]) == GREEN


def test_bad_frame_renders_red_border():
    view = NS["annotate_frame"](blank(), (10, 10, 50, 50), 60, True)
    assert tuple(view[49, 30]) == RED


def test_missing_box_and_score_renders_neutrally():
    frame = blank()
    view = NS["annotate_frame"](frame, None, None, False)
    assert view.shape == frame.shape
    assert tuple(view[49, 30]) != GREEN and tuple(view[49, 30]) != RED
    assert (frame == 0).all()


def test_box_color_agrees_with_dwell_machine():
    from nb_loader import load_notebook as load

    events_ns = load(
        Path(__file__).resolve().parents[1] / "notebooks" / "02_events_jsonl.ipynb"
    )
    box_color = NS["box_color"]
    assert box_color(False) == GREEN
    state = events_ns["new_state"]()
    for _ in range(10):
        events_ns["update"](state, 60, 1.0)
    assert state["in_bad"] is True
    assert box_color(state["in_bad"]) == RED


def test_viewer_source_has_no_persistence_calls():
    source = Path(NOTEBOOK).read_text(encoding="utf-8")
    for forbidden in ("imwrite", "VideoWriter", "imsave", "savefig", "imencode"):
        assert forbidden not in source
