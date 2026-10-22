"""Dimension-label placement for the five-column acceptance preview.

Layout only: do not alter measured DXF coordinates, PDF-selected dimensions,
the immutable review evidence, or cutting geometry.
"""
from __future__ import annotations

from collections import defaultdict


def _overlaps(a, b, pad=3.0):
    return a[0] < b[2] + pad and a[2] + pad > b[0] and a[1] < b[3] + pad and a[3] + pad > b[1]


def _outer_size(part, dim):
    """Recognize PDF-requested overall dimensions by actual DXF envelope."""
    if dim.get("kind") != "linear" or dim.get("axis") not in ("x", "y"):
        return False
    axis = dim["axis"]
    if axis not in (part.get("outer_dimension_axes") or []):
        return False
    points = []
    for contour in part.get("contours") or []:
        if contour.get("role") != "outer":
            continue
        if contour.get("kind") == "circle":
            c = float(contour["cx"] if axis == "x" else contour["cy"])
            r = float(contour["radius"])
            points.extend((c - r, c + r))
        else:
            points.extend(float(p[0 if axis == "x" else 1]) for p in contour.get("points") or [])
    if not points:
        return False
    extent = max(points) - min(points)
    coordinate = 0 if axis == "x" else 1
    a, b = float(dim["from"][coordinate]), float(dim["to"][coordinate])
    if abs(abs(b - a) - extent) > max(0.01, extent * 1e-6):
        return False
    # A hole/slot-to-hole span must not be mistaken for an outer dimension.
    return (str(dim.get("from_type") or "") not in {"circle_center", "arc_center", "profile_center"}
            and str(dim.get("to_type") or "") not in {"circle_center", "arc_center", "profile_center"})


def _text_rect(axis, position, p0, p1, width):
    if axis == "x":
        middle = (p0[0] + p1[0]) / 2.0
        return (middle - width / 2.0 - 4, position - 17,
                middle + width / 2.0 + 4, position + 17)
    middle = (p0[1] + p1[1]) / 2.0
    return (position + 4, middle - 17, position + width + 14, middle + 17)


def plan_preview_dimension_labels(part, dimensions, transform, sx, sy, drawn_w, drawn_h, text_width):
    """Return coordinates for original-style dimension lines and local callouts.

    In each side/axis group, short dimensions occupy near-outline tiers,
    longer dimension chains go progressively outward, and true outer envelope
    dimensions are always beyond *every* interior dimension on that side.
    Disjoint spans can share a tier; overlapping spans cannot.  Text collision
    checks cover distinct sides and non-linear callouts as well.
    """
    positions = [{} for _ in dimensions]
    reserved = []
    groups = defaultdict(list)
    for index, dim in enumerate(dimensions):
        if dim.get("kind") != "linear" or dim.get("axis") not in {"x", "y"}:
            continue
        axis = dim["axis"]
        side = ("bottom" if dim.get("side") == "bottom" else "top") if axis == "x" else (
            "right" if dim.get("side") == "right" else "left")
        p0, p1 = transform(*dim["from"]), transform(*dim["to"])
        coordinate = 0 if axis == "x" else 1
        span = sorted((p0[coordinate], p1[coordinate]))
        groups[(axis, side)].append({
            "index": index, "p0": p0, "p1": p1, "span": span,
            "length": abs(float(dim["to"][coordinate]) - float(dim["from"][coordinate])),
            "overall": _outer_size(part, dim),
            "width": text_width(dim["text"]),
        })

    for (axis, side), entries in groups.items():
        lanes = defaultdict(list)
        normal = sorted((e for e in entries if not e["overall"]), key=lambda e: (e["length"], e["index"]))
        overall = sorted((e for e in entries if e["overall"]), key=lambda e: (e["length"], e["index"]))
        for entry in normal + overall:
            # Overall size is not allowed between local dimensions.
            min_lane = (max(lanes.keys()) + 1) if (entry["overall"] and lanes) else 0
            for lane in range(min_lane, max(min_lane + 50, 50)):
                if axis == "x":
                    position = (sy + drawn_h + 30 + lane * 34) if side == "bottom" else (sy - 30 - lane * 34)
                else:
                    position = (sx + drawn_w + 42 + lane * 36) if side == "right" else (sx - 42 - lane * 36)
                rect = _text_rect(axis, position, entry["p0"], entry["p1"], entry["width"])
                # Coincident / crossing dimension lines on the same tier are
                # unreadable even when the numerals themselves do not intersect.
                shares_line = any(
                    min(entry["span"][1], peer["span"][1]) -
                    max(entry["span"][0], peer["span"][0]) > 3.0
                    for peer in lanes[lane]
                )
                hits_text = any(_overlaps(rect, previous) for previous in reserved)
                if shares_line or hits_text:
                    continue
                positions[entry["index"]]["dimension_line"] = position
                positions[entry["index"]]["tier"] = lane
                positions[entry["index"]]["overall"] = entry["overall"]
                reserved.append(rect)
                lanes[lane].append(entry)
                break
            else:
                raise ValueError("总预览图尺寸排布空间不足，不能在数字重叠时交付")

    # Retain old leader/text styling for angles, radii, diameters and chamfers.
    # Only relocate a label if it would collide with a dimension label or
    # another local callout; the leader remains attached to the real DXF anchor.
    for index, dim in enumerate(dimensions):
        if dim.get("kind") == "linear":
            continue
        anchor = transform(*dim["anchor"])
        side = dim.get("side") or "local"
        sign_x = -1 if side == "left" else 1
        sign_y = 1 if side == "bottom" else -1
        level = int(dim.get("level") or 0)
        start_x = anchor[0] + sign_x * (34 + level * 16)
        start_y = anchor[1] + sign_y * (34 + level * 16)
        width = text_width(dim["text"])
        candidates = [(0, 0)]
        for distance in (22, 44, 66, 88, 110, 132):
            candidates.extend((
                (0, -distance), (0, distance),
                (sign_x * distance, 0),
                (sign_x * distance, -distance), (sign_x * distance, distance),
            ))
        for dx, dy in candidates:
            tx, ty = start_x + dx, start_y + dy
            text_x = tx + 5 if sign_x > 0 else tx - width - 5
            rect = (text_x - 3, ty - 20, text_x + width + 3, ty + 5)
            if any(_overlaps(rect, previous) for previous in reserved):
                continue
            positions[index]["leader_end"] = (tx, ty)
            positions[index]["text_x"] = text_x
            reserved.append(rect)
            break
        else:
            raise ValueError("总预览图局部尺寸文字无法错开，请检查该图尺寸密度")

    return positions
