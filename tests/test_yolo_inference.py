"""T6 (issue #6) - YOLO inference wiring, RED cycle 1: loader + extraction.

Seams: load_pose_model(path, fallbacks, loader) with injectable loader;
extract_persons(result) over torch-or-numpy keypoints/boxes.
"""

from pathlib import Path

import numpy
import torch

from nb_loader import load_notebook

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "03_yolo_inference.ipynb"

NS = load_notebook(str(NOTEBOOK))


class FakeKeypoints:
    def __init__(self, xyn, data):
        self.xyn = xyn
        self.data = data


class FakeBoxes:
    def __init__(self, xyxy):
        self.xyxy = xyxy


class FakeResult:
    def __init__(self, xyn, vis, xyxy):
        data = numpy.zeros((xyn.shape[0], 17, 3))
        data[:, :, :2] = xyn
        data[:, :, 2] = vis
        self.keypoints = FakeKeypoints(xyn, data)
        self.boxes = FakeBoxes(xyxy) if xyxy is not None else None


def person_xyn(ear_shift=0.0):
    xyn = numpy.zeros((17, 2))
    xyn[0] = (0.50, 0.34)
    xyn[1] = (0.47, 0.32)
    xyn[2] = (0.53, 0.32)
    xyn[3] = (0.45 + ear_shift, 0.30)
    xyn[4] = (0.55 + ear_shift, 0.30)
    xyn[5] = (0.45, 0.45)
    xyn[6] = (0.55, 0.45)
    xyn[11] = (0.46, 0.65)
    xyn[12] = (0.54, 0.65)
    return xyn


class BoundModel:
    def __init__(self, name):
        self.name = name
        self.devices = []

    def to(self, device):
        self.devices.append(device)
        return self


def recording_loader(seen, behavior):
    def loader(name, task=None, verbose=False):
        seen.append({"name": name, "task": task, "verbose": verbose})
        return behavior(name)

    return loader


def test_loader_called_once_with_primary():
    seen = []
    model, report = NS["load_pose_model"](
        "yolo26n-pose.pt",
        fallbacks=(),
        loader=recording_loader(seen, BoundModel),
        device="cpu",
    )
    assert seen == [{"name": "yolo26n-pose.pt", "task": "pose", "verbose": False}]
    assert report == {"model": "yolo26n-pose.pt", "task": "pose", "device": "cpu"}
    assert model.devices == ["cpu"]


def test_missing_primary_falls_back_and_binds_device():
    def behavior(name):
        if name == "yolo26n-pose.pt":
            raise FileNotFoundError("no such weights")
        return BoundModel(name)

    seen = []
    model, report = NS["load_pose_model"](
        "yolo26n-pose.pt",
        fallbacks=("yolo11n-pose.pt",),
        loader=recording_loader(seen, behavior),
        device="cpu",
    )
    assert report == {"model": "yolo11n-pose.pt", "task": "pose", "device": "cpu"}
    assert model.devices == ["cpu"]


def test_missing_weights_raise_machine_code():
    def loader(name, **kwargs):
        raise FileNotFoundError("no such weights")

    InferenceError = NS["InferenceError"]
    try:
        NS["load_pose_model"]("nope.pt", fallbacks=("alsono.pt",), loader=loader)
    except InferenceError as exc:
        assert exc.code == "WEIGHTS_UNAVAILABLE"
    else:
        raise AssertionError("expected InferenceError")


def test_resolve_device_prefers_cuda(monkeypatch):
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert NS["resolve_device"]() == "cuda"


def test_resolve_device_falls_back_to_mps(monkeypatch):
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)
    assert NS["resolve_device"]() == "mps"


def test_resolve_device_cpu_last_resort(monkeypatch):
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    assert NS["resolve_device"]() == "cpu"


def test_explicit_device_wins_over_cuda(monkeypatch):
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    seen = []
    model, report = NS["load_pose_model"](
        "yolo26n-pose.pt",
        fallbacks=(),
        loader=recording_loader(seen, BoundModel),
        device="cpu",
    )
    assert report["device"] == "cpu"
    assert model.devices == ["cpu"]


def test_default_device_resolves(monkeypatch):
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    seen = []
    model, report = NS["load_pose_model"](
        "yolo26n-pose.pt", fallbacks=(), loader=recording_loader(seen, BoundModel)
    )
    assert report["device"] == "cpu"


def test_extract_persons_shapes_and_areas():
    xyn = numpy.stack([person_xyn(), person_xyn(ear_shift=0.02)])
    vis = numpy.full((2, 17), 1.0)
    xyxy = numpy.array([[10.0, 20.0, 110.0, 220.0], [0.0, 0.0, 50.0, 50.0]])
    persons = NS["extract_persons"](FakeResult(xyn, vis, xyxy))
    assert len(persons) == 2
    assert persons[0]["area"] == 100.0 * 200.0
    assert persons[1]["area"] == 50.0 * 50.0
    for person in persons:
        assert person["xyn"].shape == (17, 2)
        assert person["visibility"].shape == (17,)
        assert isinstance(person["xyn"], numpy.ndarray)


def test_extract_empty_result_yields_empty_list():
    assert NS["extract_persons"](FakeResult(numpy.zeros((0, 17, 2)), numpy.zeros((0, 17)), numpy.zeros((0, 4)))) == []


