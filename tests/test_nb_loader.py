"""Loader contract: importable cells load, LIVE cells never do."""

import json
from pathlib import Path

from nb_loader import load_notebook


def test_loader_skips_live_cells(tmp_path):
    notebook = {
        "cells": [
            {"cell_type": "code", "source": ["ran_live = True  # LIVE\n"]},
            {"cell_type": "code", "source": ["ran_pure = True\n"]},
            {"cell_type": "markdown", "source": ["# notes\n"]},
        ]
    }
    path = tmp_path / "probe.ipynb"
    path.write_text(json.dumps(notebook), encoding="utf-8")
    namespace = load_notebook(str(path))
    assert "ran_live" not in namespace
    assert namespace["ran_pure"] is True


def test_shipped_notebooks_import_without_side_effects(capsys):
    root = Path(__file__).resolve().parents[1] / "notebooks"
    for name in (
        "00_env_camera.ipynb",
        "01_pose_score.ipynb",
        "02_events_jsonl.ipynb",
        "03_yolo_inference.ipynb",
        "04_live_pipeline.ipynb",
    ):
        load_notebook(str(root / name))
    assert capsys.readouterr().out == ""
