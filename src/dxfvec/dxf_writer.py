"""DXF file generation from extracted geometry using ezdxf.

Layer convention (CNC / laser ready):
  CUT    (red,   CONTINUOUS) — part outlines (LWPOLYLINEs) + holes (CIRCLEs) + cut lines
  ENGRAVE(blue,  CONTINUOUS) — filled regions / hatch areas
  BEND   (blue,  DASHED)     — fold/bend lines
  DIM    (green, CONTINUOUS) — dimension text annotations

geometry dict schema:
  {
    "outlines":   [{"points": [[x, y], ...], "closed": true}],
    "holes":      [{"cx": float, "cy": float, "r": float}],
    "bend_lines": [{"points": [[x, y], ...]}],
    "dimensions": [{"x": float, "y": float, "text": "150mm"}],
    "polygons":   [{"points": [[x, y], ...], "closed": true}]  # for Faces / Hatch mode
  }

DXF modes:
  lines  — outlines + holes + lines → CUT layer
  hatch  — closed polygons as HATCH entities → ENGRAVE layer
  faces  — all closed shapes as LWPOLYLINEs → CUT/ENGRAVE depending on type
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import ezdxf

LAYERS: dict[str, dict[str, Any]] = {
    "CUT":     {"color": 1, "linetype": "CONTINUOUS"},
    "ENGRAVE": {"color": 5, "linetype": "CONTINUOUS"},
    "BEND":    {"color": 5, "linetype": "DASHED"},
    "DIM":     {"color": 3, "linetype": "CONTINUOUS"},
}


def _flatten(pts):
    if not pts:
        return []
    if isinstance(pts[0], dict):
        return [(p["x"], p["y"]) for p in pts]
    return [(p[0], p[1]) for p in pts]


def create_dxf(
    geometry: dict[str, Any],
    output_path: str | Path,
    dxf_mode: str = "lines",
) -> Path:
    """Write a layered DXF file from the geometry dict.

    Args:
        geometry: Geometry dictionary with outlines, holes, polygons, etc.
        output_path: Where to save the DXF file.
        dxf_mode: One of 'lines', 'hatch', 'faces'.
            - lines: outlines/holes/lines on CUT layer (default)
            - hatch: closed polygons as HATCH on ENGRAVE layer
            - faces: closed shapes as LWPOLYLINE on CUT/ENGRAVE
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"] = 4

    for name, props in LAYERS.items():
        layer = doc.layers.add(name)
        layer.color = props["color"]
        if props["linetype"] != "CONTINUOUS":
            layer.linetype = props["linetype"]

    msp = doc.modelspace()
    DXF2D = {"elevation": 0, "thickness": 0}

    mode = (dxf_mode or "lines").lower()

    if mode == "hatch":
        _write_hatch_mode(msp, geometry, DXF2D)
    elif mode == "faces":
        _write_faces_mode(msp, geometry, DXF2D)
    else:  # lines (default)
        _write_lines_mode(msp, geometry, DXF2D)

    doc.saveas(output_path)
    ezdxf.readfile(str(output_path))
    return output_path


def _write_lines_mode(msp, geometry: dict[str, Any], DXF2D: dict) -> None:
    """Standard cut-path mode: outlines + holes + lines on CUT layer."""
    for outline in geometry.get("outlines", []):
        pts = _flatten(outline.get("points", []))
        if len(pts) >= 2:
            msp.add_lwpolyline(
                pts, close=outline.get("closed", True),
                dxfattribs={"layer": "CUT", **DXF2D})

    for hole in geometry.get("holes", []):
        msp.add_circle(
            center=(hole["cx"], hole["cy"], 0), radius=hole["r"],
            dxfattribs={"layer": "CUT"})

    for poly in geometry.get("polygons", []):
        pts = _flatten(poly.get("points", []))
        if len(pts) >= 3:
            msp.add_lwpolyline(
                pts, close=poly.get("closed", True),
                dxfattribs={"layer": "CUT", **DXF2D})


def _write_hatch_mode(msp, geometry: dict[str, Any], DXF2D: dict) -> None:
    """Hatch mode: closed polygons become HATCH entities on ENGRAVE layer.

    Also keeps outlines on CUT for reference.
    """
    # Keep thin outlines on CUT for reference
    for outline in geometry.get("outlines", []):
        pts = _flatten(outline.get("points", []))
        if len(pts) >= 2:
            msp.add_lwpolyline(
                pts, close=outline.get("closed", True),
                dxfattribs={"layer": "CUT", **DXF2D})

    # Hatch all closed polygons
    polygons = geometry.get("polygons", [])
    if not polygons:
        # Fall back to outlines if no explicit polygons
        polygons = geometry.get("outlines", [])

    for poly in polygons:
        pts = _flatten(poly.get("points", []))
        if len(pts) < 3:
            continue
        try:
            hatch = msp.add_hatch(
                color=5,
                dxfattribs={"layer": "ENGRAVE"},
            )
            hatch.paths.add_polyline_path(
                pts,
                is_closed=poly.get("closed", True),
            )
            hatch.set_pattern_fill("SOLID", scale=1.0)
        except Exception:
            # Fallback: if HATCH fails, emit a closed polyline
            msp.add_lwpolyline(
                pts, close=poly.get("closed", True),
                dxfattribs={"layer": "ENGRAVE", **DXF2D})


def _write_faces_mode(msp, geometry: dict[str, Any], DXF2D: dict) -> None:
    """Faces mode: closed shapes as LWPOLYLINE on CUT/ENGRAVE.

    - Outer outlines → CUT layer
    - Interior polygons / holes → ENGRAVE layer (filled appearance)
    """
    for outline in geometry.get("outlines", []):
        pts = _flatten(outline.get("points", []))
        if len(pts) >= 2:
            msp.add_lwpolyline(
                pts, close=outline.get("closed", True),
                dxfattribs={"layer": "CUT", **DXF2D})

    for hole in geometry.get("holes", []):
        msp.add_circle(
            center=(hole["cx"], hole["cy"], 0), radius=hole["r"],
            dxfattribs={"layer": "CUT"})

    # Polygons and closed shapes on ENGRAVE
    faces = geometry.get("polygons", [])
    if not faces:
        faces = geometry.get("outlines", [])

    for poly in faces:
        pts = _flatten(poly.get("points", []))
        if len(pts) >= 3:
            msp.add_lwpolyline(
                pts, close=poly.get("closed", True),
                dxfattribs={"layer": "ENGRAVE", **DXF2D})