def test_extract_missing_keypoints_yields_empty_list():
    class EmptyResult:
        keypoints = None
        boxes = None

    assert NS["extract_persons"](EmptyResult()) == []


def test_extract_converts_torch_tensors():
    xyn = torch.zeros(1, 17, 2)
    xyn[0, 5] = torch.tensor([0.45, 0.45])
    data = torch.zeros(1, 17, 3)
    data[0, :, 2] = 1.0
    xyxy = torch.tensor([[0.0, 0.0, 10.0, 10.0]])

    class TorchKeypoints:
        pass

    class TorchResult:
        pass

    kp, res = TorchKeypoints(), TorchResult()
    kp.xyn, kp.data = xyn, data
    res.keypoints = kp
    res.boxes = FakeBoxes(xyxy)
    persons = NS["extract_persons"](res)
    assert len(persons) == 1
    assert isinstance(persons[0]["xyn"], numpy.ndarray)
    assert persons[0]["area"] == 100.0


def test_missing_boxes_falls_back_to_keypoint_spread():
    xyn = numpy.stack([person_xyn()])
    vis = numpy.full((1, 17), 1.0)
    persons = NS["extract_persons"](FakeResult(xyn, vis, None))
    assert len(persons) == 1
    assert persons[0]["area"] > 0.0


# RED cycle 2: frame inference + live smoke + scorer wiring + persistence.


class FakeModel:
    def __init__(self, results=None, error=None):
        self.results = results if results is not None else []
        self.error = error
        self.calls = []

    def __call__(self, frame, verbose=False):
        self.calls.append(frame)
        if self.error is not None:
            raise self.error
        return self.results


def test_infer_frame_returns_persons():
    xyn = numpy.stack([person_xyn()])
    vis = numpy.full((1, 17), 1.0)
    xyxy = numpy.array([[0.0, 0.0, 10.0, 10.0]])
    model = FakeModel(results=[FakeResult(xyn, vis, xyxy)])
    frame = numpy.zeros((480, 640, 3), dtype=numpy.uint8)
    persons = NS["infer_frame"](model, frame)
    assert len(persons) == 1
    assert model.calls == [frame]


def test_infer_frame_empty_results_yields_empty_list():
    assert NS["infer_frame"](FakeModel(results=[]), None) == []


def test_infer_frame_failure_carries_machine_code():
    InferenceError = NS["InferenceError"]
    try:
        NS["infer_frame"](FakeModel(error=RuntimeError("cuda gone")), None)
    except InferenceError as exc:
        assert exc.code == "INFERENCE_FAILED"
    else:
        raise AssertionError("expected InferenceError")


def test_infer_frame_passes_through_inference_error():
    InferenceError = NS["InferenceError"]
    try:
        NS["infer_frame"](
            FakeModel(error=InferenceError("WEIGHTS_UNAVAILABLE", "gone")), None
        )
    except InferenceError as exc:
        assert exc.code == "WEIGHTS_UNAVAILABLE"
    else:
        raise AssertionError("expected InferenceError")


LIVE_WEIGHTS = Path("B:/baldur-models/yolo26n-pose.pt")
LIVE_IMAGE = Path("C:/Users/samih/AppData/Local/Temp/opencode/bus.jpg")
LIVE_AVAILABLE = LIVE_WEIGHTS.exists() and LIVE_IMAGE.exists()


def test_live_smoke_shapes_and_indices():
    if not LIVE_AVAILABLE:
        import pytest

        pytest.skip("live weights/image absent")
    from ultralytics import YOLO

    model = YOLO(str(LIVE_WEIGHTS))
    persons = NS["infer_frame"](model, str(LIVE_IMAGE))
    assert len(persons) >= 1
    for person in persons:
        assert person["xyn"].shape == (17, 2)
        assert person["visibility"].shape == (17,)
    assert all(p["area"] >= 0.0 for p in persons)


def test_extracted_largest_feeds_scorer():
    from nb_loader import load_notebook as load

    scoring = load(
        Path(__file__).resolve().parents[1] / "notebooks" / "01_pose_score.ipynb"
    )
    xyn = numpy.stack([person_xyn(), person_xyn(ear_shift=0.02)])
    vis = numpy.full((2, 17), 1.0)
    xyxy = numpy.array([[10.0, 20.0, 110.0, 220.0], [0.0, 0.0, 50.0, 50.0]])
    persons = NS["extract_persons"](FakeResult(xyn, vis, xyxy))
    largest = scoring["select_largest_person"](persons)
    assert largest["area"] == 100.0 * 200.0
    score = scoring["posture_score"](largest["xyn"], largest["visibility"])
    assert score is None or 0 <= score <= 100


def test_inference_writes_no_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    xyn = numpy.stack([person_xyn()])
    vis = numpy.full((1, 17), 1.0)
    xyxy = numpy.array([[0.0, 0.0, 10.0, 10.0]])
    result = FakeResult(xyn, vis, xyxy)
    NS["extract_persons"](result)
    NS["extract_persons"](result)
    NS["infer_frame"](FakeModel(results=[result]), None)
    assert list(tmp_path.iterdir()) == []
