"""Export reviewed 2D contour geometry to a checked DXF file.

The PDF interpretation step is intentionally human-reviewed. Never infer
fabrication dimensions from page scale or emit a cutting file from an
unresolved drawing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.dxf import read_and_inspect_r12, validate, write_r12


def convert(source: Path, destination: Path) -> dict:
    document = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("status") != "reviewed":
        raise ValueError("Input must explicitly have status='reviewed'")
    contours = document.get("contours")
    if not isinstance(contours, list):
        raise ValueError("Input must contain a contours list")
    expected = validate(contours)
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_r12(destination, contours)
    _, actual = read_and_inspect_r12(destination)
    for key in ("width", "height", "area_m2", "cut_length_mm"):
        if abs(expected[key] - actual[key]) > max(1e-6, abs(expected[key]) * 1e-8):
            destination.unlink(missing_ok=True)
            raise ValueError(f"DXF readback differs from reviewed geometry: {key}")
    return actual


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Reviewed contour JSON")
    parser.add_argument("output", type=Path, help="Output DXF")
    args = parser.parse_args()
    print(json.dumps(convert(args.input, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
