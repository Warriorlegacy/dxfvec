"""Engine abstraction for dxfvec — Classic, Advanced (VTracer), and Cloud AI (BYOK).

Each engine implements a common interface:
    convert(image_path, output_dir, config) -> dict with dxf, review, geometry

Engines:
  - ClassicEngine: local OpenCV contour tracing (no API keys)
  - AdvancedEngine: local VTracer AI-style vectorization (no API keys)
  - CloudAIEngine: external APIs like Vectorizer.AI, DXFai (BYOK keys required)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import cv2

from .dxf_writer import create_dxf
from .vectorizer import (
    Vectorizer,
    ImageModifier,
    ShapeDetector,
    DXFGenerator,
)
from .preprocess import preprocess


# ── Presets ──────────────────────────────────────────────────────────────────

PRESETS: dict[str, dict[str, Any]] = {
    "logo_engrave": {
        "label": "Logo Engrave",
        "min_area": 50,
        "simplify_tolerance": 1.0,
        "smoothing": 1.0,
        "corner_threshold": 70,
        "noise_filter": 2,
        "description": "High-detail for logos and artwork engraving",
    },
    "laser_stencil": {
        "label": "Laser Stencil",
        "min_area": 200,
        "simplify_tolerance": 2.5,
        "smoothing": 2.0,
        "corner_threshold": 40,
        "noise_filter": 5,
        "description": "Simplified paths for fast laser cutting",
    },
    "technical_drawing": {
        "label": "Technical Drawing",
        "min_area": 100,
        "simplify_tolerance": 1.5,
        "smoothing": 1.0,
        "corner_threshold": 60,
        "noise_filter": 3,
        "description": "Preserves dimensions, lines, and precision",
    },
    "contour_map": {
        "label": "Contour Map",
        "min_area": 30,
        "simplify_tolerance": 0.8,
        "smoothing": 0.5,
        "corner_threshold": 80,
        "noise_filter": 1,
        "description": "Fine detail for topographic maps and contours",
    },
}


def apply_preset(config: dict[str, Any], preset_name: str) -> dict[str, Any]:
    """Merge preset values into config, returning a new dict.
    
    Preset values override base config — this is intentional so that
    selecting a preset actually changes the vectorization parameters.
    """
    if preset_name not in PRESETS:
        return config
    preset = PRESETS[preset_name]
    merged = dict(config)
    for k, v in preset.items():
        if k not in ("label", "description"):
            merged[k] = v
    merged["preset"] = preset_name
    return merged


def list_presets() -> dict[str, dict[str, Any]]:
    return dict(PRESETS)


# ── Base engine interface ─────────────────────────────────────────────────────

class BaseEngine(ABC):
    """Abstract base class for all vectorization engines."""

    @abstractmethod
    def convert(
        self,
        image_path: str | Path,
        output_dir: str | Path,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convert an image to DXF.

        Args:
            image_path: Path to input raster image.
            output_dir: Directory for output files.
            config: Engine-specific configuration overrides.

        Returns:
            dict with keys: dxf, review, geometry, stats, engine
        """
        ...


# ── Classic engine (local OpenCV) ────────────────────────────────────────────

