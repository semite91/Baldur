"""T7 (issue #8) - RULA frontal subset, RED cycle 1: bands engine.

Seam: pure band functions over (xyn, visibility), each returning
(value, confidence). Thresholds synthetic-calibrated, pending the
kappa validation protocol.
"""

from pathlib import Path

import numpy

from nb_loader import load_notebook

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "01_pose_score.ipynb"

NS = load_notebook(str(NOTEBOOK))

NOSE, EYE_L, EYE_R = 0, 1, 2
EAR_L, EAR_R, SHOULDER_L, SHOULDER_R = 3, 4, 5, 6
HIP_L, HIP_R = 11, 12


def person(nose=(0.50, 0.34), eye_l=(0.47, 0.32), eye_r=(0.53, 0.32),
           ear_l=(0.45, 0.30), ear_r=(0.55, 0.30),
           sh_l=(0.45, 0.45), sh_r=(0.55, 0.45),
           hip_l=(0.46, 0.65), hip_r=(0.54, 0.65), vis=1.0):
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
    return xyn, numpy.full(17, vis)


def upright():
    return person()


def slouched():
    return person(nose=(0.56, 0.42))


def turned():
    return person(nose=(0.545, 0.33))


def unlevel():
    return person(sh_l=(0.45, 0.43), sh_r=(0.55, 0.47))


def tilted_both():
    return person(sh_l=(0.45, 0.43), sh_r=(0.55, 0.47),
                  hip_l=(0.46, 0.63), hip_r=(0.54, 0.67))


def twisted_torso():
    return person(hip_l=(0.46, 0.63), hip_r=(0.54, 0.67))


def crouched():
    return person(hip_l=(0.46, 0.61), hip_r=(0.54, 0.61))


def test_neck_base_upright_band_one():
    xyn, vis = upright()
    assert NS["neck_base"](xyn, vis) == (1, "low")


def test_neck_base_slouch_band_three():
    xyn, vis = slouched()
    assert NS["neck_base"](xyn, vis) == (3, "low")


def test_neck_twist_adjuster():
    xyn_up, vis_up = upright()
    xyn_turned, vis_turned = turned()
    assert NS["neck_twist"](xyn_up, vis_up) == (0, "high")
    assert NS["neck_twist"](xyn_turned, vis_turned) == (1, "high")


def test_neck_twist_unseen_is_none():
    xyn, _ = upright()
    assert NS["neck_twist"](xyn, numpy.zeros(17))[0] is None


def test_neck_sidebend_adjuster():
    xyn_up, vis_up = upright()
    xyn_tilt, vis_tilt = unlevel()
    assert NS["neck_sidebend"](xyn_up, vis_up) == (0, "high")
    assert NS["neck_sidebend"](xyn_tilt, vis_tilt) == (1, "high")


def test_trunk_sidebend_adjuster():
    xyn_up, vis_up = upright()
    xyn_tilt, vis_tilt = tilted_both()
    assert NS["trunk_sidebend"](xyn_up, vis_up) == (0, "high")
    assert NS["trunk_sidebend"](xyn_tilt, vis_tilt) == (1, "high")


def test_trunk_twist_adjuster():
    xyn_up, vis_up = upright()
    xyn_twist, vis_twist = twisted_torso()
    assert NS["trunk_twist"](xyn_up, vis_up) == (0, "high")
    assert NS["trunk_twist"](xyn_twist, vis_twist) == (1, "high")


def test_trunk_base_against_baseline():
    xyn_up, vis_up = upright()
    xyn_low, vis_low = crouched()
    assert NS["trunk_base"](xyn_up, vis_up, baseline_torso=0.20) == (1, "low")
    assert NS["trunk_base"](xyn_low, vis_low, baseline_torso=0.20) == (2, "low")


def test_limb_defaults_flagged_assumed():
    defaults = NS["limb_defaults"]()
    assert defaults["legs"][1] == "assumed"
    assert all(flag == "assumed" for _, flag in defaults.values())


def test_hidden_everything_returns_none():
    xyn, _ = upright()
    vis = numpy.zeros(17)
    for name in ("neck_base", "neck_twist", "neck_sidebend", "trunk_base",
                 "trunk_twist", "trunk_sidebend"):
        fn = NS[name]
        if name == "trunk_base":
            assert fn(xyn, vis, baseline_torso=0.20)[0] is None
        else:
            assert fn(xyn, vis)[0] is None


# RED cycle 2: transcribed Tables A/B/C plus grand score (worksheet values).


def test_table_a_defaults_and_corners():
    table_a = NS["table_a"]
    assert table_a(2, 2, 2, 1) == 3
    assert table_a(1, 1, 1, 1) == 1
    assert table_a(6, 3, 4, 2) == 9


def test_table_b_spots():
    table_b = NS["table_b"]
    assert table_b(1, 1, 1) == 1
    assert table_b(5, 2, 1) == 7
    assert table_b(3, 3, 1) == 4


def test_table_c_spots_and_clamps():
    table_c = NS["table_c"]
    assert table_c(4, 2) == 3
    assert table_c(1, 1) == 1
    assert table_c(9, 9) == 7


def test_region_scores_apply_muscle_and_force():
    score_c, score_d = NS["score_c"], NS["score_d"]
    assert score_c(3) == 4
    assert score_d(1) == 2
    assert score_c(3, muscle=0, force=0) == 3
    assert score_d(7, muscle=0, force=2) == 9


def test_grand_upright_slouch_hidden():
    grand_score = NS["grand_score"]
    xyn_up, vis_up = upright()
    xyn_sl, vis_sl = slouched()
    assert grand_score(xyn_up, vis_up, baseline_torso=0.20) == (3, 2)
    assert grand_score(xyn_sl, vis_sl, baseline_torso=0.20) == (6, 3)
    xyn_hidden, _ = upright()
    assert grand_score(xyn_hidden, numpy.zeros(17), baseline_torso=0.20) is None


def test_action_levels():
    action_level = NS["action_level"]
    assert [action_level(g) for g in (1, 2, 3, 4, 5, 6, 7)] == [1, 1, 2, 2, 3, 3, 4]


def test_limb_defaults_include_wrist_twist():
    assert NS["limb_defaults"]()["wrist_twist"] == (1, "assumed")


def test_hidden_hips_default_trunk_in_grand():
    grand_score = NS["grand_score"]
    xyn, _ = upright()
    vis = numpy.full(17, 1.0)
    vis[[11, 12]] = 0.0
    assert grand_score(xyn, vis, baseline_torso=0.20) == (3, 2)


# Viewer RULA overlay: running-max torso baseline (in-memory only).


def test_first_measurement_sets_baseline():
    xyn, vis = upright()
    assert abs(NS["note_torso"](None, xyn, vis) - 0.20) < 1e-9


def test_taller_torso_ratchets_baseline_up():
    xyn, vis = upright()
    assert abs(NS["note_torso"](0.15, xyn, vis) - 0.20) < 1e-9


def test_shorter_torso_never_lowers_baseline():
    xyn, vis = upright()
    assert NS["note_torso"](0.25, xyn, vis) == 0.25


def test_unmeasurable_frame_holds_baseline():
    xyn, _ = upright()
    vis = numpy.zeros(17)
    assert NS["note_torso"](0.18, xyn, vis) == 0.18
    assert NS["note_torso"](None, xyn, vis) is None
