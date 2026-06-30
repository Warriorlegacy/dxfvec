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


def create_dxf(geometry: dict[str, Any], output_path: str | Path) -> Path:
    """Write a layered DXF file from the geometry dict. Raises on validation failure."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"] = 4  # mm

    # Register layers
    for name, props in LAYERS.items():
        layer = doc.layers.add(name)
        layer.color = props["color"]
        if props["linetype"] != "CONTINUOUS":
            layer.linetype = props["linetype"]

    msp = doc.modelspace()

    # CUT — part outlines
    for outline in geometry.get("outlines", []):
        pts = outline.get("points", [])
        if len(pts) >= 2:
            msp.add_lwpolyline(
                pts,
                close=outline.get("closed", True),
                dxfattribs={"layer": "CUT"},
            )

    # CUT — circular holes
    for hole in geometry.get("holes", []):
        msp.add_circle(
            center=(hole["cx"], hole["cy"]),
            radius=hole["r"],
            dxfattribs={"layer": "CUT"},
        )

    # BEND — fold lines
    for bend in geometry.get("bend_lines", []):
        pts = bend.get("points", [])
        if len(pts) >= 2:
            msp.add_lwpolyline(
                pts,
                close=False,
                dxfattribs={"layer": "BEND"},
            )

    # DIM — dimension text
    for dim in geometry.get("dimensions", []):
        msp.add_text(
            dim["text"],
            dxfattribs={
                "layer": "DIM",
                "height": 2.5,
                "insert": (dim["x"], dim["y"]),
            },
        )

    doc.saveas(output_path)

    # Validate — raises ezdxf.DXFStructureError on corruption
    ezdxf.readfile(str(output_path))

    return output_path
