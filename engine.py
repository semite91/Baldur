"""Baldur Recognition engine: webcam YOLO pose scoring as frozen JSON-lines.

Thin composition only (issue #16): every domain seam (camera, scoring,
dwell events, inference) is reused from the notebook namespaces loaded at
runtime via tests/nb_loader. This module defines no scoring, dwell, or
inference logic itself; orchestration mirrors 04_live_pipeline
(camera -> YOLO -> largest -> posture_score with aspect=W/H -> dwell
update with wall-clock dt -> frozen stdout).

Stdout carries only the 4 frozen events (bad_posture, recovered,
heartbeat, error). All diagnostics go to stderr so the Warning host can
parse stdout blindly.

--preview opens a local "Baldur posture" window with the live score plus
dwell-color box, reusing the 05_live_view overlay through the notebook
loader (no overlay logic lives here). Headless machines keep JSON-lines.

Exit-code contract: 0 clean stop (frames done, q pressed, or Ctrl+C), non-zero with a
reason on failure paths (2 camera unavailable, 3 engine failure mid-loop).
No image, video, keypoint, or score persistence; weights stay out of the
repo (ADR-0002).
"""

import argparse
import json
import sys
import time
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))

from nb_loader import load_notebook

EXIT_OK = 0
EXIT_CAMERA = 2
EXIT_ENGINE = 3

_NOTEBOOK_STEMS = ("00_env_camera", "01_pose_score", "02_events_jsonl", "03_yolo_inference")
_VIEW_STEMS = ("05_live_view",)
_PREVIEW_WINDOW = "Baldur posture"


