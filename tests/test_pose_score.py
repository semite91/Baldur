"""T2 (issue #3) - pose scoring calibration, RED cycle 1: score core.

Seam under test: pure posture-score function (numpy in, 0-100 or None out).
COCO-17 indices: ears 3,4; shoulders 5,6 (confirmed live on yolo26n-pose).
"""

from pathlib import Path

import numpy

from nb_loader import load_notebook

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "01_pose_score.ipynb"

NS = load_notebook(str(NOTEBOOK))

EAR_L, EAR_R, SHOULDER_L, SHOULDER_R = 3, 4, 5, 6
NOSE, EYE_L, EYE_R, HIP_L, HIP_R = 0, 1, 2, 11, 12


def make_person(ear_l, ear_r, sh_l, sh_r, visibility=1.0, nose=(0.50, 0.34),
                eye_l=(0.47, 0.32), eye_r=(0.53, 0.32),
                hip_l=(0.46, 0.65), hip_r=(0.54, 0.65)):
    xyn = numpy.zeros((17, 2))
    xyn[NOSE] = nose
    xyn[EYE_L] = eye_l
    xyn[EYE_R] = eye_r
    xyn[EAR_L] = ear_l
    xyn[EAR_R] = ear_r
    xyn[SHOULDER_L] = sh_l
    xyn[SHOULDER_R] = sh_r
    xyn[HIP_L] = hip_l
    xyn[HIP_R] = hip_r
    return xyn, numpy.full(17, visibility)


def upright():
    return make_person((0.45, 0.30), (0.55, 0.30), (0.45, 0.45), (0.55, 0.45))


def slouched():
    return make_person((0.60, 0.34), (0.64, 0.35), (0.45, 0.46), (0.55, 0.42),
                       nose=(0.56, 0.42))


def bowed():
    return make_person((0.45, 0.30), (0.55, 0.30), (0.45, 0.45), (0.55, 0.45),
                       nose=(0.50, 0.44))


def hunched():
    return make_person((0.45, 0.30), (0.55, 0.30), (0.465, 0.45), (0.535, 0.45))


def asymmetric():
    return make_person((0.45, 0.30), (0.55, 0.30), (0.45, 0.45), (0.55, 0.40))


def test_upright_scores_at_or_above_70():
    xyn, vis = upright()
    assert NS["posture_score"](xyn, vis) >= 70


def test_slouched_scores_below_70():
    xyn, vis = slouched()
    assert NS["posture_score"](xyn, vis) < 70


def test_asymmetric_scores_below_symmetric():
    xyn_up, vis_up = upright()
    xyn_asym, vis_asym = asymmetric()
    score = NS["posture_score"]
    assert score(xyn_asym, vis_asym) < score(xyn_up, vis_up)


def test_scores_within_0_to_100():
    score = NS["posture_score"]
    for fixture in (upright, slouched, asymmetric):
        xyn, vis = fixture()
        assert 0 <= score(xyn, vis) <= 100
    collapsed = numpy.zeros((17, 2)), numpy.full(17, 1.0)
    assert 0 <= score(*collapsed) <= 100


def test_hidden_ears_and_shoulders_scores_none():
    xyn, _ = upright()
    assert NS["posture_score"](xyn, numpy.zeros(17)) is None


def test_low_visibility_scores_none():
    xyn, _ = upright()
    assert NS["posture_score"](xyn, numpy.full(17, 0.1)) is None


def test_single_hidden_ear_still_scores():
    xyn, _ = upright()
    vis = numpy.full(17, 1.0)
    vis[EAR_L] = 0.0
    assert NS["posture_score"](xyn, vis) >= 70


# RED cycle 2: largest-Person selection + valid-range predicates.


def make_detected(area, fixture=upright):
    xyn, vis = fixture()
    return {"area": area, "xyn": xyn, "visibility": vis}


def test_single_person_selected_trivially():
    person = make_detected(1.0)
    assert NS["select_largest_person"]([person]) is person


def test_largest_person_selected():
    near = make_detected(2.0)
    far = make_detected(0.5)
    assert NS["select_largest_person"]([far, near]) is near


def test_empty_frame_selects_none():
    assert NS["select_largest_person"]([]) is None


def test_upright_predicate_boundary():
    assert NS["is_upright"](70) is True
    assert NS["is_upright"](69.9) is False


def test_recovered_predicate_boundary():
    assert NS["is_recovered"](80) is True
    assert NS["is_recovered"](79.9) is False


def test_none_score_is_neither_upright_nor_recovered():
    assert NS["is_upright"](None) is False
    assert NS["is_recovered"](None) is False


# Review cycle (ocr delegation): predicates must return real bools for
# numpy scalars crossing the torch->numpy boundary in T3.


def test_predicates_return_python_bools_for_numpy_scalars():
    assert NS["is_upright"](numpy.float64(70)) is True
    assert NS["is_upright"](numpy.float32(69.9)) is False
    assert NS["is_recovered"](numpy.float64(80)) is True
    assert NS["is_recovered"](numpy.float32(79.9)) is False


# RED cycle A (addendum): head-pitch term.


def test_bowed_head_scores_below_upright():
    xyn_up, vis_up = upright()
    xyn_bowed, vis_bowed = bowed()
    score = NS["posture_score"]
    assert score(xyn_bowed, vis_bowed) < score(xyn_up, vis_up)


def test_hidden_nose_and_eyes_falls_back():
    xyn, _ = upright()
    vis = numpy.full(17, 1.0)
    vis[[NOSE, EYE_L, EYE_R]] = 0.0
    assert NS["posture_score"](xyn, vis) == 100.0


# RED cycle C (aspect revision): normalized x/y units differ on non-square
# frames, so geometry must run in aspect-corrected space (x * W/H).


def observe_through_wide_camera(xyn, aspect=16 / 9):
    observed = numpy.asarray(xyn, dtype=float).copy()
    observed[:, 0] = 0.5 + (observed[:, 0] - 0.5) / aspect
    return observed


def test_aspect_correction_recovers_true_score():
    xyn, vis = upright()
    observed = observe_through_wide_camera(xyn)
    score = NS["posture_score"]
    assert abs(score(observed, vis, aspect=16 / 9) - score(xyn, vis)) < 1e-9


def test_uncorrected_wide_aspect_under_reads_lean():
    # Isolate the neck term: the same ear/shoulder pair reads leaner
    # (higher cosine) when its compressed wide-frame x is used raw.
    xyn, _ = slouched()
    observed = observe_through_wide_camera(xyn)
    verticality = NS["_side_verticality"]
    buggy = verticality(observed[3], observed[5], 1.0, 1.0)
    true = verticality(xyn[3], xyn[5], 1.0, 1.0)
    assert buggy > true


def test_invalid_aspect_raises():
    xyn, vis = upright()
    try:
        NS["posture_score"](xyn, vis, aspect=0.0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_hunched_shoulders_score_below_upright():
    xyn_up, vis_up = upright()
    xyn_hunched, vis_hunched = hunched()
    score = NS["posture_score"]
    assert score(xyn_hunched, vis_hunched) < score(xyn_up, vis_up)
