"""dxfvec — raster engineering drawings → DXF vector files. Industry-grade.

Supports three engines:
  - Classic: local OpenCV contour tracing (no API keys)
  - Advanced: local VTracer AI-style vectorization (no API keys)
  - Cloud AI: external APIs — BYOK (Vectorizer.AI, DXFai)

Key industry-grade features (v2.0):
  - Canonical PathModel — single source of truth for all geometry (PRD §7.3)
  - QA Report — DXF audit, open-path detection, self-intersection, bounding box
  - Arc/circle detection — true ARC/CIRCLE entities, not polyline approximations
  - Tolerance-based node reduction — explicit ε in real-world units
  - DXF version selection (R12/R2010/R2018) with correct $INSUNITS
  - Closed-loop enforcement for CUT layers
  - Calibration — pixel-to-real-world-unit scale factor
"""
__version__ = "2.0.0"

from .engines import ClassicEngine, AdvancedEngine, PRESETS, list_presets, apply_preset
from .cloud_providers import (
    get_cloud_provider,
    list_cloud_providers,
    get_api_key,
    list_configured_providers,
    CLOUD_PROVIDERS,
)
from .vectorizer import vectorize_image, Vectorizer, ImageModifier, ShapeDetector, DXFGenerator
from .dxf_writer import write_dxf, write_svg
from .preprocess import preprocess
from .ai_enhancer import enhance, AIEnhancer, AIEnhancerConfig
from .path_model import (
    PathModel, Path, Calibration, TraceMode, DXFMode, DXFVersion,
    LayerName, Vec2, polyline_to_path, circle_to_path,
    LineSegment, ArcSegment, BezierSegment,
)
from .qa_report import QAReport, generate_qa_report, save_qa_report
from .curve_fitting import detect_and_replace_arcs, douglas_peucker

__all__ = [
    # Engines
    "ClassicEngine",
    "AdvancedEngine",
    "PRESETS",
    "list_presets",
    "apply_preset",
    # Cloud providers
    "get_cloud_provider",
    "list_cloud_providers",
    "get_api_key",
    "list_configured_providers",
    "CLOUD_PROVIDERS",
    # Core vectorization
    "vectorize_image",
    "Vectorizer",
    "ImageModifier",
    "ShapeDetector",
    "DXFGenerator",
    # DXF writer
    "write_dxf",
    "write_svg",
    # Preprocessing
    "preprocess",
    # AI Enhancer
    "enhance",
    "AIEnhancer",
    # Path model (canonical geometry)
    "PathModel",
    "Path",
    "Calibration",
    "TraceMode",
    "DXFMode",
    "DXFVersion",
    "LayerName",
    "Vec2",
    "polyline_to_path",
    "circle_to_path",
    "LineSegment",
    "ArcSegment",
    "BezierSegment",
    # QA report
    "QAReport",
    "generate_qa_report",
    "save_qa_report",
    # Curve fitting
    "detect_and_replace_arcs",
    "douglas_peucker",
]
