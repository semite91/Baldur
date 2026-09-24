"""Minimal notebook-as-module loader (stdlib only).

Reads code cells from an .ipynb file and executes them in a fresh
namespace, mirroring the NotebookLoader exec-cells-as-module pattern
(Context7: /jupyter/notebook). Cells containing the DEMO marker are
skipped so importing never touches real hardware. Magics are rejected:
scoring/camera logic must stay importable with no magic dependencies.
"""

import json

DEMO_MARKER = "# DEMO"


def load_notebook(path):
    with open(path, encoding="utf-8") as handle:
        notebook = json.load(handle)
    namespace = {}
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        if DEMO_MARKER in source:
            continue
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("%") or stripped.startswith("!"):
                raise ValueError("magics are not allowed in importable cells")
        exec(compile(source, str(path), "exec"), namespace)
    return namespace