def _base_dir():
    """Repo root in dev, bundle dir when frozen (PyInstaller onedir).

    PyInstaller v6+ stages everything (including data files) under the
    _MEIPASS dir, so the frozen bundle carries notebooks/ plus the
    nb_loader module and the engine never needs the repo.
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _load_namespaces(stems=_NOTEBOOK_STEMS, notebooks_dir=None):
    root = Path(notebooks_dir) if notebooks_dir is not None else _base_dir() / "notebooks"
    return {stem: load_notebook(str(root / (stem + ".ipynb"))) for stem in stems}


def _preview_frame(viewer, base, width, height, person, state, extra, plotted):
    """Show one annotated overlay frame; return True when the user quits.

    Box corners mirror the 05_live_view viewer (visible keypoints scaled
    to pixels); overlay text plus RULA extra come from the 05
    annotate_frame overlay, and a status line under the score reports
    whether the base image is plotted ("plotted") or the raw frame
    ("not plotted"). Quitting means q pressed or the window's X pressed
    (X only destroys the window, so visibility is probed explicitly or
    the next imshow would silently recreate it). Raises on GUI-backend
    failure so the caller takes the error path.
    """
    box = None
    if person is not None:
        visibility = person["visibility"]
        seen = visibility >= 0.5
        if seen.any():
            xs = person["xyn"][seen, 0] * width
            ys = person["xyn"][seen, 1] * height
            box = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    overlay = viewer["annotate_frame"](base, box, state["last_score"], state["in_bad"], extra)
    cv2mod = viewer["cv2"]
    status = "plotted" if plotted else "not plotted"
    cv2mod.putText(overlay, status, (10, 90), cv2mod.FONT_HERSHEY_SIMPLEX, 1.0,
                   viewer["box_color"](state["in_bad"]), 2)
    cv2mod.imshow(_PREVIEW_WINDOW, overlay)
    if cv2mod.waitKey(1) & 0xFF == ord("q"):
        return True
    try:
        visible = cv2mod.getWindowProperty(_PREVIEW_WINDOW, cv2mod.WND_PROP_VISIBLE)
    except Exception:
        visible = 1
    return visible < 1


def run(source=0, model_path=None, model_fallbacks=None, frames=None,
        capture_factory=None, model=None, dt=None, preview=False):
    """Run the recognition loop; return a process exit code.

    Injectable seams (capture_factory as open_capture, model object, fixed
    dt seconds per frame) keep pytest fully headless. Defaults (None) take
    the live path: default webcam, notebook weights, wall-clock dt, and an
    unbounded loop until Ctrl+C. preview=True opens the local overlay
    window (q quits); the overlay reuses the 05_live_view namespace.
    """
    namespaces = _load_namespaces()
    cam = namespaces["00_env_camera"]
    scoring = namespaces["01_pose_score"]
    dwell = namespaces["02_events_jsonl"]
    yolo = namespaces["03_yolo_inference"]

    if model is None:
        device = yolo["resolve_device"]()
        path = model_path if model_path is not None else yolo["MODEL_NAME"]
        fallbacks = model_fallbacks if model_fallbacks is not None else yolo["FALLBACK_MODELS"]
        print(f"engine: loading {path} (device={device}, source={source})",
              file=sys.stderr, flush=True)
        model, report = yolo["load_pose_model"](path, fallbacks, device=device)
        print("engine: model ready " + json.dumps(report, default=str),
              file=sys.stderr, flush=True)
    else:
        print(f"engine: injected model (source={source})", file=sys.stderr, flush=True)

    viewer = None
    if preview:
        try:
            viewer = _load_namespaces(_VIEW_STEMS)["05_live_view"]
            print("engine: preview on", file=sys.stderr, flush=True)
        except Exception as exc:
            code = getattr(exc, "code", "PREVIEW_UNAVAILABLE")
            message = str(exc) or type(exc).__name__
            dwell["emit_event"]({"event": "error", "code": code, "message": message})
            return EXIT_ENGINE

    try:
        if capture_factory is None:
            cap = cam["open_camera"](source=source)
        else:
            cap = cam["open_camera"](source=source, open_capture=capture_factory)
    except Exception as exc:
        cam["emit_error"](getattr(exc, "code", "CAMERA_UNAVAILABLE"),
                          str(exc) or type(exc).__name__)
        return EXIT_CAMERA

    def score_one(frame, width, height, largest):
        persons = yolo["infer_frame"](model, frame)
        if not persons:
            return None, False
        person = scoring["select_largest_person"](persons)
        largest["person"] = person
        return (
            scoring["posture_score"](person["xyn"], person["visibility"],
                                     aspect=width / height),
            True,
        )

    try:
        try:
            warm_frame = cam["read_frame"](cap)
            yolo["infer_frame"](model, warm_frame)
        except Exception as exc:
            code = getattr(exc, "code", "UPDATE_FAILED")
            message = str(exc) or type(exc).__name__
            dwell["emit_event"]({"event": "error", "code": code, "message": message})
            return EXIT_ENGINE

        state = dwell["new_state"]()
        torso_base = None
        failed = []
        count = 0
        previous = time.monotonic()
        while frames is None or count < frames:
            frame = cam["read_frame"](cap)
            height, width = frame.shape[0], frame.shape[1]
            now = time.monotonic()
            step = dt if dt is not None else now - previous
            previous = now
            largest = {}
            frame_events = dwell["safe_update"](
                state, lambda: score_one(frame, width, height, largest), step,
                on_error=lambda code, message: failed.append(code))
            for event in frame_events:
                dwell["emit_event"](event)
            count += 1
            if failed:
                return EXIT_ENGINE
            if viewer is not None:
                # Display-only doubling: one raw call for the plotted base
                # (YOLO boxes+skeleton, like the 05 viewer); any display
                # failure falls back to the raw frame so events never lie.
                person = largest.get("person")
                base = frame
                plotted = False
                try:
                    raw = model(frame, verbose=False)
                    if raw:
                        base = raw[0].plot()
                        plotted = True
                except Exception:
                    base = frame
                    plotted = False
                extra = "RULA --"
                if person is not None:
                    torso_base = scoring["note_torso"](
                        torso_base, person["xyn"], person["visibility"])
                    grand = scoring["grand_score"](
                        person["xyn"], person["visibility"], torso_base)
                    if grand is not None:
                        extra = f"RULA {grand[0]}/A{grand[1]}"
                if _preview_frame(viewer, base, width, height, person, state, extra, plotted):
                    print("engine: preview quit", file=sys.stderr, flush=True)
                    break
    except KeyboardInterrupt:
        print("engine: interrupted", file=sys.stderr, flush=True)
        return EXIT_OK
    except Exception as exc:
        code = getattr(exc, "code", "UPDATE_FAILED")
        message = str(exc) or type(exc).__name__
        dwell["emit_event"]({"event": "error", "code": code, "message": message})
        return EXIT_ENGINE
    finally:
        cam["release_camera"](cap)
        if viewer is not None:
            try:
                viewer["cv2"].destroyAllWindows()
            except Exception:
                pass
    print(f"engine: done ({count} frames)", file=sys.stderr, flush=True)
    return EXIT_OK


def main(argv=None):
    """CLI entry: parse args, run the loop, return the exit code."""
    parser = argparse.ArgumentParser(
        prog="engine.py",
        description="Baldur posture Recognition engine (frozen JSON-lines on stdout).")
    parser.add_argument("--source", type=int, default=0, help="webcam source index")
    parser.add_argument("--model", default=None, help="weights path (default: notebook MODEL_NAME)")
    parser.add_argument("--fallbacks", nargs="*", default=None,
                        help="fallback weights tried in order (default: notebook FALLBACK_MODELS)")
    parser.add_argument("--frames", type=int, default=None,
                        help="stop after N frames (default: run until Ctrl+C)")
    parser.add_argument("--preview", action="store_true",
                        help="show the local camera/score window (q quits)")
    args = parser.parse_args(argv)
    return run(source=args.source, model_path=args.model,
               model_fallbacks=args.fallbacks, frames=args.frames,
               preview=args.preview)


if __name__ == "__main__":
    sys.exit(main())
