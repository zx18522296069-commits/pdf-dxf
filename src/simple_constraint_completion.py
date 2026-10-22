from __future__ import annotations

import copy
import math
import re
from typing import Any


_TOL = 1e-6


def _xy(point: Any) -> tuple[float, float] | None:
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    try:
        return float(point[0]), float(point[1])
    except (TypeError, ValueError):
        return None


def _outer_constraint(result: dict[str, Any], axis: str) -> dict[str, Any] | None:
    found = []
    for item in result.get("geometry_constraints") or []:
        if not isinstance(item, dict):
            continue
        if item.get("kind") != "linear" or item.get("axis") != axis:
            continue
        a, b = item.get("from"), item.get("to")
        if not isinstance(a, dict) or not isinstance(b, dict):
            continue
        if (
            a.get("type") == "outer_extreme"
            and b.get("type") == "outer_extreme"
            and a.get("axis") == axis
            and b.get("axis") == axis
            and bool(a.get("high")) is False
            and bool(b.get("high")) is True
        ):
            found.append(item)
    return found[0] if len(found) == 1 else None


def _chamfer_value(reason: str) -> tuple[int | None, float] | None:
    text = str(reason or "").replace("×", "x")
    matches = list(re.finditer(r"(?:(\d+)\s*[-x*]\s*)?C\s*(\d+(?:\.\d+)?)", text, flags=re.I))
    if len(matches) != 1:
        return None
    count = int(matches[0].group(1)) if matches[0].group(1) else None
    value = float(matches[0].group(2))
    return (count, value) if value > 0 else None


def _endpoint_ref(contour_index: int, vertex_index: int, point: tuple[float, float]) -> dict[str, Any]:
    return {
        "type": "endpoint",
        "contour_index": contour_index,
        "vertex_index": vertex_index,
        "point": [point[0], point[1]],
    }


