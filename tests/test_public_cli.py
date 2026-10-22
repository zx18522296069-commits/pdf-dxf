import json
import tempfile
import unittest
from pathlib import Path

from pdf_dxf import convert
from src.dxf import read_and_inspect_r12


class ExportTests(unittest.TestCase):
    def test_reviewed_plate_round_trip(self):
        source = Path(__file__).parents[1] / "examples/reviewed_plate.json"
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "plate.dxf"
            metrics = convert(source, output)
            contours, reread = read_and_inspect_r12(output)
            self.assertEqual(metrics, reread)
            self.assertEqual((metrics["width"], metrics["height"]), (200, 100))
            self.assertEqual(len(contours), 2)

    def test_unreviewed_geometry_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "input.json", Path(folder) / "part.dxf"
            source.write_text(json.dumps({"status": "draft", "contours": []}))
            with self.assertRaisesRegex(ValueError, "reviewed"):
                convert(source, output)
            self.assertFalse(output.exists())

    def test_hole_outside_outline_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "input.json", Path(folder) / "part.dxf"
            source.write_text(json.dumps({"status": "reviewed", "contours": [
                {"kind": "polyline", "role": "outer", "points": [[0, 0], [100, 0], [100, 100], [0, 100]]},
                {"kind": "circle", "role": "hole", "cx": 150, "cy": 50, "radius": 5},
            ]}))
            with self.assertRaisesRegex(ValueError, "超出"):
                convert(source, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
