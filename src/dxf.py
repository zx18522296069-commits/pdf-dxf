from __future__ import annotations

import math
from pathlib import Path


def _pair(code, value):
    return f"{code}\n{value}\n"


def write_r12(path: Path, contours: list[dict]) -> None:
    bounds = contour_bounds(contours)
    out = [_pair(0, "SECTION"), _pair(2, "HEADER"), _pair(9, "$ACADVER"), _pair(1, "AC1009"),
           _pair(9, "$INSUNITS"), _pair(70, 4), _pair(9, "$MEASUREMENT"), _pair(70, 1),
           _pair(9, "$EXTMIN"), _pair(10, bounds[0]), _pair(20, bounds[1]), _pair(30, 0),
           _pair(9, "$EXTMAX"), _pair(10, bounds[2]), _pair(20, bounds[3]), _pair(30, 0),
           _pair(9, "$LIMMIN"), _pair(10, bounds[0]), _pair(20, bounds[1]),
           _pair(9, "$LIMMAX"), _pair(10, bounds[2]), _pair(20, bounds[3]),
           _pair(0, "ENDSEC"), _pair(0, "SECTION"), _pair(2, "TABLES"), _pair(0, "ENDSEC"),
           _pair(0, "SECTION"), _pair(2, "ENTITIES")]
    for c in contours:
        kind = c["kind"]
        if kind == "circle":
            out += [_pair(0, "CIRCLE"), _pair(8, 0), _pair(10, c["cx"]), _pair(20, c["cy"]),
                    _pair(30, 0), _pair(40, c["radius"])]
        elif kind in ("polygon", "polyline"):
            pts = c["points"]
            out += [_pair(0, "POLYLINE"), _pair(8, 0), _pair(66, 1), _pair(70, 1)]
            for p in pts:
                out += [_pair(0, "VERTEX"), _pair(8, 0), _pair(10, p[0]), _pair(20, p[1]), _pair(30, 0)]
                if len(p) > 2 and p[2]:
                    out.append(_pair(42, p[2]))
            out += [_pair(0, "SEQEND"), _pair(8, 0)]
        else:
            raise ValueError(f"unsupported contour: {kind}")
    out += [_pair(0, "ENDSEC"), _pair(0, "EOF")]
    with path.open("w",encoding="ascii",newline="\n") as stream:
        stream.write("".join(out))


def _bulge_arc_geometry(p, q):
    bulge=float(p[2]) if len(p)>2 else 0.0
    if abs(bulge)<1e-12:
        raise ValueError("线段不是bulge圆弧")
    x1,y1=float(p[0]),float(p[1]); x2,y2=float(q[0]),float(q[1])
    chord=math.hypot(x2-x1,y2-y1)
    if chord<=1e-12:
        raise ValueError("圆弧弦长为0")
    theta=4*math.atan(bulge)
    radius=chord/(2*abs(math.sin(theta/2)))
    mx,my=(x1+x2)/2,(y1+y2)/2
    h=chord/(2*math.tan(theta/2))
    cx=mx-(y2-y1)/chord*h
    cy=my+(x2-x1)/chord*h
    start=math.atan2(y1-cy,x1-cx)
    return cx,cy,radius,start,theta


def _angle_on_arc(angle: float, start: float, theta: float, tolerance: float = 1e-12) -> bool:
    full=2*math.pi
    if theta>=0:
        return (angle-start)%full <= theta+tolerance
    return (start-angle)%full <= -theta+tolerance


def contour_bounds(contours: list[dict]):
    xs, ys = [], []
    for c in contours:
        if c["kind"] == "circle":
            r=float(c["radius"]); xs += [float(c["cx"])-r,float(c["cx"])+r]; ys += [float(c["cy"])-r,float(c["cy"])+r]
        else:
            xs += [float(p[0]) for p in c["points"]]; ys += [float(p[1]) for p in c["points"]]
            pts=c["points"]
            for p,q in zip(pts,pts[1:]+pts[:1]):
                bulge=float(p[2]) if len(p)>2 else 0.0
                if abs(bulge)<1e-12:
                    continue
                cx,cy,radius,start,theta=_bulge_arc_geometry(p,q)
                # Exact extrema: endpoints are already present; only cardinal
                # angles can extend a circular arc's bounding box.
                for angle in (0.0, math.pi/2, math.pi, 3*math.pi/2):
                    if _angle_on_arc(angle,start,theta):
                        xs.append(cx+radius*math.cos(angle))
                        ys.append(cy+radius*math.sin(angle))
    if not xs: raise ValueError("没有可计算范围的轮廓")
    return min(xs),min(ys),max(xs),max(ys)


