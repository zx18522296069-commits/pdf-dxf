from __future__ import annotations

import unittest

from src.simple_constraint_completion import complete_provable_chamfer_box_constraints


def _base(points, chamfers):
    dims = [
        {
            "kind": "linear", "axis": "x",
            "from": {"type": "outer_extreme", "axis": "x", "high": False},
            "to": {"type": "outer_extreme", "axis": "x", "high": True},
            "reason": "PDF总长",
        },
        {
            "kind": "linear", "axis": "y",
            "from": {"type": "outer_extreme", "axis": "y", "high": False},
            "to": {"type": "outer_extreme", "axis": "y", "high": True},
            "reason": "PDF总高",
        },
    ]
    for segment, reason in chamfers:
        dims.append({
            "kind": "chamfer", "axis": "aligned",
            "from": {"type": "segment", "contour_index": 0, "segment_index": segment},
            "reason": reason,
        })
    xs=[p[0] for p in points]; ys=[p[1] for p in points]
    return {
        "status":"ok",
        "geometry_constraints_complete":False,
        "geometry_fallback_allowed":True,
        "dimensions_complete":True,
        "outer_dimensions_checked":True,
        "outer_dimension_axes":["x","y"],
        "variants":[],
        "contours":[{"kind":"polyline","role":"outer","points":[[*p,0] for p in points]}],
        "geometry_constraints":[
            {
                "kind":"linear","axis":"x",
                "from":{"type":"outer_extreme","axis":"x","high":False},
                "to":{"type":"outer_extreme","axis":"x","high":True},
                "value_mm":max(xs)-min(xs),"source_text":"outer-x",
            },
            {
                "kind":"linear","axis":"y",
                "from":{"type":"outer_extreme","axis":"y","high":False},
                "to":{"type":"outer_extreme","axis":"y","high":True},
                "value_mm":max(ys)-min(ys),"source_text":"outer-y",
            },
        ],
        "dimensions":dims,
        "annotations":[],
        "reason":"chat simple visual",
    }


class SimpleConstraintCompletionTests(unittest.TestCase):
    def test_two_explicit_chamfers_complete_geometry(self):
        result=_base(
            [(0,25),(25,0),(1588,0),(1613,25),(1613,152),(0,152)],
            [(0,"PDF标注2-C25，左下倒角"),(2,"PDF标注2-C25，右下倒角")],
        )
        promoted,proof=complete_provable_chamfer_box_constraints(result)
        self.assertTrue(proof["promoted"])
        self.assertTrue(promoted["geometry_constraints_complete"])
        self.assertFalse(promoted["geometry_fallback_allowed"])
        self.assertEqual(len(promoted["geometry_constraints"]),6)

    def test_four_explicit_chamfers_complete_geometry(self):
        result=_base(
            [(0,15),(15,0),(1598,0),(1613,15),(1613,110),(1598,125),(15,125),(0,110)],
            [(0,"PDF标注4-C15"),(2,"PDF标注4-C15"),(4,"PDF标注4-C15"),(6,"PDF标注4-C15")],
        )
        promoted,proof=complete_provable_chamfer_box_constraints(result)
        self.assertTrue(proof["promoted"])
        self.assertEqual(proof["added_constraint_count"],8)
        self.assertEqual(len(promoted["geometry_constraints"]),10)

    def test_single_explicit_chamfer_is_supported(self):
        result=_base(
            [(0,0),(1613,0),(1613,487.3),(1598,502.3),(0,502.3)],
            [(2,"PDF主视图标注C15，右上倒角")],
        )
        promoted,proof=complete_provable_chamfer_box_constraints(result)
        self.assertTrue(proof["promoted"])
        self.assertTrue(promoted["geometry_constraints_complete"])

    def test_internal_step_fails_closed(self):
        result=_base(
            [(0,0),(100,0),(100,50),(80,50),(80,80),(0,80)],
            [],
        )
        promoted,proof=complete_provable_chamfer_box_constraints(result)
        self.assertFalse(proof["promoted"])
        self.assertFalse(promoted["geometry_constraints_complete"])

    def test_missing_chamfer_annotation_fails_closed(self):
        result=_base(
            [(0,20),(20,0),(100,0),(100,80),(0,80)],
            [],
        )
        promoted,proof=complete_provable_chamfer_box_constraints(result)
        self.assertFalse(proof["promoted"])
        self.assertEqual(proof["reason"],"chamfer_dimension_coverage_mismatch")

    def test_mismatched_c_value_fails_closed(self):
        result=_base(
            [(0,20),(20,0),(100,0),(100,80),(0,80)],
            [(0,"PDF标注C25")],
        )
        promoted,proof=complete_provable_chamfer_box_constraints(result)
        self.assertFalse(proof["promoted"])
        self.assertEqual(proof["reason"],"chamfer_value_geometry_mismatch")


if __name__ == "__main__":
    unittest.main()
