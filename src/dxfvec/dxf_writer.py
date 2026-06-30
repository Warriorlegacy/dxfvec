"""DXF file generation from extracted geometry using ezdxf.

Layer convention (matches the CMA agent's system prompt):
  CUT  (red,  CONTINUOUS) — part outlines (LWPOLYLINEs) + holes (CIRCLEs)
  BEND (blue, DASHED)     — fold/bend lines
  DIM  (green,CONTINUOUS) — dimension text annotations

geometry dict schema:
  {
    "outlines":   [{"points": [[x, y], ...], "closed": true}],
    "holes":      [{"cx": float, "cy": float, "r": float}],
    "bend_lines": [{"points": [[x, y], ...]}],
    "dimensions": [{"x": float, "y": float, "text": "150mm"}]
  }
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import ezdxf

LAYERS: dict[str, dict[str, Any]] = {
    "CUT":  {"color": 1, "linetype": "CONTINUOUS"},
    "BEND": {"color": 5, "linetype": "DASHED"},
    "DIM":  {"color": 3, "linetype": "CONTINUOUS"},
}


def _flatten(pts):
    if not pts:
        return []
    if isinstance(pts[0], dict):
        return [(p["x"], p["y"]) for p in pts]
    return [(p[0], p[1]) for p in pts]


def create_dxf(geometry: dict[str, Any], output_path: str | Path) -> Path:
    """Write a layered DXF file from the geometry dict."""
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

    for bend in geometry.get("bend_lines", []):
        pts = _flatten(bend.get("points", []))
        if len(pts) >= 2:
            msp.add_lwpolyline(
                pts, close=False,
                dxfattribs={"layer": "BEND", "elevation": 0, "thickness": 0})

    for dim in geometry.get("dimensions", []):
        msp.add_text(
            dim["text"],
            dxfattribs={
                "layer": "DIM", "height": 2.5,
                "insert": (dim["x"], dim["y"]),
            },
        )

    doc.saveas(output_path)
    ezdxf.readfile(str(output_path))
    return output_path
