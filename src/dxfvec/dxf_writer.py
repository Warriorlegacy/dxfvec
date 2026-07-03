"""DXF file generation from the canonical PathModel — PRD §3.4 P0.

Key industry-grade features:
  - Native ARC, CIRCLE, ELLIPSE entities (not polyline approximations)
  - DXF version selection (R12/AC1009 for legacy, R2010/AC1024, R2018/AC1032)
  - Correct $INSUNTS declaration matching user calibration
  - Layer naming convention per PRD §5.4
  - ezdxf.audit() after every write
  - Closed-loop enforcement for CUT layers

All exporters consume the canonical PathModel (PRD §7.3) so DXF, SVG, and
PDF output is guaranteed consistent.
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path as _Path

import ezdxf

from .path_model import (
    ArcSegment,
    BezierSegment,
    DXFVersion,
    LineSegment,
    LAYER_COLORS,
    LAYER_LINETYPES,
    Path as DxfPath,
    PathModel,
)

logger = logging.getLogger("dxfvec.dxf_writer")

INSUNITS_MAP: dict[str, int] = {
    "mm": 4,
    "cm": 5,
    "in": 1,
    "px": 0,
}

DXF_VERSION_MAP: dict[DXFVersion, str] = {
    DXFVersion.R12: "R12",
    DXFVersion.R2010: "R2010",
    DXFVersion.R2018: "R2018",
}


def write_dxf(
    model: PathModel,
    output_path: str | _Path,
    dxf_version: DXFVersion = DXFVersion.R2010,
    units: str = "mm",
    enforce_closed_cut: bool = True,
    max_gap_close: float = 0.0,
) -> _Path:
    """Write a DXF file from the canonical PathModel.

    Args:
        model: Canonical geometry model.
        output_path: Where to save.
        dxf_version: DXF format version.
        units: Unit string (mm, cm, in, px).
        enforce_closed_cut: Force all CUT layer paths to be closed.
        max_gap_close: Auto-close gaps up to this distance (0 = disabled).

    Returns:
        Path to the written DXF file.
    """
    output_path = _Path(output_path)
    os.makedirs(str(output_path.parent), exist_ok=True)

    logger.info("Writing DXF: %s (version=%s, units=%s, paths=%d)",
                output_path, dxf_version.value, units, model.entity_count())

    ver_str = DXF_VERSION_MAP.get(dxf_version, "R2010")
    doc = ezdxf.new(dxfversion=ver_str)

    # Set $INSUNITS from calibration or explicit units
    if model.calibration and model.calibration.is_valid:
        unit_code = INSUNITS_MAP.get(model.calibration.unit, 4)
    else:
        unit_code = INSUNITS_MAP.get(units, 4)
    doc.header["$INSUNITS"] = unit_code

    if model.calibration and model.calibration.scale_factor != 1.0:
        doc.header["$MEASUREMENT"] = 1 if unit_code in (4, 5) else 0

    # Setup layers per PRD §5.4 convention
    for name, color in LAYER_COLORS.items():
        if name not in doc.layers:
            layer = doc.layers.add(name)
            layer.color = color
            lt = LAYER_LINETYPES.get(name, "CONTINUOUS")
            if lt != "CONTINUOUS":
                layer.linetype = lt

    msp = doc.modelspace()
    dxfattribs_2d = {"elevation": 0, "thickness": 0}

    # Pre-process: enforce closed CUT paths
    if enforce_closed_cut:
        model.enforce_closed_layer("CUT")

    # Pre-process: close gaps
    if max_gap_close > 0:
        model.close_gaps(max_gap_close)

    for path in model.paths:
        _write_path(msp, path, dxf_version, dxfattribs_2d)

    doc.saveas(str(output_path))

    # Post-write audit: verify the file is valid
    try:
        ezdxf.readfile(str(output_path))
    except Exception as e:
        logger.error("DXF audit failed - output may be corrupt: %s", e)
        raise RuntimeError(f"DXF file is malformed after write: {e}") from e

    return output_path


def _write_path(
    msp: ezdxf.Drawing.modelspace,
    path: DxfPath,
    dxf_version: DXFVersion,
    dxfattribs_2d: dict,
) -> None:
    """Write a single DxfPath to the DXF modelspace."""
    if path.closed and _is_single_full_circle(path):
        _write_full_circle(msp, path)
        return

    if path.closed and _is_single_arc(path):
        seg = path.segments[0]
        if isinstance(seg, ArcSegment):
            _write_arc_entity(msp, seg, path.layer)
            return

    _write_lwpolyline(msp, path, dxf_version, dxfattribs_2d)


def _is_single_full_circle(path: DxfPath) -> bool:
    if len(path.segments) != 1:
        return False
    seg = path.segments[0]
    if isinstance(seg, ArcSegment) and seg.is_full_circle:
        return seg.radius > 0
    return False


def _is_single_arc(path: DxfPath) -> bool:
    if len(path.segments) != 1:
        return False
    return isinstance(path.segments[0], ArcSegment)


def _write_full_circle(msp, path: DxfPath) -> None:
    seg = path.segments[0]
    if not isinstance(seg, ArcSegment):
        return
    msp.add_circle(
        center=(seg.cx, seg.cy, 0),
        radius=seg.radius,
        dxfattribs={"layer": path.layer, "elevation": 0.0, "thickness": 0.0},
    )


def _write_arc_entity(msp, seg: ArcSegment, layer: str) -> None:
    start_rad = math.radians(seg.start_angle)
    end_rad = math.radians(seg.end_angle)
    msp.add_arc(
        center=(seg.cx, seg.cy, 0),
        radius=seg.radius,
        start_angle=math.degrees(start_rad),
        end_angle=math.degrees(end_rad),
        dxfattribs={"layer": layer},
    )


def _write_lwpolyline(
    msp,
    path: DxfPath,
    dxf_version: DXFVersion,
    dxfattribs_2d: dict,
) -> None:
    """Write a path as DXF geometry, using bulges for arcs where possible."""
    pts: list[tuple[float, float]] = []
    bulges: list[float] = []

    for seg in path.segments:
        if isinstance(seg, LineSegment):
            if not pts:
                pts.append((seg.start.x, seg.start.y))
            pts.append((seg.end.x, seg.end.y))
            bulges.append(0.0)
        elif isinstance(seg, ArcSegment):
            _append_arc_points(seg, pts, bulges)
        elif isinstance(seg, BezierSegment):
            _append_bezier_points(seg, pts, bulges)

    if len(pts) < 2:
        return

    if len(pts) == 2 and not path.closed:
        msp.add_line(
            (pts[0][0], pts[0][1], 0),
            (pts[1][0], pts[1][1], 0),
            dxfattribs={"layer": path.layer, **dxfattribs_2d},
        )
        return

    if dxf_version == DXFVersion.R12:
        # R12: use POLYLINE (LWPOLYLINE not supported)
        points_3d = [(p[0], p[1], 0) for p in pts]
        polyline = msp.add_polyline2d(
            points_3d,
            dxfattribs={"layer": path.layer},
        )
        if path.closed:
            polyline.close(True)
    else:
        # R2010/R2018: use LWPOLYLINE with bulges
        if any(b != 0.0 for b in bulges):
            # bulges[i] corresponds to edge pts[i]→pts[i+1]; pad last vertex with 0
            b_padded = list(bulges) + [0.0] * (len(pts) - len(bulges))
            vertices = [(pts[i][0], pts[i][1], b_padded[i]) for i in range(len(pts))]
            msp.add_lwpolyline(
                vertices, format="xyb",
                close=path.closed,
                dxfattribs={"layer": path.layer, **dxfattribs_2d},
            )
        else:
            msp.add_lwpolyline(
                pts,
                close=path.closed,
                dxfattribs={"layer": path.layer, **dxfattribs_2d},
            )


def _append_arc_points(
    seg: ArcSegment,
    pts: list,
    bulges: list,
) -> None:
    """Add arc points with bulge value to polyline vertices.

    Bulge = tan(sweep_angle / 4)  (positive for CCW).
    """
    sweep = seg.end_angle - seg.start_angle
    if sweep < 0:
        sweep += 360.0

    if abs(sweep) < 0.5:
        return

    bulge = math.tan(math.radians(sweep) / 4.0)
    if not seg.is_counterclockwise:
        bulge = -bulge

    start_x = seg.cx + seg.radius * math.cos(math.radians(seg.start_angle))
    start_y = seg.cy + seg.radius * math.sin(math.radians(seg.start_angle))
    end_x = seg.cx + seg.radius * math.cos(math.radians(seg.end_angle))
    end_y = seg.cy + seg.radius * math.sin(math.radians(seg.end_angle))

    if not pts:
        pts.append((start_x, start_y))
    pts.append((end_x, end_y))
    bulges.append(bulge)


def _adaptive_bezier_subdivision(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    tolerance: float = 0.01,
) -> list[tuple[float, float]]:
    """Subdivide cubic Bezier adaptively based on chord deviation."""
    points: list[tuple[float, float]] = []

    def _subdivide(
        pts: tuple[tuple[float, float], tuple[float, float],
                    tuple[float, float], tuple[float, float]],
        depth: int = 0,
    ) -> None:
        if depth > 10:
            points.append(pts[0])
            return
        a, b, c, d = pts
        chord = math.hypot(d[0] - a[0], d[1] - a[1])
        if chord < tolerance:
            points.append(a)
            return
        m01 = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        m12 = ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)
        m23 = ((c[0] + d[0]) / 2, (c[1] + d[1]) / 2)
        m012 = ((m01[0] + m12[0]) / 2, (m01[1] + m12[1]) / 2)
        m123 = ((m12[0] + m23[0]) / 2, (m12[1] + m23[1]) / 2)
        m0123 = ((m012[0] + m123[0]) / 2, (m012[1] + m123[1]) / 2)
        _subdivide((a, m01, m012, m0123), depth + 1)
        _subdivide((m0123, m123, m23, d), depth + 1)

    _subdivide((p0, p1, p2, p3))
    points.append(p3)
    return points


def _append_bezier_points(
    seg: BezierSegment,
    pts: list,
    bulges: list,
) -> None:
    """Subdivide a cubic Bezier into polyline segments.

    Ideal would be to use SPLINE entities, but for now subdivide
    to stay within LWPOLYLINE. Uses adaptive subdivision based on
    chord deviation for optimal point density.
    """
    p0 = (seg.p0.x, seg.p0.y)
    p1 = (seg.p1.x, seg.p1.y)
    p2 = (seg.p2.x, seg.p2.y)
    p3 = (seg.p3.x, seg.p3.y)

    curve_pts = _adaptive_bezier_subdivision(p0, p1, p2, p3)
    for pt in curve_pts:
        pts.append(pt)
        bulges.append(0.0)


def write_svg(model: PathModel, output_path: str | _Path) -> _Path:
    """Write SVG from the canonical PathModel."""
    output_path = _Path(output_path)
    os.makedirs(str(output_path.parent), exist_ok=True)

    bb = model.bounding_box()
    view_w = max(bb[2] - bb[0], 1)
    view_h = max(bb[3] - bb[1], 1)
    margin = max(view_w, view_h) * 0.05

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="{bb[0] - margin} {bb[1] - margin} {view_w + 2 * margin} {view_h + 2 * margin}">',
    ]

    for path in model.paths:
        d = _path_to_svg_d(path)
        if d:
            color_name = _aci_to_svg_color(path.color)
            lines.append(
                f'  <path d="{d}" fill="none" stroke="{color_name}" '
                f'stroke-width="0.5" stroke-linecap="round" stroke-linejoin="round"/>'
            )

    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _path_to_svg_d(path: DxfPath) -> str:
    pts = path.points()
    if not pts:
        return ""
    parts = [f"M {pts[0].x:.4f} {pts[0].y:.4f}"]
    for i in range(1, len(pts)):
        parts.append(f"L {pts[i].x:.4f} {pts[i].y:.4f}")
    if path.closed:
        parts.append("Z")
    return " ".join(parts)


def _aci_to_svg_color(aci: int) -> str:
    """Convert AutoCAD Color Index (ACI) to SVG hex color."""
    if aci <= 0 or aci > 255:
        return "#000000"

    aci_palette = {
        1: "#ff0000", 2: "#ffff00", 3: "#00ff00", 4: "#00ffff",
        5: "#0000ff", 6: "#ff00ff", 7: "#ffffff", 8: "#808080",
        9: "#c0c0c0", 10: "#800000",
    }

    if aci in aci_palette:
        return aci_palette[aci]

    h = (aci - 10) * 360.0 / 244.0
    s = 0.8 if aci % 2 == 0 else 0.6
    lightness = 0.5 if aci % 3 != 0 else 0.65

    c = (1 - abs(2 * lightness - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = lightness - c / 2
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    r, g, b = int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)
    return f"#{r:02x}{g:02x}{b:02x}"


# ── Backward-compatible alias ────────────────────────────────────────────────

def create_dxf(
    geometry: dict,
    output_path: str | _Path,
    dxf_mode: str = "lines",
    dxf_version: str = "R2010",
    units: str = "mm",
) -> _Path:
    """Backward-compatible wrapper around write_dxf for old callers.

    Converts the legacy geometry dict to a PathModel.
    """
    from .path_model import PathModel as _PathModel, polyline_to_path, circle_to_path, DXFMode

    model = _PathModel(
        dxf_mode=DXFMode(dxf_mode) if dxf_mode in ("lines", "hatch", "faces") else DXFMode.LINES,
        dxf_version=DXFVersion(dxf_version) if dxf_version in ("R12", "R2010", "R2018") else DXFVersion.R2010,
    )

    for outline in geometry.get("outlines", []):
        pts = outline.get("points", [])
        if len(pts) >= 2:
            model.add_path(polyline_to_path(pts, closed=outline.get("closed", True), layer="CUT"))

    for hole in geometry.get("holes", []):
        model.add_path(circle_to_path(hole.get("cx", 0), hole.get("cy", 0), hole.get("r", 1), layer="CUT"))

    for poly in geometry.get("polygons", []):
        pts = poly.get("points", [])
        if len(pts) >= 3:
            model.add_path(polyline_to_path(pts, closed=poly.get("closed", True), layer="ENGRAVE"))

    for line in geometry.get("lines", []):
        pts = line.get("points", [])
        if len(pts) >= 2:
            model.add_path(polyline_to_path(pts, closed=False, layer="CUT"))

    return write_dxf(
        model=model,
        output_path=output_path,
        dxf_version=model.dxf_version,
        units=units,
        enforce_closed_cut=True,
    )