class ClassicEngine(BaseEngine):
    """Deterministic pipeline using image processing and contour tracing.

    Always available, no API keys required. Uses OpenCV for:
    - Adaptive image preprocessing
    - Multi-scale Canny edge fusion (photo mode)
    - Contour extraction, polygon/circle/line detection
    - DXF output with CNC/laser layer semantics
    """

    name = "classic"

    def convert(
        self,
        image_path: str | Path,
        output_dir: str | Path,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cfg = config or {}
        scale_factor = cfg.get("scale_factor")
        min_area = cfg.get("min_area", 100)
        simplify_tolerance = cfg.get("simplify_tolerance", 1.5)
        dxf_mode = cfg.get("dxf_mode", "lines")  # lines, hatch, faces
        retr_mode_str = cfg.get("retr_mode", "auto")  # auto, external, list

        # Map retr_mode string to cv2 constant
        retr_modes = {
            "auto": None,  # handled by Vectorizer
            "external": cv2.RETR_EXTERNAL,
            "list": cv2.RETR_LIST,
            "tree": cv2.RETR_TREE,
            "ccomp": cv2.RETR_CCOMP,
        }

        vec = Vectorizer(
            min_area=min_area,
            simplify_tolerance=simplify_tolerance,
            retr_mode=retr_modes.get(retr_mode_str, cv2.RETR_LIST),
        )

        result = vec.vectorize(image_path, output_dir, scale_factor=scale_factor)

        # Convert to CNC layer semantics if requested
        if cfg.get("cnc_layers", True):
            dxf_path = Path(result["dxf"])
            _apply_cnc_layers(dxf_path, dxf_mode)

        result["engine"] = self.name
        result["dxf_mode"] = dxf_mode
        return result


def _apply_cnc_layers(dxf_path: Path, mode: str = "lines") -> None:
    """Rewrite DXF layers to CUT/ENGRAVE semantics for CNC/laser workflows.

    Args:
        dxf_path: Path to the DXF file to modify in-place.
        mode: 'lines' for cut-only, 'hatch' for engrave fills, 'faces' for closed shapes.
    """
    try:
        import ezdxf
        import numpy as np

        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        # Determine which original layers map to CUT vs ENGRAVE
        cut_layers = {"OUTLINE", "HOLE", "LINE", "POLYGON", "ELLIPSE", "CUT"}
        engrave_layers = set()

        if mode == "hatch":
            # All filled regions go to ENGRAVE
            engrave_layers = {"POLYGON", "HATCH", "FILL"}
        elif mode == "faces":
            # Closed shapes become ENGRAVE, open paths stay CUT
            engrave_layers = {"POLYGON", "ELLIPSE"}

        # Rename layers
        layer_map: dict[str, str] = {}
        for layer_name in doc.layers:
            if layer_name in cut_layers:
                layer_map[layer_name] = "CUT"
            elif layer_name in engrave_layers:
                layer_map[layer_name] = "ENGRAVE"
            elif layer_name in ("BEND",):
                layer_map[layer_name] = "BEND"
            elif layer_name in ("DIM",):
                layer_map[layer_name] = "DIM"
            else:
                layer_map[layer_name] = layer_name

        # Create target layers with correct colors
        layer_colors = {
            "CUT": 1,
            "ENGRAVE": 5,
            "BEND": 5,
            "DIM": 3,
        }
        for target_name, color in layer_colors.items():
            if target_name not in doc.layers:
                doc.layers.add(target_name, color=color)

        # Update entity layers
        for ent in msp:
            old_layer = ent.dxf.get("layer", "0")
            new_layer = layer_map.get(old_layer, old_layer)
            ent.dxf["layer"] = new_layer

        doc.saveas(str(dxf_path))
    except Exception:
        pass  # If ezdxf rewrite fails, leave DXF as-is


# ── Advanced engine (local VTracer AI) ───────────────────────────────────────

class AdvancedEngine(BaseEngine):
    """Local AI-style engine using VTracer open-source vectorizer.

    No external API keys required. Produces high-quality SVG paths
    which are then converted to DXF with CNC layer semantics.
    """

    name = "advanced"

    def _default_config(self) -> dict[str, Any]:
        return {
            "colormode": "binary",
            "hierarchical": "stacked",
            "mode": "spline",
            "filter_speckle": 4,
            "color_precision": 6,
            "layer_difference": 16,
            "corner_threshold": 60,
            "length_threshold": 4.0,
            "path_precision": 8,
            "splice_threshold": 45,
            "segment_length": 10.0,
        }

    def convert(
        self,
        image_path: str | Path,
        output_dir: str | Path,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cfg = config or {}
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Merge defaults with user config
        vcfg = self._default_config()
        vcfg.update({k: v for k, v in cfg.items() if k in self._default_config()})

        try:
            import vtracer
        except ImportError:
            raise RuntimeError(
                "VTracer is required for the Advanced engine. "
                "Install it with: pip install vtracer"
            )

        image_path = Path(image_path)

        # VTracer outputs SVG — convert to our internal format then DXF
        svg_path = output_dir / "vtracer_output.svg"
        dxf_path = output_dir / "drawing.dxf"
        review_path = output_dir / "review.md"
        orig_px = output_dir / "original_size.json"

        # Run VTracer with appropriate settings
        preset_name = cfg.get("preset", "")
        if preset_name == "logo_engrave":
            vcfg.update({"filter_speckle": 2, "corner_threshold": 80,
                         "length_threshold": 3.0, "colormode": "binary"})
        elif preset_name == "laser_stencil":
            vcfg.update({"filter_speckle": 6, "corner_threshold": 35,
                         "length_threshold": 6.0, "colormode": "binary"})
        elif preset_name == "contour_map":
            vcfg.update({"filter_speckle": 1, "corner_threshold": 90,
                         "length_threshold": 2.0, "colormode": "color"})

        vtracer.convert_image_to_svg_py(str(image_path), str(svg_path), **vcfg)

        # Parse SVG paths and convert to DXF geometry
        geometry = _svg_to_geometry(svg_path, cfg.get("scale_factor"))
        dxf_mode = cfg.get("dxf_mode", "lines")

        create_dxf(geometry, dxf_path)

        # Write review
        _write_advanced_review(
            geometry, image_path.name, review_path,
            preset_name or "custom", dxf_mode
        )

        return {
            "dxf": str(dxf_path),
            "review": str(review_path),
            "geometry": geometry,
            "engine": self.name,
            "dxf_mode": dxf_mode,
            "stats": _count_geometry(geometry),
        }


def _svg_to_geometry(svg_path: Path, scale_factor: float | None = None) -> dict[str, Any]:
    """Parse VTracer SVG output into our geometry dict format.

    Extracts path data from SVG and converts to DXF-compatible geometry.
    """
    try:
        import xml.etree.ElementTree as ET
        import re

        svg_content = svg_path.read_text(encoding="utf-8")
        root = ET.fromstring(svg_content)

        # Handle SVG namespace
        ns = {"svg": "http://www.w3.org/2000/svg"}
        # Also try without namespace
        root_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

        if root_tag != "svg":
            # Wrapper element
            svg_elem = root.find(".//svg:svg", ns) or root.find(".//svg")
            if svg_elem is None:
                svg_elem = root
        else:
            svg_elem = root

        outlines = []
        holes = []

        # Find all path elements
        paths = svg_elem.findall(".//{http://www.w3.org/2000/svg}path")
        if not paths:
            paths = svg_elem.findall(".//path")

        for i, path in enumerate(paths):
            d = path.get("d", "")
            if not d:
                continue

            # Parse SVG path data into points
            points = _parse_svg_path(d)
            if len(points) < 3:
                continue

            # Determine if closed
            closed = d.strip().endswith("Z") or d.strip().endswith("z")

            # Estimate area to classify as outline vs hole
            area = _estimate_polygon_area(points)
            if closed and area < 0:
                # Negative winding or small area → hole
                holes.append({"points": points, "closed": closed,
                              "cx": sum(p[0] for p in points) / len(points),
                              "cy": sum(p[1] for p in points) / len(points),
                              "r": _estimate_radius(points)})
            else:
                outlines.append({"points": points, "closed": closed,
                                 "area": abs(area), "perimeter": _estimate_perimeter(points)})

        # Apply scale if provided
        if scale_factor is not None:
            outlines = _scale_geometry_items(outlines, scale_factor)
            holes = _scale_geometry_items(holes, scale_factor)

        return {
            "outlines": outlines,
            "holes": holes,
            "bend_lines": [],
            "dimensions": [],
        }

    except Exception as e:
        return {
            "outlines": [],
            "holes": [],
            "bend_lines": [],
            "dimensions": [],
            "error": f"SVG parse error: {e}",
        }


def _parse_svg_path(d: str) -> list[list[float]]:
    """Parse SVG path data string into a list of [x, y] points."""
    import re

    points = []
    # Extract all coordinate pairs (x, y)
    # Match sequences of numbers separated by spaces/commas
    numbers = re.findall(r"[-+]?\d*\.?\d+", d)
    if len(numbers) < 2:
        return points

    # Process in pairs
    i = 0
    while i < len(numbers) - 1:
        try:
            x = float(numbers[i])
            y = float(numbers[i + 1])
            points.append([x, y])
            i += 2
        except ValueError:
            i += 1

    return points


def _estimate_polygon_area(points: list[list[float]]) -> float:
    """Shoelace formula for polygon area. Positive = CCW, Negative = CW."""
    if len(points) < 3:
        return 0.0
    area = 0.0
    n = len(points)
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]
    return area / 2.0


def _estimate_perimeter(points: list[list[float]]) -> float:
    """Calculate total perimeter length of polyline."""
    if len(points) < 2:
        return 0.0
    perim = 0.0
    for i in range(len(points) - 1):
        dx = points[i + 1][0] - points[i][0]
        dy = points[i + 1][1] - points[i][1]
        perim += (dx * dx + dy * dy) ** 0.5
    return perim


def _estimate_radius(points: list[list[float]]) -> float:
    """Estimate equivalent radius from centroid to farthest point."""
    if len(points) < 3:
        return 0.0
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    max_r = 0.0
    for p in points:
        dx = p[0] - cx
        dy = p[1] - cy
        max_r = max(max_r, (dx * dx + dy * dy) ** 0.5)
    return max_r


def _scale_geometry_items(items: list[dict], factor: float) -> list[dict]:
    result = []
    for item in items:
        item = dict(item)
        if "points" in item:
            item["points"] = [[x * factor, y * factor] for x, y in item["points"]]
        for key in ("cx", "cy", "r"):
            if key in item:
                item[key] = item[key] * factor
        result.append(item)
    return result


def _count_geometry(geometry: dict) -> dict[str, int]:
    return {
        "outlines": len(geometry.get("outlines", [])),
        "holes": len(geometry.get("holes", [])),
        "lines": 0,
        "polygons": len(geometry.get("polygons", [])),
        "ellipses": 0,
    }


def _write_advanced_review(
    geometry: dict,
    source_name: str,
    output_path: Path,
    preset: str,
    dxf_mode: str,
) -> None:
    counts = _count_geometry(geometry)
    lines = [
        f"# DXF Vectorization Review — {source_name}",
        f"\n**Engine:** Advanced (VTracer)  |  **Preset:** {preset}  |  **Mode:** {dxf_mode}",
        "\n## Geometry detected\n",
        "| Entity  | Count | Layer |",
        "|---------|-------|-------|",
        f"| Outlines| {counts['outlines']:>5} | CUT   |",
        f"| Holes   | {counts['holes']:>5} | CUT   |",
        f"| Polygons| {counts['polygons']:>5} | ENGRAVE |",
        "\n## Mode details\n",
        f"- **Advanced engine**: VTracer open-source vectorization (colormode=binary)",
        "- 100% local processing — no API keys",
        f"- **Preset**: {preset}",
        "- DXF layers: CUT (cut paths), ENGRAVE (filled regions)",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")
