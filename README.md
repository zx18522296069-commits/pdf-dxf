# pdf-dxf

A small open-source toolkit extracted from a production PDF-to-DXF drawing workflow. It writes millimetre-based AutoCAD R12 DXF from **reviewed** 2D contours, reads the DXF back, and checks geometry, holes, area, cut length, and envelope dimensions.

The source PDF must be interpreted and its dimensions reviewed before using this toolkit. This repository does **not** automatically understand arbitrary PDFs, OCR drawings, infer dimensions from page scale, or certify a cutting file for production. Inspect the result in your CAD/CAM workflow before cutting.

## Quick start

Python 3.11+; the example has no third-party dependencies.

```sh
python pdf_dxf.py examples/reviewed_plate.json plate.dxf
python -m unittest discover -s tests -v
```

The example is fictional: a 200 × 100 mm rectangular plate with a 20 mm hole. The input JSON uses `status: reviewed` and a `contours` array. A part must have exactly one `outer` contour; closed inner profiles use `hole`. `polyline` points are `[x, y, bulge]` and circles use `cx`, `cy`, `radius`. All dimensions are in millimetres.

The program validates the contours before writing, then reads the DXF back and compares width, height, area, and cut length. It prints the measured results as JSON. An invalid or unreviewed input exits with an error.

## Scope

- `src/dxf.py`: R12 DXF writing, readback, geometry checks and measurements.
- `src/simple_constraint_completion.py`: conservative completion of explicitly dimensioned rectangular chamfers.
- `src/preview_label_layout.py`: dimension label placement helper for acceptance previews.
- `pdf_dxf.py`: a small command-line example using the geometry core.

This public version starts with a clean history. It excludes customer drawings, order data, internal workflow configuration, Drive integration, production rules and business-specific tests. The original production repository is separate and private.

## Contributing

Issues and focused pull requests are welcome. Please use synthetic drawings or data you have permission to share; include a regression test for geometry changes. Never post customer drawings, tokens, or personal information.

## License

MIT. See [LICENSE](LICENSE).