def _poly_metrics(points):
    area=0.0; length=0.0
    for p,q in zip(points,points[1:]+points[:1]):
        x1,y1=float(p[0]),float(p[1]); x2,y2=float(q[0]),float(q[1])
        area+=(x1*y2-x2*y1)/2; chord=math.hypot(x2-x1,y2-y1); bulge=float(p[2]) if len(p)>2 else 0.0
        if abs(bulge)<1e-12: length+=chord; continue
        theta=4*math.atan(bulge); radius=chord/(2*abs(math.sin(theta/2)))
        area+=.5*radius*radius*(theta-math.sin(theta)); length+=radius*abs(theta)
    return area,length


def _read_r12_text(text: str, path_name: str) -> list[dict]:
    lines=text.splitlines()
    pairs=[(lines[i].strip(),lines[i+1].strip()) for i in range(0,len(lines)-1,2)]
    contours=[]; i=0
    while i < len(pairs):
        code,value=pairs[i]
        if code=="0" and value=="CIRCLE":
            data={}; i+=1
            while i<len(pairs) and pairs[i][0]!="0": data[pairs[i][0]]=pairs[i][1]; i+=1
            contours.append({"kind":"circle","role":"hole","cx":float(data["10"]),"cy":float(data["20"]),"radius":float(data["40"])})
            continue
        if code=="0" and value=="POLYLINE":
            points=[]; closed=False; i+=1
            while i<len(pairs):
                code_value,pair_value=pairs[i]
                if code_value=="70" and int(pair_value)&1: closed=True
                if code_value=="0" and pair_value=="VERTEX":
                    vertex={}; i+=1
                    while i<len(pairs) and pairs[i][0]!="0": vertex[pairs[i][0]]=pairs[i][1]; i+=1
                    points.append([float(vertex["10"]),float(vertex["20"]),float(vertex.get("42",0))]); continue
                if code_value=="0" and pair_value=="SEQEND": i+=1; break
                i+=1
            if not closed: raise ValueError(f"DXF存在未闭合POLYLINE：{path_name}")
            contours.append({"kind":"polyline","role":"hole","points":points}); continue
        i+=1
    if not contours: raise ValueError(f"DXF没有切割实体：{path_name}")
    def footprint(contour):
        if contour["kind"]=="circle":
            return math.pi*contour["radius"]**2
        return abs(_poly_metrics(contour["points"])[0])
    contours[max(range(len(contours)),key=lambda n:footprint(contours[n]))]["role"]="outer"
    return contours


def read_r12(path: Path) -> list[dict]:
    """Read the restricted R12 entity subset emitted by write_r12."""
    return _read_r12_text(path.read_text(encoding="ascii"), path.name)


def read_and_inspect_r12(path: Path) -> tuple[list[dict], dict]:
    """Read DXF bytes once and return both canonical contours and QA metrics."""
    text=path.read_text(encoding="ascii")
    normalized=text.replace("\r","")
    if "AC1009" not in text or "$MEASUREMENT\n70\n1" not in normalized:
        raise ValueError(f"DXF HEADER不完整：{path.name}")
    if "1e+20" in text.lower():
        raise ValueError(f"DXF HEADER仍含无效范围：{path.name}")
    contours=_read_r12_text(text,path.name)
    result=validate(contours)
    result["entities"]=len(contours)
    return contours,result


def inspect_r12(path: Path) -> dict:
    _,result=read_and_inspect_r12(path)
    return result

def metrics(contours: list[dict]):
    area, length = 0.0, 0.0
    for c in contours:
        if c["kind"] == "circle":
            r = float(c["radius"])
            signed = math.pi*r*r * (1 if c.get("role") == "outer" else -1)
            area += signed; length += 2*math.pi*r
        else:
            pts = c["points"]
            signed,segment_length=_poly_metrics(pts)
            area += abs(signed) * (1 if c.get("role") == "outer" else -1)
            length += segment_length
    if area <= 0: raise ValueError("净面积或轮廓无效")
    xmin,ymin,xmax,ymax=contour_bounds(contours)
    return {"width":xmax-xmin,"height":ymax-ymin,"area_m2":area/1e6,"cut_length_mm":length}


