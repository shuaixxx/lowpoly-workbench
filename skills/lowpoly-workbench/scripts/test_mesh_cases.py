"""Behavior checks for retrieval invariants and review/importance handling."""
import copy
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest
import mesh_cases as M


def fixture(case_id="plane", triangles=False, accepted=False):
    mesh = {"vertices": [[0.,0.,0.],[1.,0.,0.],[1.,1.,0.],[0.,1.,0.]],
            "faces": [[0,1,2],[0,2,3]] if triangles else [[0,1,2,3]]}
    record = {"schema_version":1,"id":case_id,"name":case_id,"scope":"static",
              "status":"accepted" if accepted else "unreviewed", "mesh":mesh,
              "importance":{"author":"synthetic","weights":[0.,None,.5,1.]}}
    if accepted:
        record["review"] = {"by":"user","evidence":"UNIT TEST ONLY - no actual user acceptance"}
    return record


class CasesTest(unittest.TestCase):
    def test_reindex_and_rigid_transform(self):
        original = fixture()["mesh"]
        order = [2,0,3,1]
        remap = {old:new for new,old in enumerate(order)}
        angle = .71
        transformed = {"vertices":[],"faces":[[remap[v] for v in f] for f in reversed(original["faces"])]}
        for i in order:
            x,y,z = original["vertices"][i]
            transformed["vertices"].append([4+3.7*x, -5+3.7*(y*math.cos(angle)-z*math.sin(angle)), 3+3.7*(y*math.sin(angle)+z*math.cos(angle))])
        a,b = M.describe(original),M.describe(transformed)
        self.assertEqual(a["wl_signature"],b["wl_signature"])
        self.assertEqual(a["boundary_loops"],1)
        self.assertTrue(b["planar"])
        for x,y in zip(a["shape_variance_ratios"],b["shape_variance_ratios"]):
            self.assertAlmostEqual(x,y,places=10)

    def test_same_shape_different_connectivity(self):
        a,b = M.describe(fixture()["mesh"]),M.describe(fixture(triangles=True)["mesh"])
        self.assertNotEqual(a["wl_signature"],b["wl_signature"])
        self.assertEqual(a["shape_variance_ratios"],b["shape_variance_ratios"])
        self.assertEqual(a["triangle_equivalent"],b["triangle_equivalent"])

    def test_review_is_not_invented(self):
        r=fixture();r["status"]="accepted"
        with self.assertRaises(ValueError):M.validate_record(r)
        r["status"]="unreviewed"
        M.validate_record(r)
        self.assertEqual(r["importance"]["weights"][0],0.)
        self.assertIsNone(r["importance"]["weights"][1])

    def test_retrieval_scope_quads_and_status(self):
        with tempfile.TemporaryDirectory(prefix=".lowpoly-test-", dir=Path.cwd()) as directory:
            db=Path(directory)/"cases.sqlite3"
            for r in [fixture("quad",accepted=True),fixture("tri",triangles=True,accepted=True),fixture("pending")]:M.add_case(db,r)
            deform=fixture("deform",accepted=True);deform["scope"]="deforming";M.add_case(db,deform)
            found=M.search(db,fixture("query"),quads=True)
            self.assertEqual([r["id"] for r in found["results"]],["quad"])
            found=M.search(db,fixture("query"),quads=True,include_unreviewed=True)
            self.assertEqual({r["id"] for r in found["results"]},{"quad","pending"})

    def test_duplicate_and_invalid_weights(self):
        with tempfile.TemporaryDirectory(prefix=".lowpoly-test-", dir=Path.cwd()) as directory:
            db=Path(directory)/"cases.sqlite3"
            M.add_case(db,fixture())
            with self.assertRaises(sqlite3.IntegrityError):M.add_case(db,fixture())
        r=fixture();r["importance"]["weights"][0]=float("nan")
        with self.assertRaises(ValueError):M.validate_record(r)

    def test_curved_patch(self):
        r=fixture();r["mesh"]["vertices"][2][2]=.2
        self.assertFalse(M.describe(r["mesh"])["planar"])


if __name__=="__main__":unittest.main()