def complete_provable_chamfer_box_constraints(result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Complete a strictly provable 'box with explicit C-corners' analysis.

    This never derives fabrication dimensions from page scale.  It only promotes
    a Chat analysis when the current contour itself is exactly a rectangular
    envelope with some 45-degree cut corners, the PDF-driven dimensions identify
    every such diagonal as an explicit C chamfer, and the existing hard outer
    constraints equal the final contour envelope.

    Any notch, internal step, curve, missing/mismatched C annotation, variant,
    incomplete outer dimension plan, or ambiguous segment reference fails closed.
    """
    proof: dict[str, Any] = {"promoted": False, "reason": ""}
    if not isinstance(result, dict) or result.get("status") != "ok":
        proof["reason"] = "status_not_ok"
        return result, proof
    if result.get("geometry_constraints_complete") is True and result.get("geometry_fallback_allowed") is not True:
        proof["reason"] = "already_complete"
        return result, proof
    if result.get("variants"):
        proof["reason"] = "variants_present"
        return result, proof
    if result.get("dimensions_complete") is not True or result.get("outer_dimensions_checked") is not True:
        proof["reason"] = "dimension_plan_incomplete"
        return result, proof
    axes = set(result.get("outer_dimension_axes") or [])
    if not {"x", "y"}.issubset(axes):
        proof["reason"] = "outer_axes_missing"
        return result, proof

    contours = result.get("contours") or []
    if len(contours) != 1 or not isinstance(contours[0], dict):
        proof["reason"] = "not_single_outer_contour"
        return result, proof
    contour = contours[0]
    if contour.get("role") != "outer" or contour.get("kind") not in {"polyline", "polygon"}:
        proof["reason"] = "unsupported_outer_kind"
        return result, proof
    raw_points = contour.get("points") or []
    points = [_xy(p) for p in raw_points]
    if len(points) < 4 or any(p is None for p in points):
        proof["reason"] = "invalid_points"
        return result, proof
    pts = [p for p in points if p is not None]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    width, height = xmax - xmin, ymax - ymin
    if width <= _TOL or height <= _TOL:
        proof["reason"] = "degenerate_bbox"
        return result, proof

    x_constraint = _outer_constraint(result, "x")
    y_constraint = _outer_constraint(result, "y")
    if x_constraint is None or y_constraint is None:
        proof["reason"] = "outer_constraints_not_unique"
        return result, proof
    try:
        x_value = float(x_constraint.get("value_mm"))
        y_value = float(y_constraint.get("value_mm"))
    except (TypeError, ValueError):
        proof["reason"] = "outer_constraint_value_invalid"
        return result, proof
    if abs(x_value - width) > _TOL or abs(y_value - height) > _TOL:
        proof["reason"] = "outer_constraint_bbox_mismatch"
        return result, proof

    diagonal_segments: list[int] = []
    for index, p in enumerate(pts):
        q = pts[(index + 1) % len(pts)]
        dx, dy = q[0] - p[0], q[1] - p[1]
        if abs(dx) <= _TOL and abs(dy) <= _TOL:
            proof["reason"] = "zero_length_segment"
            return result, proof
        if abs(dx) > _TOL and abs(dy) > _TOL:
            if abs(abs(dx) - abs(dy)) > _TOL:
                proof["reason"] = "non_45_degree_diagonal"
                return result, proof
            diagonal_segments.append(index)
            continue

        # Every non-chamfer straight edge must remain on one of the four outer
        # envelope sides.  This excludes notches/steps from promotion.
        if abs(dx) <= _TOL:
            if not (abs(p[0] - xmin) <= _TOL or abs(p[0] - xmax) <= _TOL):
                proof["reason"] = "internal_vertical_step"
                return result, proof
        elif abs(dy) <= _TOL:
            if not (abs(p[1] - ymin) <= _TOL or abs(p[1] - ymax) <= _TOL):
                proof["reason"] = "internal_horizontal_step"
                return result, proof

    if not diagonal_segments:
        proof["reason"] = "no_chamfer_segments"
        return result, proof

    chamfer_dims: dict[int, tuple[int | None, float, str]] = {}
    for dim in result.get("dimensions") or []:
        if not isinstance(dim, dict) or dim.get("kind") != "chamfer":
            continue
        ref = dim.get("from")
        if not isinstance(ref, dict) or ref.get("type") != "segment":
            proof["reason"] = "chamfer_dimension_not_segment_bound"
            return result, proof
        if int(ref.get("contour_index") or 0) != 0:
            proof["reason"] = "chamfer_dimension_wrong_contour"
            return result, proof
        try:
            segment_index = int(ref.get("segment_index"))
        except (TypeError, ValueError):
            proof["reason"] = "chamfer_segment_index_invalid"
            return result, proof
        parsed = _chamfer_value(str(dim.get("reason") or ""))
        if parsed is None or segment_index in chamfer_dims:
            proof["reason"] = "chamfer_text_ambiguous"
            return result, proof
        chamfer_dims[segment_index] = (parsed[0], parsed[1], str(dim.get("reason") or ""))

    if set(chamfer_dims) != set(diagonal_segments):
        proof["reason"] = "chamfer_dimension_coverage_mismatch"
        return result, proof

    explicit_counts = {count for count, _, _ in chamfer_dims.values() if count is not None}
    if len(explicit_counts) > 1:
        proof["reason"] = "chamfer_count_conflict"
        return result, proof
    if explicit_counts and next(iter(explicit_counts)) != len(diagonal_segments):
        proof["reason"] = "chamfer_count_mismatch"
        return result, proof

    added: list[dict[str, Any]] = []
    for segment_index in diagonal_segments:
        p = pts[segment_index]
        q = pts[(segment_index + 1) % len(pts)]
        _, c_value, reason = chamfer_dims[segment_index]
        if abs(abs(q[0] - p[0]) - c_value) > _TOL or abs(abs(q[1] - p[1]) - c_value) > _TOL:
            proof["reason"] = "chamfer_value_geometry_mismatch"
            return result, proof
        source_text = re.search(r"(?:\d+\s*[-x*]\s*)?C\s*\d+(?:\.\d+)?", reason, flags=re.I)
        source = source_text.group(0) if source_text else f"C{c_value:g}"
        next_index = (segment_index + 1) % len(pts)
        added.extend([
            {
                "kind": "linear",
                "axis": "x",
                "from": _endpoint_ref(0, segment_index, p),
                "to": _endpoint_ref(0, next_index, q),
                "value_mm": c_value,
                "source_text": source,
            },
            {
                "kind": "linear",
                "axis": "y",
                "from": _endpoint_ref(0, segment_index, p),
                "to": _endpoint_ref(0, next_index, q),
                "value_mm": c_value,
                "source_text": source,
            },
        ])

    promoted = copy.deepcopy(result)
    promoted.setdefault("geometry_constraints", []).extend(added)
    promoted["geometry_constraints_complete"] = True
    promoted["geometry_fallback_allowed"] = False
    promoted.setdefault("annotations", []).append({
        "text": "simple_chamfer_constraints_completed",
        "reason": (
            f"程序数学完备证明：外包{width:g}×{height:g}与硬约束一致，"
            f"{len(diagonal_segments)}条45°斜边均由PDF C倒角尺寸逐段绑定；无内部台阶/槽缺口。"
        ),
    })
    promoted["reason"] = (
        str(promoted.get("reason") or "")
        + "｜simple倒角约束已由程序数学完备证明，取消未约束自由度fallback"
    ).strip("｜")
    proof.update({
        "promoted": True,
        "reason": "provable_rectangular_envelope_with_explicit_chamfers",
        "diagonal_segments": diagonal_segments,
        "added_constraint_count": len(added),
        "bbox": [xmin, ymin, xmax, ymax],
    })
    return promoted, proof