def _sample_polyline_boundary(points: list, arc_steps: int = 32, line_steps: int = 4):
    sampled = []
    for p, q in zip(points, points[1:] + points[:1]):
        x1, y1 = float(p[0]), float(p[1])
        x2, y2 = float(q[0]), float(q[1])
        bulge = float(p[2]) if len(p) > 2 else 0.0
        if abs(bulge) < 1e-12:
            for step in range(line_steps):
                t = step / line_steps
                sampled.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
            continue
        try:
            cx, cy, radius, start, theta = _bulge_arc_geometry(p, q)
        except ValueError:
            continue
        for step in range(arc_steps):
            angle = start + theta * step / arc_steps
            sampled.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return sampled


def _sample_contour_boundary(contour: dict):
    if contour["kind"] == "circle":
        cx, cy, radius = float(contour["cx"]), float(contour["cy"]), float(contour["radius"])
        return [
            (
                cx + radius * math.cos(2 * math.pi * step / 48),
                cy + radius * math.sin(2 * math.pi * step / 48),
            )
            for step in range(48)
        ]
    return _sample_polyline_boundary(contour["points"])


def _point_on_segment(point, first, second, tolerance=1e-7):
    px, py = point
    ax, ay = first
    bx, by = second
    cross = abs((px - ax) * (by - ay) - (py - ay) * (bx - ax))
    scale = max(1.0, math.hypot(bx - ax, by - ay))
    if cross > tolerance * scale:
        return False
    return (
        min(ax, bx) - tolerance <= px <= max(ax, bx) + tolerance
        and min(ay, by) - tolerance <= py <= max(ay, by) + tolerance
    )


def _point_in_polygon(point, polygon):
    if len(polygon) < 3:
        return False
    x, y = point
    inside = False
    for first, second in zip(polygon, polygon[1:] + polygon[:1]):
        if _point_on_segment(point, first, second):
            return True
        x1, y1 = first
        x2, y2 = second
        crosses = (y1 > y) != (y2 > y)
        if not crosses:
            continue
        x_cross = (x2 - x1) * (y - y1) / (y2 - y1) + x1
        if x < x_cross:
            inside = not inside
    return inside


def _contour_inside_outer(hole: dict, outer: dict) -> bool:
    samples = _sample_contour_boundary(hole)
    if not samples:
        return False
    if outer["kind"] == "circle":
        cx, cy, radius = float(outer["cx"]), float(outer["cy"]), float(outer["radius"])
        tolerance = 1e-6
        return all(math.hypot(x - cx, y - cy) <= radius + tolerance for x, y in samples)
    polygon = _sample_polyline_boundary(outer["points"])
    return bool(polygon) and all(_point_in_polygon(point, polygon) for point in samples)


def validate(contours: list[dict]) -> dict:
    if not contours:
        raise ValueError("没有可切割轮廓")
    invalid_roles = [c.get("role") for c in contours if c.get("role") not in {"outer", "hole"}]
    if invalid_roles:
        raise ValueError("切割轮廓role必须为outer或hole")
    outers = [c for c in contours if c.get("role") == "outer"]
    if len(outers) != 1:
        raise ValueError(f"每个DXF必须且只能有1个外轮廓，实际={len(outers)}")

    outer = outers[0]
    outer_bounds = contour_bounds(outers)
    for hole in (c for c in contours if c.get("role") == "hole"):
        hole_bounds = contour_bounds([hole])
        tolerance = 1e-6
        if (
            hole_bounds[0] < outer_bounds[0] - tolerance
            or hole_bounds[1] < outer_bounds[1] - tolerance
            or hole_bounds[2] > outer_bounds[2] + tolerance
            or hole_bounds[3] > outer_bounds[3] + tolerance
        ):
            raise ValueError("内轮廓/孔超出外轮廓包络，拒绝生成DXF")
        if not _contour_inside_outer(hole, outer):
            raise ValueError("内轮廓/孔不在真实外轮廓内部，拒绝生成DXF")

    area, length = 0.0, 0.0
    for c in contours:
        if c["kind"] == "circle":
            r = float(c["radius"])
            if r <= 0:
                raise ValueError("圆半径无效")
            sign = -1 if c.get("role") == "hole" else 1
            area += sign * math.pi * r * r; length += 2 * math.pi * r
        else:
            pts = c["points"]
            if len(pts) < 3:
                raise ValueError("闭合轮廓至少需要3点")
            signed,segment_length=_poly_metrics(pts); a=abs(signed)
            sign = -1 if c.get("role") == "hole" else 1
            area += sign * a
            length += segment_length
    if area <= 0:
        raise ValueError("净面积无效")
    xmin,ymin,xmax,ymax=contour_bounds(contours)
    return {"width": xmax-xmin, "height": ymax-ymin, "area_m2": area/1e6, "cut_length_mm": length}
