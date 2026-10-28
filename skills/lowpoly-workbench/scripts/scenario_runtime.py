"""Load pinned Scenario tools without requiring a different MCP bridge."""
from pathlib import Path
import importlib
import sys

UPSTREAM_COMMIT = "d44410f058991f677ccf733a8e86ce95110857eb"


def load_backend(root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    paths = [root / "scenario-blender-expert" / "scripts", root / "scenario-blender-retopology" / "scripts"]
    for path in paths:
        if not path.is_dir():
            raise FileNotFoundError(f"Missing Scenario skill scripts: {path}")
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    modules = tuple(importlib.import_module(name) for name in ("bx_retopo", "bx_audit", "bx_review"))
    for module, path in zip(modules, [paths[1], paths[0], paths[0]]):
        if Path(module.__file__).resolve().parent != path.resolve():
            raise RuntimeError(f"An unrelated module is already loaded: {module.__file__}")
    return modules


def review_meshes(review_module, objects, out_dir, **kwargs):
    """Avoid Workbench in-front cages occluding their wire overlays; restore caller state."""
    state = [(obj, obj.show_in_front) for obj in objects]
    try:
        for obj, _ in state:
            obj.show_in_front = False
        return review_module.review(objects, str(out_dir), **kwargs)
    finally:
        for obj, in_front in state:
            obj.show_in_front = in_front
