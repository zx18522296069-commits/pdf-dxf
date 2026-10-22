"""User-accepted order 213 preview layout: inner short, outer long, totals outermost."""
import unittest

from src.preview_label_layout import plan_preview_dimension_labels


def _part():
    return {
        "outer_dimension_axes": ["x", "y"],
        "contours": [{
            "role": "outer", "kind": "polyline",
            "points": [[0, 0, 0], [1000, 0, 0], [1000, 500, 0], [0, 500, 0]],
        }],
    }


def _linear(axis, start, end, text, side, from_type="endpoint", to_type="endpoint"):
    return {
        "kind": "linear", "axis": axis,
        "from": start, "to": end, "text": text, "side": side,
        "from_type": from_type, "to_type": to_type,
    }


def _layout(part, dimensions):
    return plan_preview_dimension_labels(
        part, dimensions, lambda x, y: (x, 500 - y),
        sx=0, sy=0, drawn_w=1000, drawn_h=500,
        text_width=lambda text: 12 * len(text),
    )


class PreviewLabelLayoutTests(unittest.TestCase):
    def test_short_inside_long_outside_total_outermost(self):
        dims = [
            _linear("x", (0, 0), (1000, 0), "1000", "bottom",
                    "outer_extreme", "outer_extreme"),
            _linear("x", (100, 0), (400, 0), "300", "bottom"),
            _linear("x", (100, 0), (800, 0), "700", "bottom"),
            _linear("x", (410, 0), (490, 0), "80", "bottom"),
        ]
        result = _layout(_part(), dims)
        self.assertTrue(result[0]["overall"])
        self.assertLess(result[1]["tier"], result[2]["tier"])
        self.assertLess(result[2]["tier"], result[0]["tier"])
        self.assertEqual(result[1]["tier"], result[3]["tier"])
        self.assertEqual([d["text"] for d in dims], ["1000", "300", "700", "80"])

    def test_vertical_sizes_follow_same_rule(self):
        dims = [
            _linear("y", (0, 0), (0, 500), "500", "left",
                    "outer_extreme", "outer_extreme"),
            _linear("y", (0, 200), (0, 300), "100", "left"),
            _linear("y", (0, 50), (0, 400), "350", "left"),
        ]
        result = _layout(_part(), dims)
        self.assertGreater(result[0]["tier"], result[2]["tier"])
        self.assertGreater(result[2]["tier"], result[1]["tier"])
        self.assertLess(result[0]["dimension_line"], result[2]["dimension_line"])

    def test_local_dimension_only_moves_if_it_collides(self):
        dims = [
            {"kind": "radius", "axis": "radius", "anchor": (300, 250),
             "text": "R100", "side": "local", "level": 0},
            {"kind": "radius", "axis": "radius", "anchor": (300, 250),
             "text": "R200", "side": "local", "level": 0},
        ]
        result = _layout(_part(), dims)
        self.assertEqual(result[0]["leader_end"], (334, 216))
        self.assertNotEqual(result[0]["leader_end"], result[1]["leader_end"])

    def test_hole_to_hole_width_not_mistaken_for_outer_extent(self):
        dims = [_linear("x", (0, 100), (1000, 100), "1000", "bottom",
                        "circle_center", "circle_center")]
        result = _layout(_part(), dims)
        self.assertFalse(result[0]["overall"])

    def test_no_dimensions_preserves_empty_plan(self):
        self.assertEqual(_layout(_part(), []), [])


if __name__ == "__main__":
    unittest.main()
