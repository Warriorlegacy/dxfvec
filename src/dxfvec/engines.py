"""Engine abstraction for dxfvec — Classic, Advanced (VTracer), and Cloud AI (BYOK).

Each engine implements a common interface:
    convert(image_path, output_dir, config) -> dict with dxf, qa_report, geometry

Engines now produce the canonical PathModel (PRD §7.3) and include
QA reports (PRD §3.4 P0) with every export.

Changes vs v1:
  - All engines produce PathModel → write_dxf for DXF generation
  - QA report generated automatically after every conversion
  - Arc/circle detection post-processing (PRD §3.3 P0)
  - Tolerance-based node reduction (explicit ε in mm, not abstract slider)
  - DXF version selection (PRD §3.4 P0)
  - Calibration-aware units declaration in DXF header (PRD §3.4 P0)
  - Centerline tracing mode (PRD §3.2 P0)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .dxf_writer import write_dxf, write_svg
from .vectorizer import (
    Vectorizer,
    ImageModifier,
    ShapeDetector,
)
from .preprocess import preprocess
from .path_model import (
    Calibration,
    DXFMode,
    DXFVersion,
    PathModel,
    TraceMode,
    Vec2,
    polyline_to_path,
    circle_to_path,
)
from .qa_report import generate_qa_report, save_qa_report
from .curve_fitting import detect_and_replace_arcs, douglas_peucker


# ── Presets ──────────────────────────────────────────────────────────────────

PRESETS: dict[str, dict[str, Any]] = {
    "logo_engrave": {
        "label": "Logo Engrave",
        "min_area": 50,
        "simplify_tolerance": 1.0,
        "smoothing": 1.0,
        "tolerance_mm": 0.08,
        "corner_threshold": 70,
        "noise_filter": 2,
        "description": "High-detail for logos and artwork engraving",
    },
    "laser_stencil": {
        "label": "Laser Stencil",
        "min_area": 200,
        "simplify_tolerance": 2.5,
        "smoothing": 2.0,
        "tolerance_mm": 0.25,
        "corner_threshold": 40,
        "noise_filter": 5,
        "description": "Simplified paths for fast laser cutting",
    },
    "technical_drawing": {
        "label": "Technical Drawing",
        "min_area": 100,
        "simplify_tolerance": 1.5,
        "smoothing": 1.0,
        "tolerance_mm": 0.10,
        "corner_threshold": 60,
        "noise_filter": 3,
        "description": "Preserves dimensions, lines, and precision",
    },
    "contour_map": {
        "label": "Contour Map",
        "min_area": 30,
        "simplify_tolerance": 0.8,
        "smoothing": 0.5,
        "tolerance_mm": 0.05,
        "corner_threshold": 80,
        "noise_filter": 1,
        "description": "Fine detail for topographic maps and contours",
    },
}


def apply_preset(config: dict[str, Any], preset_name: str) -> dict[str, Any]:
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
    @abstractmethod
    def convert(
        self,
        image_path: str | Path,
        output_dir: str | Path,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...


# ── Classic engine (local OpenCV) ────────────────────────────────────────────

class ClassicEngine(BaseEngine):
    """Deterministic pipeline using image processing and contour tracing.

    Always available, no API keys required. Now produces canonical PathModel
    with QA report, arc detection, and tolerance-based node reduction.
    """

    name = "classic"

    def convert(
        self,
        image_path: str | Path,
        output_dir: str | Path,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cfg = config or {}
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Extract config with defaults
        scale_factor = cfg.get("scale_factor")
        min_area = cfg.get("min_area", 100)
        simplify_tolerance = cfg.get("simplify_tolerance", 1.5)
        dxf_mode_str = cfg.get("dxf_mode", "lines")
        dxf_version_str = cfg.get("dxf_version", "R2010")
        trace_mode_str = cfg.get("trace_mode", "outline")
        tolerance_mm = cfg.get("tolerance_mm", 0.15)
        detect_arcs = cfg.get("detect_arcs", True)
        retr_mode_str = cfg.get("retr_mode", "auto")

        # Calibration
        calibration = None
        if "calibration" in cfg:
            cal = cfg["calibration"]
            if isinstance(cal, dict):
                calibration = Calibration(
                    reference_px_length=cal.get("reference_px_length", 0),
                    real_world_length=cal.get("real_world_length", 0),
                    unit=cal.get("unit", "mm"),
                )
            elif isinstance(cal, Calibration):
                calibration = cal

        retr_modes = {
            "auto": None,
            "external": cv2.RETR_EXTERNAL,
            "list": cv2.RETR_LIST,
            "tree": cv2.RETR_TREE,
            "ccomp": cv2.RETR_CCOMP,
        }

        # Use the upgraded Vectorizer
        vec = Vectorizer(
            min_area=min_area,
            simplify_tolerance=simplify_tolerance,
            retr_mode=retr_modes.get(retr_mode_str, cv2.RETR_LIST),
        )

        result = vec.vectorize(
            image_path=image_path,
            output_dir=output_dir,
            scale_factor=scale_factor,
            calibration=calibration,
            tolerance_mm=tolerance_mm,
            detect_arcs=detect_arcs,
            trace_mode=trace_mode_str,
            dxf_mode=dxf_mode_str,
            dxf_version=dxf_version_str,
        )

        # Apply CNC layer rewrite if needed
        if cfg.get("cnc_layers", True):
            _apply_cnc_layers(Path(result["dxf"]), dxf_mode_str)

        result["engine"] = self.name
        result["dxf_mode"] = dxf_mode_str
        return result


def _apply_cnc_layers(dxf_path: Path, mode: str = "lines") -> None:
    """Rewrite DXF layers to CUT/ENGRAVE semantics for CNC/laser workflows."""
    try:
        import ezdxf
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        cut_layers = {"OUTLINE", "HOLE", "LINE", "POLYGON", "ELLIPSE", "CUT"}
        engrave_layers = set()

        if mode == "hatch":
            engrave_layers = {"POLYGON", "HATCH", "FILL"}
        elif mode == "faces":
            engrave_layers = {"POLYGON", "ELLIPSE"}

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

        layer_colors = {"CUT": 1, "ENGRAVE": 5, "BEND": 5, "DIM": 3}
        for target_name, color in layer_colors.items():
            if target_name not in doc.layers:
                doc.layers.add(target_name, color=color)

        for ent in msp:
            old_layer = ent.dxf.get("layer", "0")
            new_layer = layer_map.get(old_layer, old_layer)
            ent.dxf["layer"] = new_layer

        doc.saveas(str(dxf_path))
    except Exception:
        pass


# ── Advanced engine (local VTracer AI) ───────────────────────────────────────

class AdvancedEngine(BaseEngine):
    """Local AI-style engine using VTracer open-source vectorizer.

    VTracer SVG output is parsed into the canonical PathModel, then
    exported through the same write_dxf pipeline with QA reports.
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
        svg_path = output_dir / "vtracer_output.svg"
        dxf_path = output_dir / "drawing.dxf"

        # Calibration
        calibration = None
        if "calibration" in cfg:
            cal = cfg["calibration"]
            if isinstance(cal, dict):
                calibration = Calibration(
                    reference_px_length=cal.get("reference_px_length", 0),
                    real_world_length=cal.get("real_world_length", 0),
                    unit=cal.get("unit", "mm"),
                )
            elif isinstance(cal, Calibration):
                calibration = cal

        scale_factor = cfg.get("scale_factor")
        dxf_mode_str = cfg.get("dxf_mode", "lines")
        dxf_version_str = cfg.get("dxf_version", "R2010")
        trace_mode_str = cfg.get("trace_mode", "outline")
        tolerance_mm = cfg.get("tolerance_mm", 0.15)
        detect_arcs = cfg.get("detect_arcs", True)

        # Apply preset to vtracer config
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

        # Extract and cast VTracer params (prevents PyO3 crashes)
        colormode = str(vcfg.get("colormode", "binary"))
        hierarchical = str(vcfg.get("hierarchical", "stacked"))
        mode = str(vcfg.get("mode", "spline"))
        try:
            filter_speckle = int(float(vcfg.get("filter_speckle", 4)))
        except (ValueError, TypeError):
            filter_speckle = 4
        try:
            color_precision = int(float(vcfg.get("color_precision", 6)))
        except (ValueError, TypeError):
            color_precision = 6
        try:
            layer_difference = int(float(vcfg.get("layer_difference", 16)))
        except (ValueError, TypeError):
            layer_difference = 16
        try:
            corner_threshold = int(float(vcfg.get("corner_threshold", 60)))
        except (ValueError, TypeError):
            corner_threshold = 60
        try:
            length_threshold = float(vcfg.get("length_threshold", 4.0))
        except (ValueError, TypeError):
            length_threshold = 4.0
        try:
            max_iterations = int(float(vcfg.get("max_iterations", vcfg.get("segment_length", 10))))
        except (ValueError, TypeError):
            max_iterations = 10
        try:
            splice_threshold = int(float(vcfg.get("splice_threshold", 45)))
        except (ValueError, TypeError):
            splice_threshold = 45
        try:
            path_precision = int(float(vcfg.get("path_precision", 8)))
        except (ValueError, TypeError):
            path_precision = 8

        vtracer.convert_image_to_svg_py(
            str(image_path), str(svg_path),
            colormode, hierarchical, mode,
            filter_speckle, color_precision, layer_difference,
            corner_threshold, length_threshold, max_iterations,
            splice_threshold, path_precision,
        )

        # Parse SVG → PathModel (node reduction is done inside)
        model = self._svg_to_pathmodel(
            svg_path, scale_factor, calibration,
            dxf_mode_str, dxf_version_str, trace_mode_str,
            tolerance_mm=tolerance_mm,
        )

        # Arc/circle detection
        if detect_arcs:
            detect_and_replace_arcs(model, max_deviation=tolerance_mm)

        # Scale if calibration provided
        if calibration and calibration.is_valid:
            model.scale(calibration.scale_factor)
        elif scale_factor is not None and scale_factor != 1.0:
            model.scale(scale_factor)

        # Write DXF through canonical writer
        write_dxf(
            model=model,
            output_path=dxf_path,
            dxf_version=model.dxf_version,
            units=calibration.unit if calibration else "mm",
            enforce_closed_cut=True,
            max_gap_close=3.0,
        )

        # Write SVG
        write_svg(model, output_dir / "output.svg")

        # Generate QA report
        qa_report = generate_qa_report(model, dxf_path=dxf_path)

        # Save QA artifacts
        qa_json_path = output_dir / "qa_report.json"
        qa_json_path.write_text(qa_report.to_json(), encoding="utf-8")
        qa_md_path = output_dir / "qa_report.md"
        qa_md_path.write_text(qa_report.to_markdown(), encoding="utf-8")

        # Apply CNC layers
        if cfg.get("cnc_layers", True):
            _apply_cnc_layers(dxf_path, dxf_mode_str)

        # Write review (backward compat)
        self._write_review(model, qa_report, image_path.name,
                          output_dir / "review.md", preset_name or "custom", dxf_mode_str)

        return {
            "dxf": str(dxf_path),
            "qa_report": qa_report.to_dict(),
            "geometry": self._model_to_geometry(model),
            "engine": self.name,
            "dxf_mode": dxf_mode_str,
            "stats": {
                "paths": model.entity_count(),
                "closed": model.closed_path_count(),
                "open": model.open_path_count(),
                "segments": qa_report.total_segments,
                "nodes": qa_report.node_count,
                "layers": len(qa_report.layers),
            },
        }

    def _svg_to_pathmodel(
        self,
        svg_path: Path,
        scale_factor: float | None,
        calibration: Calibration | None,
        dxf_mode_str: str,
        dxf_version_str: str,
        trace_mode_str: str,
        tolerance_mm: float = 0.15,
    ) -> PathModel:
        import xml.etree.ElementTree as ET
        import re

        model = PathModel(
            trace_mode=TraceMode(trace_mode_str) if trace_mode_str in ("outline", "centerline") else TraceMode.OUTLINE,
            dxf_mode=DXFMode(dxf_mode_str) if dxf_mode_str in ("lines", "hatch", "faces") else DXFMode.LINES,
            dxf_version=DXFVersion(dxf_version_str) if dxf_version_str in ("R12", "R2010", "R2018") else DXFVersion.R2010,
            source_image="",
        )
        if calibration and calibration.is_valid:
            model.calibration = calibration

        svg_content = svg_path.read_text(encoding="utf-8")
        root = ET.fromstring(svg_content)
        ns = {"svg": "http://www.w3.org/2000/svg"}

        paths = root.findall(".//{http://www.w3.org/2000/svg}path")
        if not paths:
            paths = root.findall(".//path")

        for path_elem in paths:
            d = path_elem.get("d", "")
            if not d:
                continue
            points = self._parse_svg_path(d)
            if len(points) < 3:
                continue

            closed = d.strip().endswith("Z") or d.strip().endswith("z")
            area = self._estimate_polygon_area(points)

            if closed and area < 0:
                cx = sum(p[0] for p in points) / len(points)
                cy = sum(p[1] for p in points) / len(points)
                r = self._estimate_radius(points)
                model.add_path(circle_to_path(cx, cy, r, layer="CUT"))
            else:
                simplified = douglas_peucker(
                    [Vec2(p[0], p[1]) for p in points],
                    epsilon=tolerance_mm,
                    closed=closed,
                )
                model.add_path(polyline_to_path(
                    [(p.x, p.y) for p in simplified],
                    closed=closed, layer="CUT",
                ))

        return model

    def _apply_node_reduction(self, model: PathModel, tolerance_mm: float) -> None:
        for idx, path in enumerate(model.paths):
            pts = path.points()
            if len(pts) < 3:
                continue
            simplified = douglas_peucker(pts, epsilon=tolerance_mm, closed=path.closed)
            model.paths[idx] = polyline_to_path(
                [(p.x, p.y) for p in simplified],
                closed=path.closed, layer=path.layer,
            )

    @staticmethod
    def _parse_svg_path(d: str) -> list[list[float]]:
        import re
        points = []
        numbers = re.findall(r"[-+]?\d*\.?\d+", d)
        if len(numbers) < 2:
            return points
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

    @staticmethod
    def _estimate_polygon_area(points: list[list[float]]) -> float:
        if len(points) < 3:
            return 0.0
        area = 0.0
        n = len(points)
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        return area / 2.0

    @staticmethod
    def _estimate_radius(points: list[list[float]]) -> float:
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

    @staticmethod
    def _model_to_geometry(model: PathModel) -> dict:
        outlines = []
        holes = []
        for path in model.paths:
            pts = [(p.x, p.y) for p in path.points()]
            if path.layer == "CUT":
                outlines.append({"points": pts, "closed": path.closed})
            else:
                outlines.append({"points": pts, "closed": path.closed})
        return {"outlines": outlines, "holes": holes, "bend_lines": [], "dimensions": []}

    def _write_review(self, model: PathModel, qa: Any, source_name: str,
                       output_path: Path, preset: str, dxf_mode: str) -> None:
        cal = model.calibration
        coord = f"{cal.scale_factor:.4f} {cal.unit}/px" if cal and cal.is_valid else "pixel space"
        lines = [
            f"# DXF Vectorization Review — {source_name}",
            f"\n**Engine:** Advanced (VTracer)  |  **Preset:** {preset}  |  **Mode:** {dxf_mode}  |  **Coords:** {coord}",
            "\n## QA Summary\n",
            "| Metric | Value |",
            "|---|---|",
            f"| Entities | {qa.entity_count} |",
            f"| Closed | {qa.closed_path_count} |",
            f"| Open | {qa.open_path_count} |",
            f"| Self-intersections | {len(qa.self_intersections)} |",
            f"| DXF audit | {'PASS' if qa.dxf_audit_pass else 'FAIL'} |",
            "\n## Layers\n",
        ]
        for l in qa.layers:
            lines.append(f"- {l.name} ({l.color_aci}): {l.entity_count} entities")
        if qa.warnings:
            lines.append("\n## Warnings\n")
            for w in qa.warnings:
                lines.append(f"- ⚠ {w}")
        output_path.write_text("\n".join(lines), encoding="utf-8")
