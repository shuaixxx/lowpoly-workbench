"""Real-mesh case storage and coarse structural retrieval, standard library only."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def eigenvalues3(matrix):
    a = [row[:] for row in matrix]
    for _ in range(40):
        p, q = max(((0, 1), (0, 2), (1, 2)), key=lambda ij: abs(a[ij[0]][ij[1]]))
        if abs(a[p][q]) <= max(1e-30, sum(abs(a[i][i]) for i in range(3)) * 1e-14):
            break
        angle = .5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
        c, s = math.cos(angle), math.sin(angle)
        app, aqq, apq = a[p][p], a[q][q], a[p][q]
        for k in range(3):
            if k not in (p, q):
                akp, akq = a[k][p], a[k][q]
                a[k][p] = a[p][k] = c * akp - s * akq
                a[k][q] = a[q][k] = s * akp + c * akq
        a[p][p] = c*c*app - 2*s*c*apq + s*s*aqq
        a[q][q] = s*s*app + 2*s*c*apq + c*c*aqq
        a[p][q] = a[q][p] = 0.
    return sorted((max(0., a[i][i]) for i in range(3)), reverse=True)


def validate_mesh(mesh):
    vertices, faces = mesh.get("vertices"), mesh.get("faces")
    if not isinstance(vertices, list) or len(vertices) < 3 or not isinstance(faces, list) or not faces:
        raise ValueError("A mesh needs at least three vertices and one face")
    for p in vertices:
        if len(p) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in p):
            raise ValueError("Vertices must be finite XYZ triples")
    for f in faces:
        if len(f) < 3 or len(set(f)) != len(f):
            raise ValueError("A face needs at least three distinct indices")
        if any(type(i) is not int or i < 0 or i >= len(vertices) for i in f):
            raise ValueError("Face index outside the vertex array")


def describe(mesh):
    validate_mesh(mesh)
    vertices, faces = mesh["vertices"], mesh["faces"]
    edges = defaultdict(list)
    adjacent = [set() for _ in vertices]
    for fi, face in enumerate(faces):
        for a, b in zip(face, face[1:] + face[:1]):
            edges[tuple(sorted((a, b)))].append(fi)
            adjacent[a].add(b)
            adjacent[b].add(a)
    border = defaultdict(set)
    for (a, b), incident in edges.items():
        if len(incident) == 1:
            border[a].add(b)
            border[b].add(a)

    def components(graph):
        seen, total = set(), 0
        for start in graph:
            if start in seen:
                continue
            total += 1
            todo = [start]
            seen.add(start)
            while todo:
                for nxt in graph[todo.pop()]:
                    if nxt not in seen:
                        seen.add(nxt)
                        todo.append(nxt)
        return total

    loops = components(border) if all(len(v) == 2 for v in border.values()) else None
    center = [sum(p[i] for p in vertices)/len(vertices) for i in range(3)]
    cov = [[sum((p[i]-center[i])*(p[j]-center[j]) for p in vertices)/len(vertices) for j in range(3)] for i in range(3)]
    eig = eigenvalues3(cov)
    ratios = [x/sum(eig) for x in eig] if sum(eig) else [0., 0., 0.]
    # Vertex/edge/face incidence graph. WL is not a complete graph-isomorphism test.
    graph = [set() for _ in range(len(vertices)+len(edges)+len(faces))]
    labels = [f"V:{len(adjacent[i])}:{int(i in border)}" for i in range(len(vertices))]
    labels += [f"E:{len(incident)}" for incident in edges.values()]
    labels += [f"F:{len(f)}" for f in faces]
    face_offset = len(vertices)+len(edges)
    for ei, ((a, b), incident) in enumerate(edges.items(), len(vertices)):
        for other in (a, b, *(face_offset+f for f in incident)):
            graph[ei].add(other)
            graph[other].add(ei)
    colors = [digest(label) for label in labels]
    for _ in range(4):
        colors = [digest([colors[i], sorted(colors[j] for j in graph[i])]) for i in range(len(graph))]
    return {
        "vertices": len(vertices), "edges": len(edges), "faces": len(faces),
        "triangle_equivalent": sum(len(f)-2 for f in faces),
        "face_arities": dict(Counter(str(len(f)) for f in faces)),
        "vertex_valences": dict(Counter(str(len(n)) for n in adjacent)),
        "boundary_loops": loops, "boundary_vertices": len(border),
        "components": components(dict(enumerate(adjacent))),
        "nonmanifold_edges": sum(len(n)>2 for n in edges.values()),
        "euler": len(vertices)-len(edges)+len(faces),
        "all_quads": all(len(f)==4 for f in faces),
        "planar": ratios[2]<1e-6, "shape_variance_ratios": ratios,
        "wl_signature": digest(sorted(colors)), "mesh_sha256": digest(mesh),
    }


def validate_record(record):
    if record.get("schema_version") != 1:
        raise ValueError("Unsupported case schema")
    if not record.get("id") or not record.get("name"):
        raise ValueError("Case id and name are required")
    if record.get("scope") not in ("static", "deforming", "unspecified"):
        raise ValueError("Invalid scope")
    status = record.get("status", "unreviewed")
    if status not in ("unreviewed", "accepted", "rejected", "failed"):
        raise ValueError("Invalid status")
    if status in ("accepted", "rejected"):
        review = record.get("review", {})
        if review.get("by") != "user" or not review.get("evidence"):
            raise ValueError("User review evidence is required for accepted/rejected cases")
    validate_mesh(record["mesh"])
    weights = record.get("importance", {}).get("weights")
    if weights is not None:
        if len(weights) != len(record["mesh"]["vertices"]):
            raise ValueError("Importance weights must correspond to case vertices")
        if any(w is not None and (isinstance(w, bool) or not isinstance(w, (int, float)) or not math.isfinite(w) or not 0<=w<=1) for w in weights):
            raise ValueError("Importance values must be null or finite numbers from 0 to 1")


@contextmanager
def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, status TEXT NOT NULL, boundary_loops INTEGER, planar INTEGER NOT NULL, all_quads INTEGER NOT NULL, record_json TEXT NOT NULL, descriptor_json TEXT NOT NULL, created_at TEXT NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS case_filter ON cases(status,boundary_loops,planar,all_quads)")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def add_case(path, record):
    validate_record(record)
    d = describe(record["mesh"])
    with connect(path) as conn:
        conn.execute("INSERT INTO cases VALUES(?,?,?,?,?,?,?,?)", (
            record["id"], record.get("status", "unreviewed"), d["boundary_loops"], int(d["planar"]),
            int(d["all_quads"]), canonical_json(record), canonical_json(d), datetime.now(timezone.utc).isoformat()))
    return d


def search(path, query, *, quads=False, lock_boundary=False, same_signature=False, include_unreviewed=False, limit=5):
    validate_record(query)
    q = describe(query["mesh"])
    clauses = ["status IN ("+("?,?" if include_unreviewed else "?")+")", "planar = ?"]
    params = ["accepted"] + (["unreviewed"] if include_unreviewed else []) + [int(q["planar"])]
    if q["boundary_loops"] is not None:
        clauses.append("boundary_loops = ?")
        params.append(q["boundary_loops"])
    if quads:
        clauses.append("all_quads = 1")
    with connect(path) as conn:
        rows = conn.execute("SELECT record_json,descriptor_json FROM cases WHERE "+" AND ".join(clauses), params).fetchall()
    found = []
    for raw, desc_raw in rows:
        case, d = json.loads(raw), json.loads(desc_raw)
        if query["scope"] != "unspecified" and case["scope"] not in ("unspecified", query["scope"]):
            continue
        if d["components"] != q["components"] or d["nonmanifold_edges"]:
            continue
        if lock_boundary and d["boundary_vertices"] != q["boundary_vertices"]:
            continue
        if same_signature and d["wl_signature"] != q["wl_signature"]:
            continue
        distance = math.sqrt(sum((a-b)**2 for a,b in zip(d["shape_variance_ratios"], q["shape_variance_ratios"])))
        reasons = ["same_planarity", "compatible_scope", "same_components"]
        if q["boundary_loops"] is not None:
            reasons.append("same_boundary_loop_count")
        if quads:
            reasons.append("all_quads")
        found.append({"id": case["id"], "name": case["name"], "status": case.get("status", "unreviewed"),
            "descriptor_distance": distance, "matched": reasons,
            "boundary_vertices_match": d["boundary_vertices"]==q["boundary_vertices"],
            "wl_signature_match": d["wl_signature"]==q["wl_signature"], "descriptor": d,
            "requires": ["boundary_correspondence_check", "visual_review", "importance_mapping_check"]})
    return {"query": query["id"], "query_descriptor": q,
        "method": "coarse_structural_filter_and_covariance_ranking_v1", "quality_score": None,
        "results": sorted(found, key=lambda x:(x["descriptor_distance"],x["id"]))[:limit]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("--db", required=True)
    add.add_argument("--record", required=True)
    lookup = sub.add_parser("search")
    lookup.add_argument("--db", required=True)
    lookup.add_argument("--query", required=True)
    for flag in ("quads", "lock-boundary", "same-signature", "include-unreviewed"):
        lookup.add_argument("--"+flag, action="store_true")
    lookup.add_argument("--limit", type=int, default=5)
    stats = sub.add_parser("stats")
    stats.add_argument("--db", required=True)
    args = parser.parse_args()
    if args.command == "add":
        output = add_case(args.db, json.loads(Path(args.record).read_text(encoding="utf-8")))
    elif args.command == "search":
        output = search(args.db, json.loads(Path(args.query).read_text(encoding="utf-8")), quads=args.quads,
            lock_boundary=args.lock_boundary, same_signature=args.same_signature,
            include_unreviewed=args.include_unreviewed, limit=args.limit)
    else:
        with connect(args.db) as conn:
            output = dict(conn.execute("SELECT status,COUNT(*) FROM cases GROUP BY status"))
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
