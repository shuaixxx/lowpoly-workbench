"""Blender-side importance channel, read-only mesh export, and geometry-stage audit."""
from pathlib import Path
import json
import bpy
import bmesh

IMPORTANCE_GROUP = "lp_importance"


def ensure_importance_channel(obj):
    if obj.type != "MESH":
        raise TypeError("Importance needs a mesh")
    # Deliberately create no assignments: unknown remains distinct from painted zero.
    group = obj.vertex_groups.get(IMPORTANCE_GROUP)
    if group is None:
        group = obj.vertex_groups.new(name=IMPORTANCE_GROUP)
    return group


def importance_values(obj, indices=None):
    group = obj.vertex_groups.get(IMPORTANCE_GROUP)
    indices = list(range(len(obj.data.vertices))) if indices is None else list(indices)
    if group is None:
        return [None] * len(indices)
    return [next((float(g.weight) for g in obj.data.vertices[i].groups if g.group == group.index), None) for i in indices]


def audit_geometry(obj):
    if obj.type != "MESH" or obj.mode != "OBJECT":
        raise ValueError("Audit an Object Mode mesh, or first read an isolated copy")
    raw = obj.data
    bm = bmesh.new()
    try:
        bm.from_mesh(raw)
        topology = {
            "boundary_edges": sum(e.is_boundary for e in bm.edges),
            "nonmanifold_edges_excluding_boundaries": sum(not e.is_manifold and not e.is_boundary for e in bm.edges),
            "loose_vertices": sum(not v.link_faces for v in bm.verts),
            "zero_area_faces": sum(f.calc_area() <= 1e-12 for f in bm.faces),
        }
    finally:
        bm.free()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        evaluated_counts = {"vertices": len(mesh.vertices), "faces": len(mesh.polygons), "triangles": len(mesh.loop_triangles)}
    finally:
        evaluated.to_mesh_clear()
    weights = importance_values(obj)
    assigned = [w for w in weights if w is not None]
    return {
        "object": obj.name, "blender_version": bpy.app.version_string,
        "control": {"vertices": len(raw.vertices), "faces": len(raw.polygons),
                    "quads": sum(len(f.vertices) == 4 for f in raw.polygons)},
        "evaluated": evaluated_counts, "topology": topology,
        "importance": {"group": IMPORTANCE_GROUP, "assigned": len(assigned), "unassigned": len(weights)-len(assigned),
                       "explicit_zero": sum(w == 0. for w in assigned), "ready": len(assigned) == len(weights) and bool(weights)},
        "uv_layers": len(raw.uv_layers), "modifiers": [m.type for m in obj.modifiers],
        "bake_verified": False, "user_review": "pending",
    }


def mesh_record(obj, case_id, *, face_indices=None, provenance=None, scope="static", importance_author=None):
    if obj.type != "MESH" or obj.mode != "OBJECT":
        raise ValueError("Export an Object Mode mesh; do not read stale Edit Mode arrays")
    polys = list(obj.data.polygons) if face_indices is None else [obj.data.polygons[i] for i in face_indices]
    used = sorted({i for f in polys for i in f.vertices})
    mapping = {old: new for new, old in enumerate(used)}
    weights = importance_values(obj, used)
    if importance_author not in (None, "user", "synthetic", "unknown", "unassigned"):
        raise ValueError("Unknown importance author")
    return {
        "schema_version": 1, "id": case_id, "name": obj.name, "status": "unreviewed", "scope": scope,
        "mesh": {"vertices": [list(obj.data.vertices[i].co) for i in used],
                 "faces": [[mapping[i] for i in f.vertices] for f in polys]},
        "importance": {"channel": IMPORTANCE_GROUP,
                       "author": importance_author or ("unknown" if any(w is not None for w in weights) else "unassigned"),
                       "weights": weights},
        "transform": [list(row) for row in obj.matrix_world],
        "provenance": provenance or {"kind": "mesh-export", "object": obj.name, "source_file": bpy.data.filepath},
        "source_vertex_indices": used, "source_face_indices": [f.index for f in polys],
        "rule_ids": [], "related_case_ids": [],
        "notes": "Control mesh; modifier evaluation is audited separately. Weight authorship requires review.",
    }


def export_patch(obj, path, *, case_id=None, face_indices=None, provenance=None, scope="static", importance_author=None):
    record = mesh_record(obj, case_id or Path(path).stem, face_indices=face_indices, provenance=provenance, scope=scope, importance_author=importance_author)
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"Use a new version instead of overwriting {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record
